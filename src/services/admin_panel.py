"""
Админ-панель для управления настройками парсера
"""

import asyncio
import json
from datetime import datetime

from aiogram import Router, F
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramRetryAfter
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
CALLBACK_TOGGLE_CHAT = "admin_toggle_chat"
CALLBACK_CLEAR_DATA = "admin_clear_data"
CALLBACK_CLEAR_DATA_CONFIRM = "admin_clear_data_confirm"
CALLBACK_EXPORT = "admin_export"
CALLBACK_EXPORT_MENU = "admin_export_menu"
CALLBACK_EXPORT_REGIONS = "admin_export_regions"
CALLBACK_EXPORT_YEARS = "admin_export_years"
CALLBACK_EXPORT_RUN_PARSE = "admin_export_run_parse"
CALLBACK_EXPORT_FULL = "admin_export_full"
CALLBACK_EXPORT_DESIGNERS = "admin_export_designers"
CALLBACK_EXPORT_CATEGORIES = "admin_export_categories"
CALLBACK_CREDENTIALS = "admin_credentials"
CALLBACK_ADD_CREDENTIAL = "admin_add_cred"
CALLBACK_REMOVE_CREDENTIAL = "admin_remove_cred"
CALLBACK_SET_ACTIVE_CREDENTIAL = "admin_set_cred"
CALLBACK_CATEGORIES_RESET = "cat_reset"
CALLBACK_REGIONS_RESET = "reg_reset"
CALLBACK_SCHEDULE_HOUR = "sched_hour"
CALLBACK_SCHEDULE_DAYS = "sched_days"
CALLBACK_SCHEDULE_INTERVAL = "sched_interval"
CALLBACK_SCHEDULE_CUSTOM = "sched_custom"

ITEMS_PER_PAGE = 5


