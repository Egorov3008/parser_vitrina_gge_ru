"""
Парсер витрины проектов vitrina.gge.ru

Основной модуль, запускающий бот и планировщик.
"""

import asyncio
import signal
from typing import Optional

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from src.browser.session import SessionManager
from src.config import get_config
from src.db.database import Database
from src.db.repository import Repository
from src.services.admin_panel import AdminPanelService
from src.services.scheduler import SchedulerService
from src.services.telegram import TelegramService
from src.utils.logger import get_logger, setup_logger

logger = get_logger()

# Глобальная переменная для scheduler
scheduler: Optional[SchedulerService] = None
admin_panel: Optional[AdminPanelService] = None


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка inline кнопок"""
    query = update.callback_query
    data = query.data

    await query.answer()

    if data == "cmd_status":
        await status_command(update, context)
    elif data == "cmd_run_now":
        await run_now_command(update, context)
    elif data == "cmd_stats":
        await stats_command(update, context)
    elif data == "cmd_admin":
        await admin_command(update, context)
    elif data == "cmd_help":
        await help_command(update, context)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start - приветствие"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    message = (
        "👋 <b>Добро пожаловать в парсер витрины проектов!</b>\n\n"
        "🔧 <b>Основные команды:</b>\n"
        "/status - статус последнего запуска\n"
        "/run_now - запустить парсер сейчас\n"
        "/stats - статистика проектов\n"
        "/admin - панель настроек (администраторам)\n\n"
        "⚙️ <b>Администраторам:</b>\n"
        "Используйте /admin или кнопку ниже для настройки фильтров:\n"
        "• Категории проектов\n"
        "• Регионы\n"
        "• Период фильтрации\n"
        "• Расписание запуска\n\n"
        "📚 <b>Документация:</b>\n"
        "ADMIN_PANEL.md - руководство по админ-панели"
    )

    keyboard = [
        [
            InlineKeyboardButton("📊 Статус", callback_data="cmd_status"),
            InlineKeyboardButton("🚀 Запустить", callback_data="cmd_run_now"),
        ],
        [
            InlineKeyboardButton("📈 Статистика", callback_data="cmd_stats"),
            InlineKeyboardButton("⚙️ Админ-панель", callback_data="cmd_admin"),
        ],
        [
            InlineKeyboardButton("❓ Справка", callback_data="cmd_help"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_html(message, reply_markup=reply_markup)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /status - информация о последнем запуске"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    if not scheduler:
        text = "❌ Планировщик не инициализирован"
        if update.callback_query:
            await update.callback_query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return

    run_log = scheduler.repository.get_last_run()

    if run_log:
        status_emoji = "✅" if run_log.get("status") == "success" else "❌"
        text = (
            f"{status_emoji} <b>Последний запуск</b>\n\n"
            f"🆔 ID: {run_log.get('id')}\n"
            f"⏰ Начат: {run_log.get('started_at', 'N/A')}\n"
            f"⏱ Завершён: {run_log.get('finished_at', 'N/A')}\n"
            f"📊 Статус: {run_log.get('status', 'N/A')}\n"
            f"📁 Найдено: {run_log.get('new_count', 0)} проектов"
        )
        if run_log.get("error_msg"):
            text += f"\n\n❌ Ошибка:\n<code>{run_log.get('error_msg')[:200]}</code>"
    else:
        text = "ℹ️ Запусков ещё не было"

    keyboard = [[InlineKeyboardButton("🚀 Запустить сейчас", callback_data="cmd_run_now")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")


async def run_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /run_now - запустить парсер немедленно"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    if not scheduler:
        text = "❌ Планировщик не инициализирован"
        if update.callback_query:
            await update.callback_query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return

    # Отправляем сообщение о запуске
    text = "⏳ <b>Запуск парсера...</b>"
    keyboard = [[InlineKeyboardButton("📊 Статус", callback_data="cmd_status")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        msg = await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        msg = await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")

    # Запускаем парсер
    try:
        await scheduler.run_immediately()
        text = "✅ <b>Парсер завершил работу!</b>\n\n"
        text += "Используйте /status для просмотра результатов."
        keyboard = [[InlineKeyboardButton("📊 Статус", callback_data="cmd_status")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await msg.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except Exception as e:
        text = f"❌ <b>Ошибка при запуске:</b>\n<code>{str(e)[:200]}</code>"
        keyboard = [[InlineKeyboardButton("🔄 Попробовать снова", callback_data="cmd_run_now")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await msg.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /stats - статистика проектов"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    if not scheduler:
        text = "❌ Планировщик не инициализирован"
        if update.callback_query:
            await update.callback_query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return

    stats = scheduler.repository.get_stats()
    errors = scheduler.repository.get_recent_errors(limit=3)

    text = (
        "📈 <b>Статистика проектов</b>\n\n"
        f"📁 Всего: {stats.get('total_projects', 0)}\n"
        f"✅ Уведомлено: {stats.get('notified_projects', 0)}\n"
        f"🆕 За сегодня: {stats.get('today_projects', 0)}\n"
    )

    if errors:
        text += "\n❌ <b>Последние ошибки:</b>\n"
        for err in errors[:3]:
            err_msg = err.get("error_msg", "N/A")[:50]
            text += f"• {err.get('started_at', 'N/A')}: {err_msg}\n"

    keyboard = [
        [InlineKeyboardButton("🚀 Запустить парсер", callback_data="cmd_run_now")],
        [InlineKeyboardButton("📊 Статус", callback_data="cmd_status")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /help - справка"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    message = (
        "📖 <b>Справка по парсеру витрины проектов</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔧 <b>Основные команды:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>/start</b>\n"
        "Приветственное сообщение с кнопками\n\n"
        "<b>/status</b>\n"
        "Показать информацию о последнем запуске парсера\n\n"
        "<b>/run_now</b>\n"
        "Запустить парсер немедленно (вне расписания)\n\n"
        "<b>/stats</b>\n"
        "Статистика проектов в базе данных\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚙️ <b>Админ-панель:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>/admin</b>\n"
        "Открыть панель управления настройками:\n"
        "• 📁 Категории проектов\n"
        "• 📍 Регионы\n"
        "• 📅 Период фильтрации\n"
        "• ⏰ Расписание (cron)\n"
        "• 👥 Управление администраторами\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "ℹ️ <b>Информация:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Парсер автоматически проверяет новые проекты\n"
        "по расписанию и отправляет уведомления в этот чат.\n\n"
        "Для доступа к админ-панели добавьте свой Telegram ID\n"
        "в переменную ADMIN_ID файла .env и перезапустите бота."
    )

    keyboard = [
        [
            InlineKeyboardButton("📊 Статус", callback_data="cmd_status"),
            InlineKeyboardButton("🚀 Запустить", callback_data="cmd_run_now"),
        ],
        [
            InlineKeyboardButton("📈 Статистика", callback_data="cmd_stats"),
            InlineKeyboardButton("⚙️ Админ-панель", callback_data="cmd_admin"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode="HTML")


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /admin - панель администратора"""
    global admin_panel
    if not admin_panel:
        await update.message.reply_text("❌ Админ-панель не инициализирована")
        return

    user_id = str(update.effective_user.id) if update.effective_user else ""

    # Проверка прав
    if not admin_panel._check_admin(update.effective_user.id if update.effective_user else 0):
        message = (
            "❌ <b>Доступ запрещён</b>\n\n"
            f"Ваш Telegram ID: <code>{user_id}</code>\n\n"
            "Для доступа к админ-панели:\n"
            "1. Откройте файл .env\n"
            "2. Добавьте ваш ID в ADMIN_ID:\n"
            f"<code>ADMIN_ID={user_id}</code>\n"
            "3. Перезапустите парсер\n\n"
            "Или попросите текущего администратора\n"
            "добавить вас через /add_admin"
        )
        await update.message.reply_html(message)
        return

    await admin_panel.show_admin_menu(update, context)


