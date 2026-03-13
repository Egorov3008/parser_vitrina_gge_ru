"""
Админ-панель для управления настройками парсера
"""

from datetime import datetime
from typing import List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes, MessageHandler, filters

from src.config import get_config
from src.db.repository import ParserSettings, Repository
from src.utils.logger import get_logger

logger = get_logger()

# Callback данные для кнопок
CALLBACK_CATEGORIES = "admin_categories"
CALLBACK_REGIONS = "admin_regions"
CALLBACK_EXPERTISE_YEAR = "admin_expertise_year"
CALLBACK_EXPERTISE_YEAR_FROM = "admin_expertise_year_from"
CALLBACK_EXPERTISE_YEAR_TO = "admin_expertise_year_to"
CALLBACK_SCHEDULE = "admin_schedule"
CALLBACK_BACK = "admin_back"
CALLBACK_EXIT = "admin_exit"
CALLBACK_SAVE = "admin_save"
CALLBACK_ADD_ADMIN = "admin_add"
CALLBACK_REMOVE_ADMIN = "admin_remove"
CALLBACK_ADMINS = "admin_list"
CALLBACK_PREV_PAGE = "admin_prev"
CALLBACK_NEXT_PAGE = "admin_next"

ITEMS_PER_PAGE = 5


class AdminPanelService:
    """Сервис админ-панели"""

    # Доступные категории (полный список с vitrina.gge.ru)
    ALL_CATEGORIES = [
        "Жилые объекты для постоянного проживания",
        "Жилые объекты специализированного назначения",
        "Среда населенных пунктов (кроме жилых объектов)",
        "Образование",
        "Наука, культура, религия",
        "Здравоохранение",
        "Спорт, отдых",
        "Автомобильный транспорт",
        "Железнодорожный транспорт",
        "Транспорт (кроме автомобильного, железнодорожного)",
        "Энергетика",
        "Сельское хозяйство",
        "Пищевая промышленность",
        "Лесная и деревообрабатывающая промышленность",
        "Химическая промышленность (кроме нефтепереработки, нефтехимии)",
        "Нефтеперерабатывающая и нефтехимическая промышленность",
        "Добыча и транспортировка природного газа",
        "Добыча и транспортировка сырой нефти",
        "Добывающая промышленность (кроме нефти и газа)",
        "Промышленность строительных материалов",
        "Металлургия",
        "Производство машин и оборудования",
        "Производство готовых изделий",
        "Инженерные сети",
        "Гидротехнические и защитные сооружения",
    ]

    # Регионы
    ALL_REGIONS = [
        "Москва",
        "Московская область",
        "Санкт-Петербург",
        "Ленинградская область",
        "Новосибирская область",
        "Свердловская область",
        "Краснодарский край",
        "Республика Татарстан",
        "Нижегородская область",
        "Челябинская область",
        "Самарская область",
        "Омская область",
        "Ростовская область",
        "Уфа",
        "Пермский край",
        "Воронежская область",
        "Волгоградская область",
        "Красноярский край",
        "Саратовская область",
        "Тюменская область",
        "Приморский край",
        "Иркутская область",
        "Хабаровский край",
        "Оренбургская область",
        "Кемеровская область",
    ]

    def __init__(self, repo: Repository):
        self.repo = repo
        self.config = get_config()

    def _check_admin(self, user_id: int) -> bool:
        """Проверить права администратора (БД + конфиг)"""
        user_id_str = str(user_id)

        # Проверка через БД
        if self.repo.is_admin(user_id_str):
            return True

        # Проверка через конфиг (ADMIN_ID)
        admin_ids = self.config.get_admin_ids()
        return user_id_str in admin_ids

    async def show_admin_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать главное меню админ-панели"""
        user_id = update.effective_user.id

        if not self._check_admin(user_id):
            await update.message.reply_text(
                "❌ У вас нет прав администратора.\n\n"
                "Обратитесь к текущему администратору для добавления."
            )
            return

        settings = self.repo.get_all_settings()

        # Формируем сообщение со статусом
        categories_count = len(settings.filter_categories)
        regions_count = len(settings.filter_regions)
        year_from = settings.expertise_year_from or "—"
        year_to = settings.expertise_year_to or "—"
        year_range = f"{year_from} - {year_to}" if year_from != "—" or year_to != "—" else "все"

        text = (
            "⚙️ <b>Админ-панель парсера</b>\n\n"
            "📊 <b>Текущие настройки:</b>\n"
            f"• Категории: {categories_count} выбр.\n"
            f"• Регионы: {regions_count} выбр.\n"
            f"• Год экспертизы: {year_range}\n"
            f"• Расписание: {settings.cron_schedule}\n\n"
            "Выберите действие:"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "📁 Категории", callback_data=CALLBACK_CATEGORIES
                ),
                InlineKeyboardButton("📍 Регионы", callback_data=CALLBACK_REGIONS),
            ],
            [
                InlineKeyboardButton("📅 Год экспертизы", callback_data=CALLBACK_EXPERTISE_YEAR),
                InlineKeyboardButton("⏰ Расписание", callback_data=CALLBACK_SCHEDULE),
            ],
            [
                InlineKeyboardButton("👥 Админы", callback_data=CALLBACK_ADMINS),
            ],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка callback запросов от кнопок"""
        query = update.callback_query
        user_id = query.from_user.id

        if not self._check_admin(user_id):
            await query.answer("❌ Нет прав доступа", show_alert=True)
            return

        await query.answer()

        data = query.data

        if data == CALLBACK_CATEGORIES:
            await self._show_categories_menu(query)
        elif data == CALLBACK_REGIONS:
            await self._show_regions_menu(query)
        elif data == CALLBACK_EXPERTISE_YEAR:
            await self._show_expertise_year_menu(query)
        elif data == CALLBACK_EXPERTISE_YEAR_FROM:
            await self._show_year_selector(query, "from")
        elif data == CALLBACK_EXPERTISE_YEAR_TO:
            await self._show_year_selector(query, "to")
        elif data.startswith("expertise_year_set:"):
            parts = data.split(":")
            year_type = parts[1]  # "from" or "to"
            year = int(parts[2])
            await self._set_expertise_year(query, year_type, year)
        elif data == "expertise_year_reset":
            await self._reset_expertise_year(query)
        elif data == CALLBACK_SCHEDULE:
            await self._show_schedule_menu(query, context)
        elif data == CALLBACK_ADMINS:
            await self._show_admins_menu(query)
        elif data.startswith(f"{CALLBACK_ADD_ADMIN}:"):
            await self._add_admin(query, data.split(":")[1])
        elif data.startswith(f"{CALLBACK_REMOVE_ADMIN}:"):
            await self._remove_admin(query, data.split(":")[1])
        elif data == CALLBACK_BACK:
            await self._show_back_menu(query, context)
        elif data == CALLBACK_EXIT:
            await self._exit_panel(query)
        elif data == CALLBACK_SAVE:
            await self._save_settings(query)
        elif data.startswith("cat:"):
            cat_index = int(data[4:])
            await self._handle_category_toggle(query, cat_index)
        elif data.startswith("reg:"):
            region_index = int(data[4:])
            await self._handle_region_toggle(query, region_index)
        elif data.startswith("days:"):
            days = int(data[5:])
            await self._handle_days_back_set(query, days)
        elif data.startswith("catpage:"):
            page = int(data[8:])
            await self._show_categories_menu(query, page)
        elif data.startswith("regpage:"):
            page = int(data[8:])
            await self._show_regions_menu(query, page)

    async def _show_categories_menu(self, query, page: int = 0):
        """Меню выбора категорий с пагинацией"""
        settings = self.repo.get_all_settings()
        selected = set(settings.filter_categories)

        text = (
            "📁 <b>Категории проектов</b>\n\n"
            f"Выбрано: {len(selected)} из {len(self.ALL_CATEGORIES)}\n\n"
            "Нажмите на категорию для выбора/снятия:"
        )

        # Пагинация
        total_pages = (len(self.ALL_CATEGORIES) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        start_idx = page * ITEMS_PER_PAGE
        end_idx = min(start_idx + ITEMS_PER_PAGE, len(self.ALL_CATEGORIES))

        # Создаём кнопки с категориями (используем индексы для callback)
        keyboard = []
        for i in range(start_idx, end_idx):
            cat = self.ALL_CATEGORIES[i]
            is_selected = cat in selected
            emoji = "✅" if is_selected else "⬜"
            # Сокращаем название для кнопки
            short_name = cat[:30] + "..." if len(cat) > 30 else cat
            keyboard.append(
                [InlineKeyboardButton(f"{emoji} {short_name}", callback_data=f"cat:{i}")]
            )

        # Кнопки навигации
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("◀️ Назад", callback_data=f"catpage:{page-1}"))
        if end_idx < len(self.ALL_CATEGORIES):
            nav_row.append(InlineKeyboardButton("Вперёд ▶️", callback_data=f"catpage:{page+1}"))

        if nav_row:
            keyboard.append(nav_row)

        keyboard.append([InlineKeyboardButton("❌ Выйти из панели", callback_data=CALLBACK_EXIT)])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")

    async def _handle_category_toggle(self, query, cat_index: int):
        """Переключить категорию по индексу"""
        settings = self.repo.get_all_settings()

        if cat_index < 0 or cat_index >= len(self.ALL_CATEGORIES):
            return

        category = self.ALL_CATEGORIES[cat_index]

        if category in settings.filter_categories:
            settings.filter_categories.remove(category)
        else:
            settings.filter_categories.append(category)

        self.repo.save_settings(settings)
        # Сохраняем текущую страницу
        current_page = cat_index // ITEMS_PER_PAGE
        await self._show_categories_menu(query, current_page)

    async def _show_regions_menu(self, query, page: int = 0):
        """Меню выбора регионов с пагинацией"""
        settings = self.repo.get_all_settings()
        selected = set(settings.filter_regions)

        text = (
            "📍 <b>Регионы</b>\n\n"
            f"Выбрано: {len(selected)}\n\n"
            "Нажмите на регион для выбора/снятия:"
        )

        # Пагинация
        total_pages = (len(self.ALL_REGIONS) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        start_idx = page * ITEMS_PER_PAGE
        end_idx = min(start_idx + ITEMS_PER_PAGE, len(self.ALL_REGIONS))

        # Создаём кнопки с регионами (используем индексы для callback)
        keyboard = []
        for i in range(start_idx, end_idx):
            region = self.ALL_REGIONS[i]
            is_selected = region in selected
            emoji = "✅" if is_selected else "⬜"
            keyboard.append(
                [InlineKeyboardButton(f"{emoji} {region}", callback_data=f"reg:{i}")]
            )

        # Кнопки навигации
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("◀️ Назад", callback_data=f"regpage:{page-1}"))
        if end_idx < len(self.ALL_REGIONS):
            nav_row.append(InlineKeyboardButton("Вперёд ▶️", callback_data=f"regpage:{page+1}"))

        if nav_row:
            keyboard.append(nav_row)

        keyboard.append([InlineKeyboardButton("❌ Выйти из панели", callback_data=CALLBACK_EXIT)])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")

    async def _handle_region_toggle(self, query, region_index: int):
        """Переключить регион по индексу"""
        settings = self.repo.get_all_settings()

        if region_index < 0 or region_index >= len(self.ALL_REGIONS):
            return

        region = self.ALL_REGIONS[region_index]

        if region in settings.filter_regions:
            settings.filter_regions.remove(region)
        else:
            settings.filter_regions.append(region)

        self.repo.save_settings(settings)
        # Сохраняем текущую страницу
        current_page = region_index // ITEMS_PER_PAGE
        await self._show_regions_menu(query, current_page)

    # ========== Год экспертизы ==========

    async def _show_expertise_year_menu(self, query):
        """Меню выбора года экспертизы"""
        settings = self.repo.get_all_settings()
        year_from = settings.expertise_year_from
        year_to = settings.expertise_year_to
        year_range = f"{year_from} - {year_to}" if year_from and year_to else "все"

        text = (
            "📅 <b>Год экспертизы</b>\n\n"
            f"Текущий диапазон: <b>{year_range}</b>\n\n"
            "Выберите год начала и конца диапазона:\n"
            "Проекты будут отфильтрованы по номеру экспертизы\n"
            "(последние цифры номера = год)"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    f"🔽 От года: {year_from or 'не задан'}",
                    callback_data=CALLBACK_EXPERTISE_YEAR_FROM
                ),
                InlineKeyboardButton(
                    f"🔼 До года: {year_to or 'не задан'}",
                    callback_data=CALLBACK_EXPERTISE_YEAR_TO
                ),
            ],
            [
                InlineKeyboardButton("🔄 Сбросить", callback_data="expertise_year_reset"),
            ],
            [InlineKeyboardButton("◀️ Назад", callback_data=CALLBACK_BACK)],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")

    async def _show_year_selector(self, query, year_type: str):
        """Меню выбора конкретного года"""
        label = "от" if year_type == "from" else "до"
        text = f"📅 Выберите год <b>{label}</b>:\n\n"

        current_year = datetime.now().year
        years = list(range(current_year - 10, current_year + 2))  # 10 лет назад + 2 вперёд

        keyboard = []
        row = []
        for year in reversed(years):  # От новых к старым
            row.append(InlineKeyboardButton(str(year), callback_data=f"expertise_year_set:{year_type}:{year}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=CALLBACK_EXPERTISE_YEAR)])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")

    async def _set_expertise_year(self, query, year_type: str, year: int):
        """Установить год экспертизы"""
        settings = self.repo.get_all_settings()

        if year_type == "from":
            settings.expertise_year_from = year
        else:
            settings.expertise_year_to = year

        self.repo.save_settings(settings)
        await self._show_expertise_year_menu(query)

    async def _reset_expertise_year(self, query):
        """Сбросить фильтр по году экспертизы"""
        settings = self.repo.get_all_settings()
        settings.expertise_year_from = None
        settings.expertise_year_to = None
        self.repo.save_settings(settings)
        await query.edit_message_text(
            "✅ Фильтр по году экспертизы сброшен\n\n"
            "Будут показаны все проекты независимо от года.\n\n"
            "Нажмите ◀️ Назад для продолжения.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("◀️ Назад", callback_data=CALLBACK_BACK)]]
            ),
            parse_mode="HTML",
        )

    async def _show_schedule_menu(self, query, context):
        """Меню расписания"""
        settings = self.repo.get_all_settings()

        text = (
            "⏰ <b>Расписание запуска (cron)</b>\n\n"
            f"Текущее: <code>{settings.cron_schedule}</code>\n\n"
            "Формат: минута час день месяц день_недели\n"
            "Примеры:\n"
            "• <code>0 6 * * *</code> - ежедневно в 6:00 UTC\n"
            "• <code>0 9 * * 1-5</code> - в 9:00 по будням\n"
            "• <code>0 */4 * * *</code> - каждые 4 часа\n\n"
            "Отправьте новое расписание сообщением:"
        )

        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=CALLBACK_BACK)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
        context.user_data["waiting_schedule"] = True

    async def _show_admins_menu(self, query):
        """Меню администраторов"""
        admins = self.repo.get_admins()

        text = "👥 <b>Администраторы</b>\n\n"

        if admins:
            for admin in admins:
                username = admin.username or f"ID: {admin.telegram_id}"
                text += f"• @{username} (<code>{admin.telegram_id}</code>)\n"
        else:
            text += "Нет администраторов\n"

        text += "\nДля добавления отправьте Telegram ID пользователя."

        keyboard = [
            [InlineKeyboardButton("◀️ Назад", callback_data=CALLBACK_BACK)],
        ]

        if admins:
            for admin in admins:
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            f"❌ {admin.username or admin.telegram_id}",
                            callback_data=f"{CALLBACK_REMOVE_ADMIN}:{admin.telegram_id}",
                        )
                    ]
                )

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")

    async def _add_admin(self, query, telegram_id: str):
        """Добавить администратора"""
        self.repo.add_admin(telegram_id)
        await query.answer(f"✅ Администратор {telegram_id} добавлен", show_alert=True)
        await self._show_admins_menu(query)

    async def _remove_admin(self, query, telegram_id: str):
        """Удалить администратора"""
        if telegram_id == str(query.from_user.id):
            await query.answer("❌ Нельзя удалить себя", show_alert=True)
            return

        self.repo.remove_admin(telegram_id)
        await query.answer(f"✅ Администратор {telegram_id} удалён", show_alert=True)
        await self._show_admins_menu(query)

    async def _show_back_menu(self, query, context):
        """Вернуться в главное меню"""
        # Очищаем состояние ожидания
        if "waiting_schedule" in context.user_data:
            del context.user_data["waiting_schedule"]

        await self.show_admin_menu_from_query(query)

    async def _exit_panel(self, query):
        """Выйти из админ-панели"""
        await query.edit_message_text(
            "✅ Выход из админ-панели\n\n"
            "Используйте /admin для возврата или /help для справки.",
            reply_markup=None,
            parse_mode="HTML",
        )

    async def show_admin_menu_from_query(self, query):
        """Показать меню админ-панели из callback query"""
        settings = self.repo.get_all_settings()

        categories_count = len(settings.filter_categories)
        regions_count = len(settings.filter_regions)
        year_from = settings.expertise_year_from or "—"
        year_to = settings.expertise_year_to or "—"
        year_range = f"{year_from} - {year_to}" if year_from != "—" or year_to != "—" else "все"

        text = (
            "⚙️ <b>Админ-панель парсера</b>\n\n"
            "📊 <b>Текущие настройки:</b>\n"
            f"• Категории: {categories_count} выбр.\n"
            f"• Регионы: {regions_count} выбр.\n"
            f"• Год экспертизы: {year_range}\n"
            f"• Расписание: {settings.cron_schedule}\n\n"
            "Выберите действие:"
        )

        keyboard = [
            [
                InlineKeyboardButton("📁 Категории", callback_data=CALLBACK_CATEGORIES),
                InlineKeyboardButton("📍 Регионы", callback_data=CALLBACK_REGIONS),
            ],
            [
                InlineKeyboardButton("📅 Год экспертизы", callback_data=CALLBACK_EXPERTISE_YEAR),
                InlineKeyboardButton("⏰ Расписание", callback_data=CALLBACK_SCHEDULE),
            ],
            [
                InlineKeyboardButton("👥 Админы", callback_data=CALLBACK_ADMINS),
            ],
            [
                InlineKeyboardButton("❌ Выйти из панели", callback_data=CALLBACK_EXIT),
            ],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")

    async def _save_settings(self, query):
        """Сохранить настройки"""
        # Настройки сохраняются автоматически при изменении
        await query.answer("✅ Настройки сохранены", show_alert=True)

    async def handle_schedule_input(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Обработка ввода расписания"""
        user_id = update.effective_user.id

        if not self._check_admin(user_id):
            return

        # Проверяем, ждём ли мы ввод расписания
        if not context.user_data.get("waiting_schedule"):
            return

        if update.message is None:
            return

        new_schedule = update.message.text.strip()

        # Простая валидация cron (5 полей)
        parts = new_schedule.split()
        if len(parts) != 5:
            await update.message.reply_text(
                "❌ Неверный формат cron. Должно быть 5 полей.\n"
                "Пример: <code>0 6 * * *</code>",
                parse_mode="HTML",
            )
            return

        settings = self.repo.get_all_settings()
        settings.cron_schedule = new_schedule
        self.repo.save_settings(settings)

        del context.user_data["waiting_schedule"]

        await update.message.reply_text(
            f"✅ Расписание обновлено: <code>{new_schedule}</code>",
            parse_mode="HTML",
        )

    def get_handlers(self):
        """Получить обработчики callback запросов"""
        return [
            CallbackQueryHandler(self.handle_callback),
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_schedule_input),
        ]
