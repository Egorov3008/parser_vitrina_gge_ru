"""
Парсер витрины проектов vitrina.gge.ru

Основной модуль, запускающий бот и планировщик.
"""

import asyncio
import signal
from typing import Optional

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from src.browser.session import SessionManager
from src.config import get_config
from src.db.database import Database
from src.db.repository import Repository
from src.services.admin_panel import AdminPanelService
from src.services.scheduler import SchedulerService
from src.services.telegram import TelegramService
from src.utils.logger import get_logger, setup_logger

logger = get_logger()

# Глобальные переменные для scheduler и admin_panel
scheduler: Optional[SchedulerService] = None
admin_panel: Optional[AdminPanelService] = None


# ============== Команды ==============

async def start_command(message: Message) -> None:
    """Команда /start - приветствие"""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    user_id = message.from_user.id
    logger.info(f"User {user_id} executed /start command")

    text = (
        "👋 <b>Добро пожаловать в парсер витрины проектов!</b>\n\n"
        "🔧 <b>Основные команды:</b>\n"
        "/status - статус последнего запуска\n"
        "/run_now - запустить парсер сейчас\n"
        "/stats - статистика проектов\n"
        "/admin - панель настроек (администраторам)\n"
        "/getChatId - получить ID текущего чата\n\n"
        "⚙️ <b>Администраторам:</b>\n"
        "Используйте /admin или кнопку ниже для настройки:\n"
        "• 📁 Категории проектов\n"
        "• 📍 Регионы\n"
        "• 📅 Период фильтрации\n"
        "• ⏰ Расписание запуска\n"
        "• 📱 Чаты для уведомлений\n"
        "• 👥 Администраторы\n\n"
        "📚 <b>Документация:</b>\n"
        "ADMIN_PANEL.md - руководство по админ-панели"
    )

    keyboard = [
        [
            InlineKeyboardButton(text="📊 Статус", callback_data="cmd_status"),
            InlineKeyboardButton(text="🚀 Запустить", callback_data="cmd_run_now"),
        ],
        [
            InlineKeyboardButton(text="📈 Статистика", callback_data="cmd_stats"),
            InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="cmd_admin"),
        ],
        [
            InlineKeyboardButton(text="❓ Справка", callback_data="cmd_help"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    

    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


async def status_command(message: Message) -> None:
    """Команда /status - информация о последнем запуске"""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    user_id = message.from_user.id
    logger.info(f"User {user_id} executed /status command")

    if not scheduler:
        text = "❌ Планировщик не инициализирован"
        await message.reply_text(text)
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

    keyboard = [[InlineKeyboardButton(text="🚀 Запустить сейчас", callback_data="cmd_run_now")]]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


async def run_now_command(message: Message) -> None:
    """Команда /run_now - запустить парсер немедленно"""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    user_id = message.from_user.id
    logger.info(f"User {user_id} executed /run_now command")

    if not scheduler:
        text = "❌ Планировщик не инициализирован"
        await message.reply_text(text)
        return

    # Отправляем сообщение о запуске
    text = "⏳ <b>Запуск парсера...</b>"
    keyboard = [[InlineKeyboardButton(text="📊 Статус", callback_data="cmd_status")]]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    msg = await message.answer(text, reply_markup=reply_markup)

    # Запускаем парсер
    try:
        await scheduler.run_immediately()
        text = "✅ <b>Парсер завершил работу!</b>\n\n"
        text += "Используйте /status для просмотра результатов."
        keyboard = [[InlineKeyboardButton(text="📊 Статус", callback_data="cmd_status")]]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await msg.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except Exception as e:
        text = f"❌ <b>Ошибка при запуске:</b>\n<code>{str(e)[:200]}</code>"
        keyboard = [[InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="cmd_run_now")]]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await msg.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")


async def stats_command(message: Message) -> None:
    """Команда /stats - статистика проектов"""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    user_id = message.from_user.id
    logger.info(f"User {user_id} executed /stats command")

    if not scheduler:
        text = "❌ Планировщик не инициализирован"
        await message.reply_text(text)
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
        [InlineKeyboardButton(text="🚀 Запустить парсер", callback_data="cmd_run_now")],
        [InlineKeyboardButton(text="📊 Статус", callback_data="cmd_status")],
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


async def help_command(message: Message) -> None:
    """Команда /help - справка"""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    user_id = message.from_user.id
    logger.info(f"User {user_id} executed /help command")

    text = (
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
        "<b>/getChatId</b>\n"
        "Получить ID текущего чата для добавления в уведомления\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚙️ <b>Админ-панель:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>/admin</b>\n"
        "Открыть панель управления настройками:\n"
        "• 📁 Категории проектов\n"
        "• 📍 Регионы\n"
        "• 📅 Период фильтрации\n"
        "• ⏰ Расписание (cron)\n"
        "• 📱 Управление чатами для уведомлений\n"
        "• 👥 Управление администраторами\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "ℹ️ <b>Информация:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Парсер автоматически проверяет новые проекты\n"
        "по расписанию и отправляет уведомления в настроенные чаты.\n\n"
        "Для доступа к админ-панели добавьте свой Telegram ID\n"
        "в переменную ADMIN_ID файла .env и перезапустите бота."
    )

    keyboard = [
        [
            InlineKeyboardButton(text="📊 Статус", callback_data="cmd_status"),
            InlineKeyboardButton(text="🚀 Запустить", callback_data="cmd_run_now"),
        ],
        [
            InlineKeyboardButton(text="📈 Статистика", callback_data="cmd_stats"),
            InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="cmd_admin"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


async def admin_command(message: Message, state: FSMContext) -> None:
    """Команда /admin - панель администратора"""
    global admin_panel
    if not admin_panel:
        text = "❌ Админ-панель не инициализирована"
        await message.reply_text(text)
        return

    user_id = message.from_user.id
    logger.info(f"User {user_id} executed /admin command")

    # Проверка прав
    if not admin_panel._check_admin(user_id):
        logger.warning(f"User {user_id} denied access to admin panel (not in admin list)")
        user_id_str = str(user_id)
        text = (
            "❌ <b>Доступ запрещён</b>\n\n"
            f"Ваш Telegram ID: <code>{user_id_str}</code>\n\n"
            "Для доступа к админ-панели:\n"
            "1. Откройте файл .env\n"
            "2. Добавьте ваш ID в ADMIN_ID:\n"
            f"<code>ADMIN_ID={user_id_str}</code>\n"
            "3. Перезапустите парсер\n\n"
            "Или попросите текущего администратора\n"
            "добавить вас через /add_admin"
        )
        await message.answer(text, parse_mode=ParseMode.HTML)
        return

    await admin_panel.show_admin_menu(message, state)


async def add_admin_command(message: Message) -> None:
    """Команда /add_admin - добавить администратора"""
    if message.from_user is None:
        return

    user_id = str(message.from_user.id)
    username = message.from_user.username
    logger.info(f"User {user_id} executed /add_admin command")

    # Проверка: только админ может добавлять других
    repo = Repository(Database(get_config().db_path))
    if not repo.is_admin(user_id):
        logger.warning(f"User {user_id} denied access to /add_admin (not admin)")
        await message.answer(
            "❌ Только администратор может добавлять других.\n\n"
            f"Ваш ID: <code>{user_id}</code>\n"
            "Добавьте себя в ADMIN_ID в .env файле.",
            parse_mode=ParseMode.HTML
        )
        return

    args = message.text.split()[1:] if message.text else []
    if not args:
        await message.answer(
            "Использование: /add_admin &lt;telegram_id&gt; [telegram_id2, ...]\n\n"
            f"Ваш ID: <code>{user_id}</code>\n\n"
            "Можно добавить несколько ID через запятую.",
            parse_mode=ParseMode.HTML
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
                logger.info(f"Admin {user_id} added new admin: {tid}")

    await message.reply_text(
        f"✅ Добавлены администраторы:\n" + "\n".join(f"• {tid}" for tid in added)
    )


async def get_chat_id_command(message: Message) -> None:
    """Команда /getChatId - получить ID текущего чата"""
    if message.chat is None:
        return

    user_id = message.from_user.id if message.from_user else "unknown"
    logger.info(f"User {user_id} executed /getChatId command")

    chat = message.chat
    chat_id = chat.id
    chat_type = chat.type

    text = (
        f"📱 <b>ID вашего чата:</b>\n\n"
        f"<code>{chat_id}</code>\n\n"
        f"<b>Тип:</b> {chat_type}\n"
    )

    if chat.title:
        text += f"<b>Название:</b> {chat.title}\n"
    if chat.username:
        text += f"<b>Username:</b> @{chat.username}\n"

    text += (
        "\n<b>Как добавить этот чат в уведомления:</b>\n"
        "1. Откройте админ-панель (/admin)\n"
        "2. Нажмите на 📱 Чаты\n"
        "3. Отправьте ID сообщением\n\n"
        "✅ Чат будет добавлен и будет получать уведомления!"
    )

    await message.answer(text)


# ============== Callback Handlers ==============

async def handle_top_level_callbacks(message: Message = None, bot: Bot = None, callback_data: str = None) -> None:
    """Обработка топ-уровневых callback запросов"""
    pass  # Будет обработано через Router


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


async def main():
    """Запуск бота"""
    db = None
    session = None
    telegram = None
    sched = None
    bot = None
    dp = None

    try:
        # Инициализировать сервисы
        db, repository, session, telegram, sched = await initialize_services()

        # Обновить глобальные переменные
        global scheduler, admin_panel
        scheduler = sched
        admin_panel = AdminPanelService(repository)

        # Создать Bot и Dispatcher
        config = get_config()
        bot = Bot(
            token=config.telegram_bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        dp = Dispatcher(storage=MemoryStorage())

        # Инъекция зависимостей в workflow_data
        dp["scheduler"] = scheduler
        dp["admin_panel"] = admin_panel
        dp["repo"] = repository

        # Главный router для команд и callbacks
        router = Router()

        # Регистрация обработчиков команд
        @router.message(Command("start"))
        async def cmd_start(msg: Message):
            await start_command(msg)

        @router.message(Command("status"))
        async def cmd_status(msg: Message):
            await status_command(msg)

        @router.message(Command("run_now"))
        async def cmd_run_now(msg: Message):
            await run_now_command(msg)

        @router.message(Command("stats"))
        async def cmd_stats(msg: Message):
            await stats_command(msg)

        @router.message(Command("help"))
        async def cmd_help(msg: Message):
            await help_command(msg)

        @router.message(Command("admin"))
        async def cmd_admin(msg: Message, state: FSMContext):
            await admin_command(msg, state)

        @router.message(Command("add_admin"))
        async def cmd_add_admin(msg: Message):
            await add_admin_command(msg)

        @router.message(Command("getChatId"))
        async def cmd_get_chat_id(msg: Message):
            await get_chat_id_command(msg)

        # Callback handlers для топ-уровневых кнопок
        @router.callback_query(F.data == "cmd_status")
        async def cb_status(callback: CallbackQuery):
            user_id = callback.from_user.id
            logger.info(f"User {user_id} clicked cmd_status button")
            await status_command(callback.message)
            await callback.answer()

        @router.callback_query(F.data == "cmd_run_now")
        async def cb_run_now(callback: CallbackQuery):
            user_id = callback.from_user.id
            logger.info(f"User {user_id} clicked cmd_run_now button")
            await run_now_command(callback.message)
            await callback.answer()

        @router.callback_query(F.data == "cmd_stats")
        async def cb_stats(callback: CallbackQuery):
            user_id = callback.from_user.id
            logger.info(f"User {user_id} clicked cmd_stats button")
            await stats_command(callback.message)
            await callback.answer()

        @router.callback_query(F.data == "cmd_help")
        async def cb_help(callback: CallbackQuery):
            user_id = callback.from_user.id
            logger.info(f"User {user_id} clicked cmd_help button")
            await help_command(callback.message)
            await callback.answer()

        @router.callback_query(F.data == "cmd_admin")
        async def cb_admin(callback: CallbackQuery, state: FSMContext):
            user_id = callback.from_user.id
            logger.info(f"User {user_id} clicked cmd_admin button")

            # Check admin rights
            if not admin_panel._check_admin(user_id):
                logger.warning(f"User {user_id} denied access to admin panel (not in admin list)")
                user_id_str = str(user_id)
                text = (
                    "❌ <b>Доступ запрещён</b>\n\n"
                    f"Ваш Telegram ID: <code>{user_id_str}</code>\n\n"
                    "Для доступа к админ-панели:\n"
                    "1. Откройте файл .env\n"
                    "2. Добавьте ваш ID в ADMIN_ID:\n"
                    f"<code>ADMIN_ID={user_id_str}</code>\n"
                    "3. Перезапустите парсер\n\n"
                    "Или попросите текущего администратора\n"
                    "добавить вас через /add_admin"
                )
                await callback.message.edit_text(text, parse_mode=ParseMode.HTML)
            else:
                # Show admin panel menu
                await admin_panel.show_admin_menu(callback.message, state)

            await callback.answer()

        # Добавить routers
        dp.include_router(router)
        dp.include_router(admin_panel.router)

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

        # Запустить бота
        logger.info("Starting Telegram bot...")
        try:
            await dp.start_polling(bot)
        except Exception as e:
            logger.error(f"Failed to start bot: {e}", exc_info=True)
            raise

    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Interrupted by user (Ctrl+C)")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        raise
    finally:
        # Закрыть все сервисы при выходе
        if bot:
            try:
                await bot.session.close()
            except Exception:
                pass
        if sched and telegram and session and db:
            try:
                await shutdown_services(db, session, telegram, sched)
            except Exception:
                pass  # Игнорировать ошибки при shutdown


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Bot gracefully stopped")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        exit(1)