async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /add_admin - добавить администратора"""
    if update.effective_user is None:
        return

    user_id = str(update.effective_user.id)
    username = update.effective_user.username

    # Проверка: только админ может добавлять других
    repo = Repository(Database(get_config().db_path))
    if not repo.is_admin(user_id):
        await update.message.reply_text(
            "❌ Только администратор может добавлять других.\n\n"
            f"Ваш ID: <code>{user_id}</code>\n"
            "Добавьте себя в ADMIN_ID в .env файле.",
            parse_mode="HTML",
        )
        return

    args = context.args
    if not args:
        await update.message.reply_text(
            "Использование: /add_admin <telegram_id> [telegram_id2, ...]\n\n"
            f"Ваш ID: <code>{user_id}</code>\n\n"
            "Можно добавить несколько ID через запятую.",
            parse_mode="HTML",
        )
        return

    # Добавить всех указанных админов
    added = []
    for target_id in args:
        # Поддержка нескольких ID через запятую
        for tid in target_id.split(","):
            tid = tid.strip()
            if tid:
                repo.add_admin(tid)
                added.append(tid)

    await update.message.reply_text(
        f"✅ Добавлены администраторы:\n" + "\n".join(f"• {tid}" for tid in added)
    )


async def initialize_services() -> tuple:
    """Инициализировать все сервисы"""
    config = get_config()

    # БД
    db = Database(config.db_path)
    db.init_schema()

    # Репозиторий
    repository = Repository(db)

    # Синхронизировать админов из конфига в БД
    for admin_id in config.get_admin_ids():
        repository.add_admin(admin_id, "config")
    logger.info(f"Admins synced from config: {config.get_admin_ids()}")

    # Браузер
    session = SessionManager()
    await session.initialize()

    # Telegram
    telegram = TelegramService()
    await telegram.setup_commands()

    # Планировщик
    sched = SchedulerService(telegram, session, db, repository)
    await sched.initialize()

    logger.info("All services initialized")
    return db, repository, session, telegram, sched


async def shutdown_services(
    db: Database,
    session: SessionManager,
    telegram: TelegramService,
    sched: SchedulerService,
) -> None:
    """Закрыть все сервисы"""
    await sched.stop()
    await session.close()
    db.close()
    logger.info("All services closed")


async def main_with_retry():
    """Запуск с обработкой flood control"""
    max_retries = 3
    retry_delay = 60  # секунд

    db = None
    session = None
    telegram = None
    sched = None
    app = None

    for attempt in range(max_retries):
        try:
            # Инициализировать сервисы
            db, repository, session, telegram, sched = await initialize_services()

            # Обновить глобальные переменные
            global scheduler, admin_panel
            scheduler = sched
            admin_panel = AdminPanelService(repository)

            # Создать Telegram приложение
            app = Application.builder().token(get_config().telegram_bot_token).build()

            # Добавить обработчики команд
            app.add_handler(CommandHandler("start", start_command))
            app.add_handler(CommandHandler("status", status_command))
            app.add_handler(CommandHandler("run_now", run_now_command))
            app.add_handler(CommandHandler("stats", stats_command))
            app.add_handler(CommandHandler("help", help_command))
            app.add_handler(CommandHandler("admin", admin_command))
            app.add_handler(CommandHandler("add_admin", add_admin_command))

            # Добавить обработчик inline кнопок
            app.add_handler(CallbackQueryHandler(handle_callback))

            # Добавить обработчики админ-панели
            for handler in admin_panel.get_handlers():
                app.add_handler(handler)

            # Запустить планировщик
            sched.start()

            # Если нужно, запустить парсер сразу
            config = get_config()
            if config.run_on_start:
                logger.info("Running parser on start...")
                try:
                    await sched.run_immediately()
                except Exception as e:
                    logger.error(f"Error running parser on start: {e}")

            # Запустить бота через updater напрямую
            logger.info("Starting Telegram bot...")
            try:
                await app.initialize()
                logger.info("App initialized")
                await app.start()
                logger.info("App started")
                await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
                logger.info("Polling started")
            except Exception as e:
                logger.error(f"Failed to start bot: {e}", exc_info=True)
                raise

            # Держать бота запущенным
            logger.info("Bot is running, waiting for messages...")
            while True:
                await asyncio.sleep(1)

        except Exception as e:
            error_str = str(e)
            if "Flood control" in error_str:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Flood control hit. Retrying in {retry_delay}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    # Закрыть сервисы перед retry
                    if app:
                        try:
                            await app.stop()
                            await app.shutdown()
                        except Exception:
                            pass
                    if sched or telegram or session or db:
                        await shutdown_services(db, session, telegram, sched)
                    await asyncio.sleep(retry_delay)
                else:
                    logger.critical(
                        f"Flood control exceeded after {max_retries} attempts. "
                        f"Wait 10 minutes before restarting."
                    )
                    raise
            else:
                logger.critical(f"Fatal error: {e}", exc_info=True)
                raise
        finally:
            # Закрыть сервисы после каждой попытки
            if app:
                try:
                    await app.stop()
                    await app.shutdown()
                except Exception:
                    pass
            if sched or telegram or session or db:
                try:
                    await shutdown_services(db, session, telegram, sched)
                except Exception:
                    pass  # Игнорировать ошибки при shutdown


if __name__ == "__main__":
    try:
        asyncio.run(main_with_retry())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        exit(1)