class AdminFSM(StatesGroup):
    """FSM состояния для админ-панели"""
    waiting_schedule = State()   # ожидание cron-выражения
    waiting_chat_id = State()    # ожидание chat ID
    waiting_admin_id = State()   # ожидание username или user_id админа
    waiting_credential = State() # ожидание логина и пароля учетки
    export_menu = State()        # в подменю экспорта (хранит фильтры в state data)


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

    # Регионы — дословно совпадают с option-текстами на vitrina.gge.ru
    ALL_REGIONS = [
        "0. На территории нескольких субъектов Российской Федерации",
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
        "28. Амурская область",
        "29. Архангельская область",
        "30. Астраханская область",
        "31. Белгородская область",
        "32. Брянская область",
        "33. Владимирская область",
        "34. Волгоградская область",
        "35. Вологодская область",
        "36. Воронежская область",
        "37. Ивановская область",
        "38. Иркутская область",
        "39. Калининградская область",
        "40. Калужская область",
        "41. Камчатский край",
        "42. Кемеровская область — Кузбасс",
        "43. Кировская область",
        "44. Костромская область",
        "45. Курганская область",
        "46. Курская область",
        "47. Ленинградская область",
        "48. Липецкая область",
        "49. Магаданская область",
        "50. Московская область",
        "51. Мурманская область",
        "52. Нижегородская область",
        "53. Новгородская область",
        "54. Новосибирская область",
        "55. Омская область",
        "56. Оренбургская область",
        "57. Орловская область",
        "58. Пензенская область",
        "59. Пермский край",
        "60. Псковская область",
        "61. Ростовская область",
        "62. Рязанская область",
        "63. Самарская область",
        "64. Саратовская область",
        "65. Сахалинская область",
        "66. Свердловская область",
        "67. Смоленская область",
        "68. Тамбовская область",
        "69. Тверская область",
        "70. Томская область",
        "71. Тульская область",
        "72. Тюменская область",
        "73. Ульяновская область",
        "74. Челябинская область",
        "75. Забайкальский край",
        "76. Ярославская область",
        "77. г. Москва",
        "78. г. Санкт-Петербург",
        "79. Еврейская автономная область",
        "83. Ненецкий АО",
        "86. Ханты-Мансийский АО-Югра",
        "87. Чукотский АО",
        "89. Ямало-Ненецкий АО",
        "91. Республика Крым",
        "92. г. Севастополь",
        "93. Донецкая Народная Республика",
        "94. Луганская Народная Республика",
        "95. Запорожская область",
        "96. Херсонская область",
        "99. Байконур",
    ]

    def __init__(self, repo: Repository, scheduler=None):
        self.repo = repo
        self.scheduler = scheduler
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
        self.router.message.register(
            self._handle_admin_id_text,
            AdminFSM.waiting_admin_id
        )
        self.router.message.register(
            self._handle_credential_text,
            AdminFSM.waiting_credential
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

    async def show_admin_menu(self, message: Message, state: FSMContext, user_id: int = None):
        """Показать главное меню админ-панели"""
        # Очищаем состояние при открытии админ-панели
        if state:
            await state.clear()

        if user_id is None:
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

        if data == "noop":
            return
        elif data == CALLBACK_CATEGORIES:
            await self._show_categories_menu(callback)
        elif data == CALLBACK_REGIONS:
            await self._show_regions_menu(callback)
        elif data == CALLBACK_EXPERTISE_YEAR:
            await self._show_expertise_year_menu(callback)
        elif data.startswith("expertise_year_set:"):
            year = int(data.split(":")[1])
            await self._set_expertise_year(callback, year)
        elif data == "expertise_year_reset":
            await self._reset_expertise_year(callback)
        elif data == CALLBACK_SCHEDULE:
            await self._show_schedule_menu(callback, state)
        elif data.startswith("sched_set:"):
            cron_value = data[len("sched_set:"):]
            await self._set_schedule_preset(callback, cron_value, state)
        elif data == CALLBACK_SCHEDULE_HOUR:
            await self._show_schedule_hour_menu(callback)
        elif data.startswith("sched_hour_set:"):
            hour = int(data.split(":")[1])
            await self._set_schedule_hour(callback, hour, state)
        elif data == CALLBACK_SCHEDULE_DAYS:
            await self._show_schedule_days_menu(callback)
        elif data.startswith("sched_days_set:"):
            dow = data[len("sched_days_set:"):]
            await self._set_schedule_days(callback, dow, state)
        elif data == CALLBACK_SCHEDULE_INTERVAL:
            await self._show_schedule_interval_menu(callback)
        elif data.startswith("sched_interval_set:"):
            interval = int(data.split(":")[1])
            await self._set_schedule_interval(callback, interval, state)
        elif data == CALLBACK_SCHEDULE_CUSTOM:
            await self._show_schedule_custom_input(callback, state)
        elif data == CALLBACK_ADMINS:
            await state.clear()
            await self._show_admins_menu(callback)
        elif data == CALLBACK_ADD_ADMIN:
            await self._show_add_admin_input(callback, state)
        elif data.startswith(f"{CALLBACK_ADD_ADMIN}:"):
            await self._add_admin(callback, data.split(":")[1])
        elif data.startswith(f"{CALLBACK_REMOVE_ADMIN}:"):
            await self._remove_admin(callback, data.split(":")[1])
        elif data == CALLBACK_NOTIFICATION_CHATS:
            await self._show_chats_menu(callback, state)
        elif data.startswith(f"{CALLBACK_REMOVE_CHAT}:"):
            await self._remove_chat(callback, state, data.split(":")[1])
        elif data.startswith(f"{CALLBACK_TOGGLE_CHAT}:"):
            await self._toggle_chat(callback, state, data.split(":")[1])
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
        elif data == CALLBACK_CREDENTIALS:
            await self._show_credentials_menu(callback, state)
        elif data == CALLBACK_ADD_CREDENTIAL:
            await self._show_add_credential_input(callback, state)
        elif data.startswith(f"{CALLBACK_REMOVE_CREDENTIAL}:"):
            cred_id = int(data.split(":")[1])
            await self._remove_credential(callback, state, cred_id)
        elif data.startswith(f"{CALLBACK_SET_ACTIVE_CREDENTIAL}:"):
            cred_id = int(data.split(":")[1])
            await self._set_active_credential(callback, state, cred_id)
        elif data == CALLBACK_CLEAR_DATA:
            await self._show_clear_data_confirmation(callback)
        elif data == CALLBACK_CLEAR_DATA_CONFIRM:
            await self._perform_clear_data(callback)
        elif data == CALLBACK_EXPORT or data == CALLBACK_EXPORT_MENU:
            await self._show_export_menu(callback, state)
        elif data == CALLBACK_EXPORT_CATEGORIES:
            await self._show_export_categories_menu(callback, state)
        elif data.startswith("expcat:"):
            cat_index = int(data[7:])
            await self._handle_export_category_toggle(callback, state, cat_index)
        elif data.startswith("expcatpage:"):
            page = int(data[11:])
            await self._show_export_categories_menu(callback, state, page)
        elif data == "expcat_reset":
            await state.update_data(export_categories=[])
            await self._show_export_categories_menu(callback, state)
        elif data == CALLBACK_EXPORT_REGIONS:
            await self._show_export_regions_menu(callback, state)
        elif data.startswith("expreg:"):
            region_index = int(data[7:])
            await self._handle_export_region_toggle(callback, state, region_index)
        elif data.startswith("expregpage:"):
            page = int(data[11:])
            await self._show_export_regions_menu(callback, state, page)
        elif data == "expreg_reset":
            await state.update_data(export_regions=[])
            await self._show_export_regions_menu(callback, state)
        elif data == CALLBACK_EXPORT_YEARS:
            await self._show_export_years_menu(callback, state)
        elif data.startswith("exp_year_from:"):
            year = int(data.split(":")[1])
            await state.update_data(export_year_from=year)
            await self._show_export_years_menu(callback, state)
        elif data.startswith("exp_year_to:"):
            year = int(data.split(":")[1])
            await state.update_data(export_year_to=year)
            await self._show_export_years_menu(callback, state)
        elif data == CALLBACK_EXPORT_RUN_PARSE:
            await self._run_export_parsing(callback, state)
        elif data == CALLBACK_EXPORT_FULL:
            await self._perform_export_full(callback, state)
        elif data == CALLBACK_EXPORT_DESIGNERS:
            await self._perform_export_designers(callback, state)

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
        current_year_value = settings.expertise_year

        text = (
            "📅 <b>Год экспертизы</b>\n\n"
            f"Текущий: <b>{current_year_value or 'все'}</b>\n\n"
            "Выберите год экспертизы:\n"
            "Проекты будут отфильтрованы по номеру экспертизы\n"
            "(последние цифры номера = год)"
        )

        current_year = datetime.now().year
        years = list(range(current_year - 10, current_year + 2))

        keyboard = []
        row = []
        for year in reversed(years):
            label = f"✅ {year}" if year == current_year_value else str(year)
            row.append(InlineKeyboardButton(text=label, callback_data=f"expertise_year_set:{year}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        keyboard.append([InlineKeyboardButton(text="🔄 Сбросить", callback_data="expertise_year_reset")])
        keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_BACK)])

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    async def _set_expertise_year(self, callback: CallbackQuery, year: int):
        """Установить год экспертизы"""
        settings = self.repo.get_all_settings()
        settings.expertise_year = year
        self.repo.save_settings(settings)
        await self._show_expertise_year_menu(callback)

    async def _reset_expertise_year(self, callback: CallbackQuery):
        """Сбросить фильтр по году экспертизы"""
        settings = self.repo.get_all_settings()
        settings.expertise_year = None
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

    @staticmethod
    def _cron_to_human(cron: str) -> str:
        """Преобразовать cron-выражение в читаемый текст"""
        parts = cron.split()
        if len(parts) != 5:
            return cron

        minute, hour, dom, month, dow = parts

        DAYS_MAP = {
            "0": "Вс", "1": "Пн", "2": "Вт", "3": "Ср",
            "4": "Чт", "5": "Пт", "6": "Сб", "7": "Вс",
        }

        # Определяем время
        time_str = ""
        if hour.startswith("*/"):
            interval = hour[2:]
            time_str = f"каждые {interval}ч"
            if minute != "0":
                time_str += f" (в :{minute.zfill(2)})"
        elif minute == "0":
            time_str = f"в {hour}:00 UTC"
        else:
            time_str = f"в {hour}:{minute.zfill(2)} UTC"

        # Определяем дни
        days_str = ""
        if dow == "*" and dom == "*":
            days_str = "ежедневно"
        elif dow == "1-5":
            days_str = "по будням (Пн-Пт)"
        elif dow == "0,6" or dow == "6,0":
            days_str = "по выходным (Сб-Вс)"
        elif dow != "*":
            # Разбираем конкретные дни
            day_parts = dow.replace("-", ",").split(",")
            day_names = [DAYS_MAP.get(d, d) for d in day_parts if d in DAYS_MAP]
            if day_names:
                days_str = ", ".join(day_names)
            else:
                days_str = f"дни: {dow}"
        else:
            days_str = "ежедневно"

        return f"{days_str}, {time_str}"

    async def _show_schedule_menu(self, callback: CallbackQuery, state: FSMContext):
        """Меню расписания с удобными кнопками"""
        settings = self.repo.get_all_settings()
        cron = settings.cron_schedule
        human = self._cron_to_human(cron)

        text = (
            "⏰ <b>Расписание запуска</b>\n\n"
            f"Текущее: <b>{human}</b>\n"
            f"<code>{cron}</code>\n\n"
            "Выберите готовый вариант или настройте:"
        )

        keyboard = [
            # Быстрые пресеты
            [InlineKeyboardButton(
                text=("✅ " if cron == "0 6 * * *" else "") + "Ежедневно в 06:00",
                callback_data="sched_set:0 6 * * *",
            )],
            [InlineKeyboardButton(
                text=("✅ " if cron == "0 9 * * *" else "") + "Ежедневно в 09:00",
                callback_data="sched_set:0 9 * * *",
            )],
            [InlineKeyboardButton(
                text=("✅ " if cron == "0 12 * * *" else "") + "Ежедневно в 12:00",
                callback_data="sched_set:0 12 * * *",
            )],
            [InlineKeyboardButton(
                text=("✅ " if cron == "0 9 * * 1-5" else "") + "По будням в 09:00",
                callback_data="sched_set:0 9 * * 1-5",
            )],
            [InlineKeyboardButton(
                text=("✅ " if cron == "0 6 * * 1-5" else "") + "По будням в 06:00",
                callback_data="sched_set:0 6 * * 1-5",
            )],
            # Подменю
            [
                InlineKeyboardButton(text="🕐 Выбрать час", callback_data=CALLBACK_SCHEDULE_HOUR),
                InlineKeyboardButton(text="📅 Дни недели", callback_data=CALLBACK_SCHEDULE_DAYS),
            ],
            [
                InlineKeyboardButton(text="🔄 Интервал (каждые N ч)", callback_data=CALLBACK_SCHEDULE_INTERVAL),
            ],
            [InlineKeyboardButton(text="✏️ Ввести cron вручную", callback_data=CALLBACK_SCHEDULE_CUSTOM)],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_BACK)],
        ]

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    async def _set_schedule_preset(self, callback: CallbackQuery, cron: str, state: FSMContext):
        """Установить пресет расписания"""
        settings = self.repo.get_all_settings()
        settings.cron_schedule = cron
        self.repo.save_settings(settings)
        if self.scheduler:
            self.scheduler.reschedule(cron)
        await self._show_schedule_menu(callback, state)

    async def _show_schedule_hour_menu(self, callback: CallbackQuery):
        """Выбор часа запуска"""
        settings = self.repo.get_all_settings()
        parts = settings.cron_schedule.split()
        current_hour = parts[1] if len(parts) == 5 else "6"
        current_dow = parts[4] if len(parts) == 5 else "*"

        text = (
            "🕐 <b>Выберите час запуска (UTC)</b>\n\n"
            f"Текущий: <b>{current_hour}:00 UTC</b>\n"
            "Дни останутся без изменений."
        )

        keyboard = []
        row = []
        for h in range(24):
            label = f"✅ {h:02d}" if str(h) == current_hour else f"{h:02d}"
            row.append(InlineKeyboardButton(
                text=label,
                callback_data=f"sched_hour_set:{h}",
            ))
            if len(row) == 6:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        keyboard.append([InlineKeyboardButton(text="◀️ Назад к расписанию", callback_data=CALLBACK_SCHEDULE)])

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    async def _set_schedule_hour(self, callback: CallbackQuery, hour: int, state: FSMContext):
        """Установить час в расписании"""
        settings = self.repo.get_all_settings()
        parts = settings.cron_schedule.split()
        if len(parts) == 5:
            # Сохраняем дни, меняем час и минуту
            parts[0] = "0"
            parts[1] = str(hour)
        else:
            parts = ["0", str(hour), "*", "*", "*"]

        settings.cron_schedule = " ".join(parts)
        self.repo.save_settings(settings)
        if self.scheduler:
            self.scheduler.reschedule(settings.cron_schedule)
        await self._show_schedule_menu(callback, state)

    async def _show_schedule_days_menu(self, callback: CallbackQuery):
        """Выбор дней недели"""
        settings = self.repo.get_all_settings()
        parts = settings.cron_schedule.split()
        current_dow = parts[4] if len(parts) == 5 else "*"

        text = (
            "📅 <b>Дни запуска</b>\n\n"
            f"Текущие: <b>{self._dow_to_human(current_dow)}</b>\n"
            "Час останется без изменений."
        )

        keyboard = [
            [InlineKeyboardButton(
                text=("✅ " if current_dow == "*" else "") + "Ежедневно",
                callback_data="sched_days_set:*",
            )],
            [InlineKeyboardButton(
                text=("✅ " if current_dow == "1-5" else "") + "Будни (Пн-Пт)",
                callback_data="sched_days_set:1-5",
            )],
            [InlineKeyboardButton(
                text=("✅ " if current_dow in ("0,6", "6,0") else "") + "Выходные (Сб-Вс)",
                callback_data="sched_days_set:6,0",
            )],
            [InlineKeyboardButton(text="◀️ Назад к расписанию", callback_data=CALLBACK_SCHEDULE)],
        ]

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    @staticmethod
    def _dow_to_human(dow: str) -> str:
        """Дни недели cron → текст"""
        if dow == "*":
            return "ежедневно"
        if dow == "1-5":
            return "Пн-Пт (будни)"
        if dow in ("0,6", "6,0"):
            return "Сб-Вс (выходные)"
        return dow

    async def _set_schedule_days(self, callback: CallbackQuery, dow: str, state: FSMContext):
        """Установить дни недели в расписании"""
        settings = self.repo.get_all_settings()
        parts = settings.cron_schedule.split()
        if len(parts) == 5:
            # Если был интервал (*/N), переключаемся на конкретный час
            if parts[1].startswith("*/"):
                parts[0] = "0"
                parts[1] = "6"
            parts[4] = dow
        else:
            parts = ["0", "6", "*", "*", dow]

        settings.cron_schedule = " ".join(parts)
        self.repo.save_settings(settings)
        if self.scheduler:
            self.scheduler.reschedule(settings.cron_schedule)
        await self._show_schedule_menu(callback, state)

    async def _show_schedule_interval_menu(self, callback: CallbackQuery):
        """Выбор интервала запуска"""
        settings = self.repo.get_all_settings()
        parts = settings.cron_schedule.split()
        current_hour = parts[1] if len(parts) == 5 else "6"

        text = (
            "🔄 <b>Запуск каждые N часов</b>\n\n"
            "Парсер будет запускаться с заданным интервалом, ежедневно.\n"
            "⚠️ Дни недели будут сброшены на «ежедневно»."
        )

        intervals = [2, 3, 4, 6, 8, 12]
        keyboard = []
        row = []
        for iv in intervals:
            is_current = current_hour == f"*/{iv}"
            label = f"✅ {iv}ч" if is_current else f"Каждые {iv}ч"
            row.append(InlineKeyboardButton(
                text=label,
                callback_data=f"sched_interval_set:{iv}",
            ))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        keyboard.append([InlineKeyboardButton(text="◀️ Назад к расписанию", callback_data=CALLBACK_SCHEDULE)])

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    async def _set_schedule_interval(self, callback: CallbackQuery, interval: int, state: FSMContext):
        """Установить интервальное расписание"""
        settings = self.repo.get_all_settings()
        settings.cron_schedule = f"0 */{interval} * * *"
        self.repo.save_settings(settings)
        if self.scheduler:
            self.scheduler.reschedule(settings.cron_schedule)
        await self._show_schedule_menu(callback, state)

    async def _show_schedule_custom_input(self, callback: CallbackQuery, state: FSMContext):
        """Показать форму ручного ввода cron"""
        settings = self.repo.get_all_settings()

        text = (
            "✏️ <b>Ручной ввод cron-расписания</b>\n\n"
            f"Текущее: <code>{settings.cron_schedule}</code>\n\n"
            "Формат: <code>минута час день месяц день_недели</code>\n"
            "Примеры:\n"
            "• <code>0 6 * * *</code> — ежедневно в 6:00 UTC\n"
            "• <code>0 9 * * 1-5</code> — в 9:00 по будням\n"
            "• <code>0 */4 * * *</code> — каждые 4 часа\n"
            "• <code>30 7 * * *</code> — ежедневно в 7:30 UTC\n\n"
            "Отправьте новое расписание сообщением:"
        )

        keyboard = [[InlineKeyboardButton(text="◀️ Назад к расписанию", callback_data=CALLBACK_SCHEDULE)]]
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

        keyboard = [
            [InlineKeyboardButton(text="➕ Добавить админа", callback_data=CALLBACK_ADD_ADMIN)],
        ]

        if admins:
            for admin in admins:
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            text=f"❌ {admin.username or admin.telegram_id}",
                            callback_data=f"{CALLBACK_REMOVE_ADMIN}:{admin.telegram_id}",
                        )
                    ]
                )

        keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_BACK)])

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

    async def _show_add_admin_input(self, callback: CallbackQuery, state: FSMContext):
        """Показать форму ввода для добавления админа"""
        text = (
            "➕ <b>Добавление администратора</b>\n\n"
            "Отправьте <b>username</b> (без @) или <b>Telegram ID</b> пользователя.\n\n"
            "Примеры:\n"
            "• <code>username123</code>\n"
            "• <code>123456789</code>"
        )
        keyboard = [[InlineKeyboardButton(text="◀️ Отмена", callback_data=CALLBACK_ADMINS)]]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        await state.set_state(AdminFSM.waiting_admin_id)

    async def _handle_admin_id_text(self, message: Message, state: FSMContext):
        """Обработка ввода username или user_id для добавления админа (FSM)"""
        user_id = message.from_user.id
        logger.info(f"User {user_id} entered admin ID/username in FSM")

        if not self._check_admin(user_id):
            logger.warning(f"User {user_id} tried to add admin without admin rights")
            return

        input_text = message.text.strip().lstrip("@")

        if not input_text:
            await message.answer("❌ Введите username или Telegram ID.")
            return

        # Определяем: числовой ID или username
        username = None
        if input_text.isdigit():
            telegram_id = input_text
        else:
            # Это username — сохраняем как есть, telegram_id = username (до резолва)
            telegram_id = input_text
            username = input_text

        self.repo.add_admin(telegram_id, username)

        await state.clear()

        display = f"@{username}" if username else telegram_id
        keyboard = [[InlineKeyboardButton(text="◀️ Назад к админам", callback_data=CALLBACK_ADMINS)]]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

        await message.answer(
            f"✅ Администратор {display} добавлен",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )

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
                toggle_icon = "🔕" if chat.is_active else "🔔"
                toggle_label = "Выкл" if chat.is_active else "Вкл"
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            text=f"{toggle_icon} {toggle_label}",
                            callback_data=f"{CALLBACK_TOGGLE_CHAT}:{chat.chat_id}",
                        ),
                        InlineKeyboardButton(
                            text=f"🗑 {chat_display}",
                            callback_data=f"{CALLBACK_REMOVE_CHAT}:{chat.chat_id}",
                        ),
                    ]
                )

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        await state.set_state(AdminFSM.waiting_chat_id)

    async def _toggle_chat(self, callback: CallbackQuery, state: FSMContext, chat_id: str):
        """Переключить активность чата"""
        new_state = self.repo.toggle_notification_chat(chat_id)
        status = "включён ✅" if new_state else "выключен 🔕"
        await callback.answer(f"Чат {chat_id} {status}", show_alert=True)
        await self._show_chats_menu(callback, state)

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
        year_display = settings.expertise_year or "все"

        text = (
            "⚙️ <b>Админ-панель парсера</b>\n\n"
            "📊 <b>Текущие настройки:</b>\n"
            f"• Категории: {categories_count} выбр.\n"
            f"• Регионы: {regions_count} выбр.\n"
            f"• Год экспертизы: {year_display}\n"
            f"• Расписание: {self._cron_to_human(settings.cron_schedule)}\n\n"
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
                InlineKeyboardButton(text="🔑 Учетки", callback_data=CALLBACK_CREDENTIALS),
            ],
            [
                InlineKeyboardButton(text="📊 Экспорт в Excel", callback_data=CALLBACK_EXPORT_MENU),
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
        if self.scheduler:
            self.scheduler.reschedule(new_schedule)

        await state.clear()

        keyboard = [[InlineKeyboardButton(text="◀️ Назад в админ-панель", callback_data=CALLBACK_BACK)]]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

        human = self._cron_to_human(new_schedule)
        await message.answer(
            f"✅ Расписание обновлено: <b>{human}</b>\n"
            f"<code>{new_schedule}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
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

        keyboard = [[InlineKeyboardButton(text="◀️ Назад в админ-панель", callback_data=CALLBACK_BACK)]]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

        await message.answer(
            f"✅ Чат {chat_id_input} добавлен для отправки уведомлений",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )

    # ========== Учетные записи ==========

    async def _show_credentials_menu(self, callback: CallbackQuery, state: FSMContext):
        """Меню управления учетными записями"""
        await state.clear()
        credentials = self.repo.get_all_credentials()

        text = "🔑 <b>Учетные записи</b>\n\n"

        if credentials:
            for cred in credentials:
                status = "✅" if cred.is_active else "⬜"
                label = cred.label or cred.login
                text += f"{status} {label} (<code>{cred.login}</code>)\n"
        else:
            text += "Нет учетных записей\n"

        text += "\nАктивная учетка используется для парсинга."

        keyboard = [
            [InlineKeyboardButton(text="➕ Добавить учетку", callback_data=CALLBACK_ADD_CREDENTIAL)],
        ]

        if credentials:
            for cred in credentials:
                row = []
                if not cred.is_active:
                    row.append(InlineKeyboardButton(
                        text=f"✅ Выбрать {cred.label or cred.login}",
                        callback_data=f"{CALLBACK_SET_ACTIVE_CREDENTIAL}:{cred.id}",
                    ))
                row.append(InlineKeyboardButton(
                    text=f"🗑 {cred.label or cred.login}",
                    callback_data=f"{CALLBACK_REMOVE_CREDENTIAL}:{cred.id}",
                ))
                keyboard.append(row)

        keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_BACK)])

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    async def _show_add_credential_input(self, callback: CallbackQuery, state: FSMContext):
        """Показать форму добавления учетки"""
        text = (
            "➕ <b>Добавление учетной записи</b>\n\n"
            "Отправьте данные в формате:\n"
            "<code>логин пароль</code>\n\n"
            "Или с названием:\n"
            "<code>логин пароль Название</code>\n\n"
            "Пример:\n"
            "<code>user@mail.ru mypass123 Основной</code>"
        )
        keyboard = [[InlineKeyboardButton(text="◀️ Отмена", callback_data=CALLBACK_CREDENTIALS)]]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        await state.set_state(AdminFSM.waiting_credential)

    async def _handle_credential_text(self, message: Message, state: FSMContext):
        """Обработка ввода учетных данных (FSM)"""
        user_id = message.from_user.id
        logger.info(f"User {user_id} entered credential in FSM")

        if not self._check_admin(user_id):
            return

        parts = message.text.strip().split(maxsplit=2)
        if len(parts) < 2:
            await message.answer(
                "❌ Неверный формат. Отправьте:\n"
                "<code>логин пароль</code>\n"
                "или\n"
                "<code>логин пароль Название</code>",
                parse_mode=ParseMode.HTML,
            )
            return

        login = parts[0]
        password = parts[1]
        label = parts[2] if len(parts) > 2 else None

        self.repo.add_credential(login, password, label)

        # Если это первая учетка, сделать активной
        credentials = self.repo.get_all_credentials()
        active = any(c.is_active for c in credentials)
        if not active and credentials:
            self.repo.set_active_credential(credentials[0].id)
            # Обновить сессию
            self._update_session_credentials(credentials[0].login, credentials[0].password)

        await state.clear()

        display = label or login
        keyboard = [[InlineKeyboardButton(text="◀️ К учеткам", callback_data=CALLBACK_CREDENTIALS)]]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

        await message.answer(
            f"✅ Учетная запись <b>{display}</b> добавлена",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )

    async def _remove_credential(self, callback: CallbackQuery, state: FSMContext, cred_id: int):
        """Удалить учетную запись"""
        credentials = self.repo.get_all_credentials()
        cred = next((c for c in credentials if c.id == cred_id), None)

        if cred and cred.is_active:
            await callback.answer("❌ Нельзя удалить активную учетку. Сначала выберите другую.", show_alert=True)
            return

        self.repo.remove_credential(cred_id)
        await callback.answer("✅ Учетка удалена", show_alert=True)
        await self._show_credentials_menu(callback, state)

    async def _set_active_credential(self, callback: CallbackQuery, state: FSMContext, cred_id: int):
        """Установить активную учетку"""
        self.repo.set_active_credential(cred_id)

        # Обновить сессию браузера
        cred = self.repo.get_active_credential()
        if cred:
            self._update_session_credentials(cred.login, cred.password)

        await callback.answer("✅ Учетка активирована", show_alert=True)
        await self._show_credentials_menu(callback, state)

    def _update_session_credentials(self, login: str, password: str):
        """Обновить учетные данные в SessionManager"""
        try:
            from src.browser.session import SessionManager
            session = SessionManager()
            session.set_credentials(login, password)
        except Exception as e:
            logger.error(f"Failed to update session credentials: {e}")

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

        except TelegramRetryAfter as e:
            logger.warning(f"Flood control on clear_data, retrying in {e.retry_after}s")
            await asyncio.sleep(e.retry_after)
            await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Error clearing data: {e}")
            await callback.answer(f"❌ Ошибка при очистке: {str(e)[:100]}", show_alert=True)

    # ========== Подменю экспорта в Excel ==========

    async def _show_export_menu(self, callback: CallbackQuery, state: FSMContext):
        """Показать подменю экспорта с текущими фильтрами"""
        await state.set_state(AdminFSM.export_menu)
        data = await state.get_data()

        export_regions = data.get('export_regions', [])
        export_categories = data.get('export_categories', [])
        export_year_from = data.get('export_year_from')
        export_year_to = data.get('export_year_to')

        regions_text = f"{len(export_regions)} выбр." if export_regions else "все"
        categories_text = f"{len(export_categories)} выбр." if export_categories else "все"
        year_from_text = str(export_year_from) if export_year_from else "—"
        year_to_text = str(export_year_to) if export_year_to else "—"

        text = (
            "📊 <b>Экспорт в Excel</b>\n\n"
            "<b>Фильтры экспорта:</b>\n"
            f"• Категории: {categories_text}\n"
            f"• Регионы: {regions_text}\n"
            f"• Период экспертизы: {year_from_text} — {year_to_text}\n\n"
            "1️⃣ Выберите фильтры\n"
            "2️⃣ Запустите парсинг (загрузит новые проекты)\n"
            "3️⃣ Экспортируйте в Excel"
        )

        keyboard = [
            [InlineKeyboardButton(text="📁 Выбрать категории", callback_data=CALLBACK_EXPORT_CATEGORIES)],
            [InlineKeyboardButton(text="📍 Выбрать регионы", callback_data=CALLBACK_EXPORT_REGIONS)],
            [InlineKeyboardButton(text="📅 Период экспертизы", callback_data=CALLBACK_EXPORT_YEARS)],
            [InlineKeyboardButton(text="🔄 Запустить парсинг", callback_data=CALLBACK_EXPORT_RUN_PARSE)],
            [InlineKeyboardButton(text="📋 Полный экспорт .xlsx", callback_data=CALLBACK_EXPORT_FULL)],
            [InlineKeyboardButton(text="🏗 Проектировщики .xlsx", callback_data=CALLBACK_EXPORT_DESIGNERS)],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_BACK)],
        ]

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    async def _show_export_categories_menu(self, callback: CallbackQuery, state: FSMContext, page: int = 0):
        """Меню выбора категорий для экспорта"""
        data = await state.get_data()
        selected = set(data.get('export_categories', []))

        text = (
            "📁 <b>Категории для экспорта</b>\n\n"
            f"Выбрано: {len(selected)}\n\n"
            "Нажмите на категорию для выбора/снятия:"
        )

        total_pages = (len(self.ALL_CATEGORIES) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        start_idx = page * ITEMS_PER_PAGE
        end_idx = min(start_idx + ITEMS_PER_PAGE, len(self.ALL_CATEGORIES))

        keyboard = []
        for i in range(start_idx, end_idx):
            category = self.ALL_CATEGORIES[i]
            is_selected = category in selected
            emoji = "✅" if is_selected else "⬜"
            keyboard.append(
                [InlineKeyboardButton(text=f"{emoji} {category}", callback_data=f"expcat:{i}")]
            )

        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"expcatpage:{page-1}"))
        if end_idx < len(self.ALL_CATEGORIES):
            nav_row.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"expcatpage:{page+1}"))

        if nav_row:
            keyboard.append(nav_row)

        keyboard.append([InlineKeyboardButton(text="🔄 Сбросить категории", callback_data="expcat_reset")])
        keyboard.append([InlineKeyboardButton(text="✅ Готово", callback_data=CALLBACK_EXPORT_MENU)])

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    async def _handle_export_category_toggle(self, callback: CallbackQuery, state: FSMContext, cat_index: int):
        """Переключить категорию экспорта по индексу"""
        if cat_index < 0 or cat_index >= len(self.ALL_CATEGORIES):
            return

        data = await state.get_data()
        export_categories = list(data.get('export_categories', []))
        category = self.ALL_CATEGORIES[cat_index]

        if category in export_categories:
            export_categories.remove(category)
        else:
            export_categories.append(category)

        await state.update_data(export_categories=export_categories)
        current_page = cat_index // ITEMS_PER_PAGE
        await self._show_export_categories_menu(callback, state, current_page)

    async def _show_export_regions_menu(self, callback: CallbackQuery, state: FSMContext, page: int = 0):
        """Меню выбора регионов для экспорта"""
        data = await state.get_data()
        selected = set(data.get('export_regions', []))

        text = (
            "📍 <b>Регионы для экспорта</b>\n\n"
            f"Выбрано: {len(selected)}\n\n"
            "Нажмите на регион для выбора/снятия:"
        )

        total_pages = (len(self.ALL_REGIONS) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        start_idx = page * ITEMS_PER_PAGE
        end_idx = min(start_idx + ITEMS_PER_PAGE, len(self.ALL_REGIONS))

        keyboard = []
        for i in range(start_idx, end_idx):
            region = self.ALL_REGIONS[i]
            is_selected = region in selected
            emoji = "✅" if is_selected else "⬜"
            keyboard.append(
                [InlineKeyboardButton(text=f"{emoji} {region}", callback_data=f"expreg:{i}")]
            )

        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"expregpage:{page-1}"))
        if end_idx < len(self.ALL_REGIONS):
            nav_row.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"expregpage:{page+1}"))

        if nav_row:
            keyboard.append(nav_row)

        keyboard.append([InlineKeyboardButton(text="🔄 Сбросить регионы", callback_data="expreg_reset")])
        keyboard.append([InlineKeyboardButton(text="✅ Готово", callback_data=CALLBACK_EXPORT_MENU)])

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    async def _handle_export_region_toggle(self, callback: CallbackQuery, state: FSMContext, region_index: int):
        """Переключить регион экспорта по индексу"""
        if region_index < 0 or region_index >= len(self.ALL_REGIONS):
            return

        data = await state.get_data()
        export_regions = list(data.get('export_regions', []))
        region = self.ALL_REGIONS[region_index]

        if region in export_regions:
            export_regions.remove(region)
        else:
            export_regions.append(region)

        await state.update_data(export_regions=export_regions)
        current_page = region_index // ITEMS_PER_PAGE
        await self._show_export_regions_menu(callback, state, current_page)

    async def _show_export_years_menu(self, callback: CallbackQuery, state: FSMContext):
        """Меню выбора периода экспертизы для экспорта"""
        data = await state.get_data()
        current_from = data.get('export_year_from')
        current_to = data.get('export_year_to')

        text = (
            "📅 <b>Период экспертизы для экспорта</b>\n\n"
            f"С года: <b>{current_from or '—'}</b>\n"
            f"По год: <b>{current_to or '—'}</b>\n\n"
            "Выберите начальный и конечный год:"
        )

        current_year = datetime.now().year
        years = list(range(2015, current_year + 2))

        # Ряд "С года:"
        keyboard = []
        keyboard.append([InlineKeyboardButton(text="— С года: —", callback_data="noop")])

        row = []
        for year in years:
            emoji = "✅ " if year == current_from else ""
            row.append(InlineKeyboardButton(text=f"{emoji}{year}", callback_data=f"exp_year_from:{year}"))
            if len(row) == 4:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        # Ряд "По год:"
        keyboard.append([InlineKeyboardButton(text="— По год: —", callback_data="noop")])

        row = []
        for year in years:
            emoji = "✅ " if year == current_to else ""
            row.append(InlineKeyboardButton(text=f"{emoji}{year}", callback_data=f"exp_year_to:{year}"))
            if len(row) == 4:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        keyboard.append([InlineKeyboardButton(text="✅ Готово", callback_data=CALLBACK_EXPORT_MENU)])

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    async def _run_export_parsing(self, callback: CallbackQuery, state: FSMContext):
        """Запустить парсинг с фильтрами экспорта"""
        if not self.scheduler:
            await callback.message.edit_text(
                "❌ Планировщик не инициализирован",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_EXPORT_MENU)]
                ]),
                parse_mode=ParseMode.HTML,
            )
            return

        if self.scheduler.is_running:
            await callback.message.edit_text(
                "⏳ Парсер уже запущен. Дождитесь завершения.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_EXPORT_MENU)]
                ]),
                parse_mode=ParseMode.HTML,
            )
            return

        data = await state.get_data()
        export_regions = data.get('export_regions', [])
        export_categories = data.get('export_categories', [])
        export_year_from = data.get('export_year_from')
        export_year_to = data.get('export_year_to')

        # Собрать список годов
        expertise_years = None
        if export_year_from and export_year_to:
            expertise_years = list(range(export_year_from, export_year_to + 1))
        elif export_year_from:
            expertise_years = [export_year_from]
        elif export_year_to:
            expertise_years = [export_year_to]

        categories_text = f"{len(export_categories)} кат." if export_categories else "все"
        regions_text = f"{len(export_regions)} рег." if export_regions else "все"
        years_text = f"{export_year_from or '?'}—{export_year_to or '?'}" if (export_year_from or export_year_to) else "все"

        await callback.message.edit_text(
            f"⏳ <b>Парсинг запущен...</b>\n\n"
            f"Категории: {categories_text}\n"
            f"Регионы: {regions_text}\n"
            f"Годы: {years_text}\n\n"
            f"Это может занять несколько минут.",
            parse_mode=ParseMode.HTML,
        )

        try:
            result = await self.scheduler.run_bulk_parse(
                regions=export_regions or None,
                categories=export_categories or None,
                expertise_years=expertise_years,
            )

            text = (
                f"✅ <b>Парсинг завершён!</b>\n\n"
                f"📊 Всего найдено: {result['total']}\n"
                f"🆕 Новых сохранено: {result['new']}\n"
                f"⏭ Пропущено (уже в БД): {result['skipped']}\n\n"
                f"Теперь можно экспортировать данные."
            )

            keyboard = [
                [InlineKeyboardButton(text="📋 Полный экспорт .xlsx", callback_data=CALLBACK_EXPORT_FULL)],
                [InlineKeyboardButton(text="🏗 Проектировщики .xlsx", callback_data=CALLBACK_EXPORT_DESIGNERS)],
                [InlineKeyboardButton(text="◀️ Назад в меню экспорта", callback_data=CALLBACK_EXPORT_MENU)],
            ]

            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

        except Exception as e:
            logger.error(f"Export parsing error: {e}", exc_info=True)
            text = f"❌ <b>Ошибка парсинга:</b>\n<code>{str(e)[:200]}</code>"
            keyboard = [
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=CALLBACK_EXPORT_RUN_PARSE)],
                [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_EXPORT_MENU)],
            ]
            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    async def _perform_export_full(self, callback: CallbackQuery, state: FSMContext):
        """Полный экспорт проектов в Excel"""
        try:
            from src.services.telegram import TelegramService
            from src.utils.excel_export import generate_full_export

            data = await state.get_data()
            export_regions = data.get('export_regions', [])
            export_categories = data.get('export_categories', [])
            export_year_from = data.get('export_year_from')
            export_year_to = data.get('export_year_to')

            logger.info(f"Export full: categories={export_categories}, regions={export_regions}, year_from={export_year_from}, year_to={export_year_to}")

            projects = self.repo.get_projects_filtered(
                regions=export_regions or None,
                categories=export_categories or None,
                year_from=export_year_from,
                year_to=export_year_to,
            )

            if not projects:
                await callback.message.answer("❌ Нет данных для экспорта. Сначала запустите парсинг.")
                return

            await callback.message.answer("⏳ Формирую Excel-файл...")

            excel_bytes = generate_full_export(projects)

            telegram_service = TelegramService()
            filename = f"projects_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            caption = f"📋 Полный экспорт: {len(projects)} проектов"

            await telegram_service.send_binary_file(
                file_bytes=excel_bytes,
                filename=filename,
                chat_ids=[str(callback.from_user.id)],
                caption=caption,
            )

            logger.info(f"Full Excel export by admin {callback.from_user.id}: {len(projects)} projects")

        except Exception as e:
            logger.error(f"Error exporting to Excel: {e}", exc_info=True)
            await callback.message.answer(f"❌ Ошибка экспорта: {str(e)[:200]}")

    async def _perform_export_designers(self, callback: CallbackQuery, state: FSMContext):
        """Экспорт аналитики проектировщиков в Excel"""
        try:
            from src.services.telegram import TelegramService
            from src.utils.excel_export import generate_designers_report

            data = await state.get_data()
            export_regions = data.get('export_regions', [])
            export_categories = data.get('export_categories', [])
            export_year_from = data.get('export_year_from')
            export_year_to = data.get('export_year_to')
            logger.info(f"Export designers: categories={export_categories}, regions={export_regions}, year_from={export_year_from}, year_to={export_year_to}")

            projects = self.repo.get_projects_filtered(
                regions=export_regions or None,
                categories=export_categories or None,
                year_from=export_year_from,
                year_to=export_year_to,
            )

            if not projects:
                await callback.message.answer("❌ Нет данных для экспорта. Сначала запустите парсинг.")
                return

            await callback.message.answer("⏳ Формирую Excel-файл...")

            excel_bytes = generate_designers_report(projects)

            telegram_service = TelegramService()
            filename = f"designers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            caption = f"🏗 Проектировщики: {len(projects)} проектов"

            await telegram_service.send_binary_file(
                file_bytes=excel_bytes,
                filename=filename,
                chat_ids=[str(callback.from_user.id)],
                caption=caption,
            )

            logger.info(f"Designers Excel export by admin {callback.from_user.id}: {len(projects)} projects")

        except Exception as e:
            logger.error(f"Error exporting designers report: {e}", exc_info=True)
            await callback.message.answer(f"❌ Ошибка экспорта: {str(e)[:200]}")

