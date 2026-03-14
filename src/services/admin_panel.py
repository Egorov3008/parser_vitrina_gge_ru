"""
Админ-панель для управления настройками парсера
"""

import json
from datetime import datetime

from aiogram import Router, F
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter

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
CALLBACK_NOTIFICATION_CHATS = "admin_chats"
CALLBACK_ADD_CHAT = "admin_add_chat"
CALLBACK_REMOVE_CHAT = "admin_remove_chat"
CALLBACK_CLEAR_DATA = "admin_clear_data"
CALLBACK_CLEAR_DATA_CONFIRM = "admin_clear_data_confirm"
CALLBACK_EXPORT = "admin_export"
CALLBACK_CATEGORIES_RESET = "cat_reset"
CALLBACK_REGIONS_RESET = "reg_reset"

ITEMS_PER_PAGE = 5


class AdminFSM(StatesGroup):
    """FSM состояния для админ-панели"""
    waiting_schedule = State()   # ожидание cron-выражения
    waiting_chat_id = State()    # ожидание chat ID


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

    # Регионы (полный список из 85 федеральных субъектов РФ)
    ALL_REGIONS = [
        "01. Республика Адыгея",
        "02. Республика Башкортостан",
        "03. Республика Бурятия",
        "04. Республика Алтай",
        "05. Республика Дагестан",
        "06. Республика Ингушетия",
        "07. Кабардино-Балкарская Республика",
        "08. Республика Калмыкия",
        "09. Карачаево-Черкесская Республика",
        "10. Республика Карелия",
        "11. Республика Коми",
        "12. Республика Марий Эл",
        "13. Республика Мордовия",
        "14. Республика Саха (Якутия)",
        "15. Республика Северная Осетия — Алания",
        "16. Республика Татарстан",
        "17. Республика Тыва",
        "18. Удмуртская Республика",
        "19. Республика Хакасия",
        "20. Чеченская Республика",
        "21. Чувашская Республика",
        "22. Алтайский край",
        "23. Краснодарский край",
        "24. Красноярский край",
        "25. Приморский край",
        "26. Ставропольский край",
        "27. Хабаровский край",
        "29. Амурская область",
        "30. Архангельская область",
        "31. Астраханская область",
        "32. Белгородская область",
        "33. Брянская область",
        "34. Владимирская область",
        "35. Волгоградская область",
        "36. Вологодская область",
        "37. Воронежская область",
        "38. Ивановская область",
        "39. Иркутская область",
        "40. Калининградская область",
        "41. Калужская область",
        "42. Камчатский край",
        "43. Кемеровская область",
        "44. Кировская область",
        "45. Костромская область",
        "46. Курганская область",
        "47. Курская область",
        "48. Ленинградская область",
        "49. Липецкая область",
        "50. Магаданская область",
        "51. Московская область",
        "52. Мурманская область",
        "53. Нижегородская область",
        "54. Новгородская область",
        "55. Новосибирская область",
        "56. Омская область",
        "57. Оренбургская область",
        "58. Орловская область",
        "59. Пензенская область",
        "60. Пермский край",
        "61. Приморский край",
        "62. Псковская область",
        "63. Ростовская область",
        "64. Рязанская область",
        "65. Самарская область",
        "66. Саратовская область",
        "67. Смоленская область",
        "68. Свердловская область",
        "69. Тамбовская область",
        "70. Тверская область",
        "71. Томская область",
        "72. Тульская область",
        "73. Тюменская область",
        "74. Тюменская область (ХМАО)",
        "75. Тюменская область (ЯНАО)",
        "76. Ульяновская область",
        "77. г. Москва",
        "78. г. Санкт-Петербург",
        "79. Еврейская автономная область",
        "80. Чукотский автономный округ",
        "81. Республика Крым",
        "82. г. Севастополь",
        "83. Сахалинская область",
        "84. Заморские регионы",
        "85. Забайкальский край",
    ]

    def __init__(self, repo: Repository):
        self.repo = repo
        self.config = get_config()
        self.router = Router()
        self._register_handlers()

    def _register_handlers(self):
        """Регистрация обработчиков aiogram"""
        # Callback handlers
        self.router.callback_query.register(self.handle_callback)

        # FSM handlers для ввода текста
        self.router.message.register(
            self._handle_schedule_text,
            AdminFSM.waiting_schedule
        )
        self.router.message.register(
            self._handle_chat_id_text,
            AdminFSM.waiting_chat_id
        )

    def _check_admin(self, user_id: int) -> bool:
        """Проверить права администратора (БД + конфиг)"""
        user_id_str = str(user_id)

        # Проверка через БД
        if self.repo.is_admin(user_id_str):
            return True

        # Проверка через конфиг (ADMIN_ID)
        admin_ids = self.config.get_admin_ids()
        return user_id_str in admin_ids

    async def show_admin_menu(self, message: Message, state: FSMContext):
        """Показать главное меню админ-панели"""
        # Очищаем состояние при открытии админ-панели
        if state:
            await state.clear()

        user_id = message.from_user.id

        if not self._check_admin(user_id):
            await message.answer(
                "❌ У вас нет прав администратора.\n\n"
                "Обратитесь к текущему администратору для добавления.",
                parse_mode=ParseMode.HTML
            )
            return

        settings = self.repo.get_all_settings()
        text, keyboard = self._build_admin_menu_content(settings)
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await message.answer(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    async def handle_callback(self, callback: CallbackQuery, state: FSMContext):
        """Обработка callback запросов от кнопок"""
        user_id = callback.from_user.id

        if not self._check_admin(user_id):
            logger.warning(f"User {user_id} denied access to admin panel callback")
            await callback.answer("❌ Нет прав доступа", show_alert=True)
            return

        await callback.answer()

        data = callback.data
        logger.info(f"User {user_id} admin callback: {data}")

        if data == CALLBACK_CATEGORIES:
            await self._show_categories_menu(callback)
        elif data == CALLBACK_REGIONS:
            await self._show_regions_menu(callback)
        elif data == CALLBACK_EXPERTISE_YEAR:
            await self._show_expertise_year_menu(callback)
        elif data == CALLBACK_EXPERTISE_YEAR_FROM:
            await self._show_year_selector(callback, "from")
        elif data == CALLBACK_EXPERTISE_YEAR_TO:
            await self._show_year_selector(callback, "to")
        elif data.startswith("expertise_year_set:"):
            parts = data.split(":")
            year_type = parts[1]  # "from" or "to"
            year = int(parts[2])
            await self._set_expertise_year(callback, year_type, year)
        elif data == "expertise_year_reset":
            await self._reset_expertise_year(callback)
        elif data == CALLBACK_SCHEDULE:
            await self._show_schedule_menu(callback, state)
        elif data == CALLBACK_ADMINS:
            await self._show_admins_menu(callback)
        elif data.startswith(f"{CALLBACK_ADD_ADMIN}:"):
            await self._add_admin(callback, data.split(":")[1])
        elif data.startswith(f"{CALLBACK_REMOVE_ADMIN}:"):
            await self._remove_admin(callback, data.split(":")[1])
        elif data == CALLBACK_NOTIFICATION_CHATS:
            await self._show_chats_menu(callback, state)
        elif data.startswith(f"{CALLBACK_REMOVE_CHAT}:"):
            await self._remove_chat(callback, state, data.split(":")[1])
        elif data == CALLBACK_BACK:
            await self._show_back_menu(callback, state)
        elif data == CALLBACK_EXIT:
            await self._exit_panel(callback, state)
        elif data == CALLBACK_SAVE:
            await self._save_settings(callback)
        elif data.startswith("cat:"):
            cat_index = int(data[4:])
            await self._handle_category_toggle(callback, cat_index)
        elif data.startswith("reg:"):
            region_index = int(data[4:])
            await self._handle_region_toggle(callback, region_index)
        elif data.startswith("catpage:"):
            page = int(data[8:])
            await self._show_categories_menu(callback, page)
        elif data.startswith("regpage:"):
            page = int(data[8:])
            await self._show_regions_menu(callback, page)
        elif data == CALLBACK_CATEGORIES_RESET:
            await self._reset_categories(callback)
        elif data == CALLBACK_REGIONS_RESET:
            await self._reset_regions(callback)
        elif data == CALLBACK_CLEAR_DATA:
            await self._show_clear_data_confirmation(callback)
        elif data == CALLBACK_CLEAR_DATA_CONFIRM:
            await self._perform_clear_data(callback)
        elif data == CALLBACK_EXPORT:
            await self._perform_export(callback)

    async def _show_categories_menu(self, callback: CallbackQuery, page: int = 0):
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
                [InlineKeyboardButton(text=f"{emoji} {short_name}", callback_data=f"cat:{i}")]
            )

        # Кнопки навигации
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"catpage:{page-1}"))
        if end_idx < len(self.ALL_CATEGORIES):
            nav_row.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"catpage:{page+1}"))

        if nav_row:
            keyboard.append(nav_row)

        keyboard.append([InlineKeyboardButton(text="🔄 Сбросить категории", callback_data=CALLBACK_CATEGORIES_RESET)])
        keyboard.append([InlineKeyboardButton(text="✅ Готово", callback_data=CALLBACK_BACK)])

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    async def _handle_category_toggle(self, callback: CallbackQuery, cat_index: int):
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
        await self._show_categories_menu(callback, current_page)

    async def _show_regions_menu(self, callback: CallbackQuery, page: int = 0):
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
                [InlineKeyboardButton(text=f"{emoji} {region}", callback_data=f"reg:{i}")]
            )

        # Кнопки навигации
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"regpage:{page-1}"))
        if end_idx < len(self.ALL_REGIONS):
            nav_row.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"regpage:{page+1}"))

        if nav_row:
            keyboard.append(nav_row)

        keyboard.append([InlineKeyboardButton(text="🔄 Сбросить регионы", callback_data=CALLBACK_REGIONS_RESET)])
        keyboard.append([InlineKeyboardButton(text="✅ Готово", callback_data=CALLBACK_BACK)])

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    async def _handle_region_toggle(self, callback: CallbackQuery, region_index: int):
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
        await self._show_regions_menu(callback, current_page)

    # ========== Год экспертизы ==========

    async def _show_expertise_year_menu(self, callback: CallbackQuery):
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
                InlineKeyboardButton(text="🔄 Сбросить", callback_data="expertise_year_reset"),
            ],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_BACK)],
        ]

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    async def _show_year_selector(self, callback: CallbackQuery, year_type: str):
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

        keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_EXPERTISE_YEAR)])

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    async def _set_expertise_year(self, callback: CallbackQuery, year_type: str, year: int):
        """Установить год экспертизы"""
        settings = self.repo.get_all_settings()

        if year_type == "from":
            settings.expertise_year_from = year
        else:
            settings.expertise_year_to = year

        self.repo.save_settings(settings)
        await self._show_expertise_year_menu(callback)

    async def _reset_expertise_year(self, callback: CallbackQuery):
        """Сбросить фильтр по году экспертизы"""
        settings = self.repo.get_all_settings()
        settings.expertise_year_from = None
        settings.expertise_year_to = None
        self.repo.save_settings(settings)
        await callback.message.edit_text(
            "✅ Фильтр по году экспертизы сброшен\n\n"
            "Будут показаны все проекты независимо от года.\n\n"
            "Нажмите ◀️ Назад для продолжения.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_BACK)]]
            ),
            parse_mode=ParseMode.HTML,
        )

    async def _reset_categories(self, callback: CallbackQuery):
        """Сбросить фильтр по категориям"""
        settings = self.repo.get_all_settings()
        settings.filter_categories = []
        self.repo.save_settings(settings)
        # Показываем меню категорий с начальной страницы
        await self._show_categories_menu(callback, 0)

    async def _reset_regions(self, callback: CallbackQuery):
        """Сбросить фильтр по регионам"""
        settings = self.repo.get_all_settings()
        settings.filter_regions = []
        self.repo.save_settings(settings)
        # Показываем меню регионов с начальной страницы
        await self._show_regions_menu(callback, 0)

    async def _show_schedule_menu(self, callback: CallbackQuery, state: FSMContext):
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

        keyboard = [[InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_BACK)]]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        await state.set_state(AdminFSM.waiting_schedule)

    async def _show_admins_menu(self, callback: CallbackQuery):
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
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_BACK)],
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

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    async def _add_admin(self, callback: CallbackQuery, telegram_id: str):
        """Добавить администратора"""
        self.repo.add_admin(telegram_id)
        await callback.answer(f"✅ Администратор {telegram_id} добавлен", show_alert=True)
        await self._show_admins_menu(callback)

    async def _remove_admin(self, callback: CallbackQuery, telegram_id: str):
        """Удалить администратора"""
        if telegram_id == str(callback.from_user.id):
            await callback.answer("❌ Нельзя удалить себя", show_alert=True)
            return

        self.repo.remove_admin(telegram_id)
        await callback.answer(f"✅ Администратор {telegram_id} удалён", show_alert=True)
        await self._show_admins_menu(callback)

    async def _show_chats_menu(self, callback: CallbackQuery, state: FSMContext):
        """Меню управления чатами для отправки уведомлений"""
        chats = self.repo.get_all_notification_chats()

        text = "📱 <b>Чаты для отправки уведомлений</b>\n\n"

        if chats:
            for chat in chats:
                status = "✅" if chat.is_active else "❌"
                chat_display = chat.chat_name or f"ID: {chat.chat_id}"
                text += f"{status} {chat_display} (<code>{chat.chat_id}</code>)\n"
        else:
            text += "Нет добавленных чатов\n"

        text += (
            "\n<b>Для добавления нового чата:</b>\n"
            "1. Отправьте /getChatId в нужный чат\n"
            "2. Бот ответит с ID чата\n"
            "3. Отправьте ID сообщением сюда\n\n"
            "<b>Для приватного чата:</b>\n"
            "• Добавьте бота в чат\n"
            "• Отправьте команду\n"
            "• ID будет отправлен в бот (приватный чат)\n\n"
            "<b>Для личного чата:</b>\n"
            "• Просто отправьте /getChatId здесь"
        )

        keyboard = [
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_BACK)],
        ]

        if chats:
            for chat in chats:
                chat_display = chat.chat_name or f"ID: {chat.chat_id}"
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            f"❌ {chat_display}",
                            callback_data=f"{CALLBACK_REMOVE_CHAT}:{chat.chat_id}",
                        )
                    ]
                )

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        await state.set_state(AdminFSM.waiting_chat_id)

    async def _remove_chat(self, callback: CallbackQuery, state: FSMContext, chat_id: str):
        """Удалить чат"""
        self.repo.remove_notification_chat(chat_id)
        await callback.answer(f"✅ Чат {chat_id} удалён", show_alert=True)
        await self._show_chats_menu(callback, state)

    async def _show_back_menu(self, callback: CallbackQuery, state: FSMContext):
        """Вернуться в главное меню"""
        # Очищаем состояние ожидания
        await state.clear()
        await self.show_admin_menu_from_query(callback)

    async def _exit_panel(self, callback: CallbackQuery, state: FSMContext):
        """Выйти из админ-панели (вернуться в главное меню)"""
        # Очищаем состояние ожидания
        await state.clear()

        try:
            # Возвращаемся в главное меню
            await self.show_admin_menu_from_query(callback)
        except Exception as e:
            # Если сообщение не изменилось (уже на главном меню)
            if "Message is not modified" in str(e):
                await callback.answer()
            else:
                logger.error(f"Failed to show admin menu: {e}")
                raise

    def _build_admin_menu_content(self, settings):
        """Построить содержимое главного меню админ-панели"""
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
                InlineKeyboardButton(text="📁 Категории", callback_data=CALLBACK_CATEGORIES),
                InlineKeyboardButton(text="📍 Регионы", callback_data=CALLBACK_REGIONS),
            ],
            [
                InlineKeyboardButton(text="📅 Год экспертизы", callback_data=CALLBACK_EXPERTISE_YEAR),
                InlineKeyboardButton(text="⏰ Расписание", callback_data=CALLBACK_SCHEDULE),
            ],
            [
                InlineKeyboardButton(text="👥 Админы", callback_data=CALLBACK_ADMINS),
                InlineKeyboardButton(text="📱 Чаты", callback_data=CALLBACK_NOTIFICATION_CHATS),
            ],
            [
                InlineKeyboardButton(text="💾 Экспорт в .txt", callback_data=CALLBACK_EXPORT),
                InlineKeyboardButton(text="🗑️ Очистить данные", callback_data=CALLBACK_CLEAR_DATA),
            ],
        ]

        return text, keyboard

    async def show_admin_menu_from_query(self, callback: CallbackQuery):
        """Показать меню админ-панели из callback query"""
        settings = self.repo.get_all_settings()
        text, keyboard = self._build_admin_menu_content(settings)
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    async def _save_settings(self, callback: CallbackQuery):
        """Сохранить настройки"""
        # Настройки сохраняются автоматически при изменении
        await callback.answer("✅ Настройки сохранены", show_alert=True)

    async def _handle_schedule_text(self, message: Message, state: FSMContext):
        """Обработка ввода расписания (FSM)"""
        user_id = message.from_user.id
        logger.info(f"User {user_id} entered schedule text in FSM")

        if not self._check_admin(user_id):
            logger.warning(f"User {user_id} tried to set schedule without admin rights")
            return

        new_schedule = message.text.strip()

        # Простая валидация cron (5 полей)
        parts = new_schedule.split()
        if len(parts) != 5:
            await message.answer(
                "❌ Неверный формат cron. Должно быть 5 полей.\n"
                "Пример: <code>0 6 * * *</code>",
                parse_mode=ParseMode.HTML,
            )
            return

        settings = self.repo.get_all_settings()
        settings.cron_schedule = new_schedule
        self.repo.save_settings(settings)

        await state.clear()

        await message.answer(
            f"✅ Расписание обновлено: <code>{new_schedule}</code>",
            parse_mode=ParseMode.HTML,
        )

    async def _handle_chat_id_text(self, message: Message, state: FSMContext):
        """Обработка ввода ID чата (FSM)"""
        user_id = message.from_user.id
        logger.info(f"User {user_id} entered chat ID text in FSM")

        if not self._check_admin(user_id):
            logger.warning(f"User {user_id} tried to add chat ID without admin rights")
            return

        chat_id_input = message.text.strip()

        # Проверяем, что это число (ID чата)
        try:
            # ID могут быть отрицательными (группы) или положительными (личные чаты)
            int(chat_id_input)
        except ValueError:
            await message.answer(
                "❌ Неверный ID чата. Должно быть число.\n"
                "Пример: <code>123456789</code> или <code>-1001234567890</code>",
                parse_mode=ParseMode.HTML,
            )
            return

        # Добавляем чат
        self.repo.add_notification_chat(chat_id_input)

        await state.clear()

        await message.answer(
            f"✅ Чат {chat_id_input} добавлен для отправки уведомлений",
            parse_mode=ParseMode.HTML,
        )

    async def _show_clear_data_confirmation(self, callback: CallbackQuery):
        """Показать подтверждение очистки данных"""
        stats = self.repo.get_stats()

        text = (
            "⚠️ <b>Внимание! Необратимая операция</b>\n\n"
            "Это удалит ВСЕ сохранённые данные:\n\n"
            f"🗂️ Проектов: {stats.get('total_projects', 0)}\n"
            f"📋 Логов запусков: {len(self.repo.get_recent_errors(limit=1000))}\n\n"
            "Вы <b>не сможете восстановить</b> эти данные!\n\n"
            "Вы уверены, что хотите продолжить?"
        )

        keyboard = [
            [
                InlineKeyboardButton(text="✅ Да, удалить", callback_data=CALLBACK_CLEAR_DATA_CONFIRM),
                InlineKeyboardButton(text="❌ Отмена", callback_data=CALLBACK_BACK),
            ]
        ]

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    async def _perform_clear_data(self, callback: CallbackQuery):
        """Выполнить очистку данных"""
        try:
            result = self.repo.clear_all_data()

            text = (
                "✅ <b>Данные успешно очищены!</b>\n\n"
                f"🗂️ Удалено проектов: {result['projects_deleted']}\n"
                f"📋 Удалено логов: {result['logs_deleted']}\n\n"
                "Парсер готов к новому запуску."
            )

            keyboard = [[InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_BACK)]]
            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

            await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            logger.info(f"Data cleared by admin {callback.from_user.id}: {result['projects_deleted']} projects, {result['logs_deleted']} logs")

        except Exception as e:
            logger.error(f"Error clearing data: {e}")
            await callback.answer(f"❌ Ошибка при очистке: {str(e)}", show_alert=True)

    def _format_projects_to_txt(self, projects: list) -> str:
        """Форматировать проекты в текст для экспорта"""
        if not projects:
            return "Нет проектов для экспорта"

        lines = [
            "=" * 100,
            f"ЭКСПОРТ ДАННЫХ ПРОЕКТОВ - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 100,
            f"Всего проектов: {len(projects)}\n",
        ]

        for idx, project in enumerate(projects, 1):
            lines.append("-" * 100)
            lines.append(f"Проект #{idx}")
            lines.append("-" * 100)

            # Базовые поля
            lines.append(f"ID: {project.get('vitrina_id', 'N/A')}")
            lines.append(f"Номер экспертизы: {project.get('expertise_num', 'N/A')}")
            lines.append(f"Название объекта: {project.get('object_name', 'N/A')}")
            lines.append(f"Организация-эксперт: {project.get('expert_org', 'N/A')}")
            lines.append(f"Разработчик: {project.get('developer', 'N/A')}")
            lines.append(f"Технический заказчик: {project.get('tech_customer', 'N/A')}")
            lines.append(f"Регион: {project.get('region', 'N/A')}")
            lines.append(f"Категория: {project.get('category', 'N/A')}")
            lines.append(f"URL: {project.get('url', 'N/A')}")
            lines.append(f"Опубликовано: {project.get('published_at', 'N/A')}")
            lines.append(f"Обновлено: {project.get('updated_at', 'N/A')}")
            lines.append(f"Создано в БД: {project.get('created_at', 'N/A')}")
            lines.append(f"Уведомлено: {project.get('notified_at', 'N/A') or 'Нет'}")

            # Характеристики
            if project.get('characteristics'):
                try:
                    chars = json.loads(project.get('characteristics'))
                    if chars:
                        lines.append("\nДополнительные характеристики:")
                        for key, value in chars.items():
                            val_str = str(value).strip()
                            # Фильтровать значения "Не выбрано" и аналогичные
                            if val_str in ('Не выбрано', 'Сведения отсутствуют', '-', ''):
                                continue
                            lines.append(f"  • {key}: {val_str}")
                except:
                    pass

            lines.append("")

        lines.append("=" * 100)
        lines.append("Конец экспорта")
        lines.append("=" * 100)

        return "\n".join(lines)

    async def _perform_export(self, callback: CallbackQuery):
        """Выполнить экспорт данных в .txt файл"""
        try:
            from src.services.telegram import TelegramService

            # Получить все проекты
            projects = self.repo.get_all_projects()

            if not projects:
                await callback.answer("❌ Нет данных для экспорта", show_alert=True)
                return

            # Форматировать в текст
            txt_content = self._format_projects_to_txt(projects)

            # Отправить файл
            telegram_service = TelegramService()
            caption = f"✅ Экспорт {len(projects)} проектов"

            await telegram_service.send_file(
                file_content=txt_content,
                filename=f"projects_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                chat_ids=[str(callback.from_user.id)],
                caption=caption,
            )

            await callback.answer("✅ Файл отправлен!", show_alert=False)
            logger.info(f"Data exported by admin {callback.from_user.id}: {len(projects)} projects")

        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            await callback.answer(f"❌ Ошибка при экспорте: {str(e)[:100]}", show_alert=True)

