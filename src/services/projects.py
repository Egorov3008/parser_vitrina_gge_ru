import asyncio
from datetime import datetime
from typing import List, Optional

import httpx

from src.browser.scraper import Scraper
from src.browser.session import SessionManager
from src.config import get_config
from src.db.repository import Project
from src.utils.logger import get_logger

logger = get_logger()

# Словарь сопоставления русских лейблов с полями датакласса Project
LABEL_MAPPING = {
    "номер экспертизы": "expertise_num",
    "№ экспертизы": "expertise_num",
    "номер заключения": "expertise_num",
    "регистрационный номер": "expertise_num",
    "реестровый номер": "expertise_num",
    "экспертная организация": "expert_org",
    "орган экспертизы": "expert_org",
    "организация": "expert_org",
    "застройщик": "developer",
    "инвестор-застройщик": "developer",
    "технический заказчик": "tech_customer",
    "техзаказчик": "tech_customer",
    "регион": "region",
    "субъект": "region",
    "категория": "category",
    "функциональное назначение": "category",
    "наименование объекта": "object_name",
    "наименование": "object_name",
    "объект капитального строительства": "object_name",
    "объект": "object_name",
}

# JS-код для извлечения данных из #object-* элементов (новая структура sidebar)
JS_EXTRACT_BY_IDS = """
() => {
    const result = {
        vitrina_id: null,
        object_name: null,
        category: null,
        region: null,
        developer: null,
        expertise_num: null,
        expertise_nums: [],
        characteristics: {},
        teps: {}
    };

    // Хелпер: получить текст из элемента
    const getText = (selector) => {
        const el = document.querySelector(selector);
        return el ? el.innerText.trim() : null;
    };

    // Хелпер: удалить leading zeros из ID
    const removeLeadingZeros = (id) => {
        return id ? String(parseInt(id, 10)) : null;
    };

    // Основные поля из ID элементов
    result.object_name = getText('#object-name');
    result.category = getText('#object-func');
    result.region = getText('#object-region');
    result.developer = getText('#object-developer');

    // vitrina_id из #object-id
    let idText = getText('#object-id');
    if (idText) {
        result.vitrina_id = removeLeadingZeros(idText);
    }

    // Номера экспертиз из #object-conclusions (ссылки)
    const conclusionsEl = document.querySelector('#object-conclusions');
    if (conclusionsEl) {
        const links = conclusionsEl.querySelectorAll('a');
        links.forEach((link, idx) => {
            const text = link.innerText.trim();
            if (text) {
                result.expertise_nums.push(text);
                if (idx === 0) {
                    result.expertise_num = text;  // первый номер
                }
            }
        });
    }

    // Дополнительные поля в characteristics
    const charFields = [
        'object-addr',
        'object-power',
        'object-cost',
        'object-finance',
        'object-designer',
        'object-tpd',
        'object-natproj',
        'object-construction-permit',
        'object-entry-number',
        'object-kazna',
        'object-climat',
        'object-geolog',
        'object-wind',
        'object-snow',
        'object-seysm'
    ];

    charFields.forEach(field => {
        const value = getText('#' + field);
        if (value && value !== 'Сведения отсутствуют' && value !== 'Не выбрано') {
            result.characteristics[field] = value;
        }
    });

    // Таблица показателей #object-teps
    const tepsEl = document.querySelector('#object-teps');
    if (tepsEl) {
        const rows = tepsEl.querySelectorAll('tr');
        rows.forEach(row => {
            const cells = row.querySelectorAll('td, th');
            if (cells.length >= 2) {
                const k = cells[0].innerText.trim();
                const v = cells[1].innerText.trim();
                if (k && v && v !== 'Сведения отсутствуют' && v !== 'Не выбрано') {
                    result.teps[k] = v;
                    result.characteristics[k] = v;
                }
            }
        });
    }

    return result;
}
"""

# JS-код для извлечения всех пар лейбл-значение + секции характеристик
JS_EXTRACT_PAIRS = """
() => {
    const pairs = {};
    const charSection = {};

    // Хелпер: клонировать элемент и удалить input/select перед чтением текста
    const cleanText = el => {
        const clone = el.cloneNode(true);
        clone.querySelectorAll('input, select').forEach(i => i.remove());
        return clone.innerText.trim();
    };

    // Структура 1: таблицы <tr><td>Лейбл</td><td>Значение</td></tr>
    document.querySelectorAll('tr').forEach(tr => {
        const cells = tr.querySelectorAll('td, th');
        if (cells.length >= 2) {
            const label = cleanText(cells[0]);
            const value = cleanText(cells[1]);
            if (label && value && label.length < 150 && value.length < 300 && !value.includes('\\n'))
                pairs[label] = value;
        }
    });

    // Структура 2: dl/dt/dd
    document.querySelectorAll('dl').forEach(dl => {
        const items = dl.querySelectorAll('dt, dd');
        for (let i = 0; i < items.length - 1; i++) {
            if (items[i].tagName === 'DT' && items[i+1].tagName === 'DD') {
                const label = cleanText(items[i]);
                const value = cleanText(items[i+1]);
                if (label && value && value.length < 300 && !value.includes('\\n')) pairs[label] = value;
            }
        }
    });

    // Структура 3: div-пары с классами label/value
    ['[class*="label"]', '[class*="field-name"]', '[class*="prop-name"]'].forEach(sel => {
        document.querySelectorAll(sel).forEach(labelEl => {
            const valueEl = labelEl.nextElementSibling;
            if (valueEl) {
                const label = cleanText(labelEl);
                const value = cleanText(valueEl);
                if (label && value && label.length < 150 && value.length < 300 && !value.includes('\\n'))
                    pairs[label] = value;
            }
        });
    });

    // Секция "Характеристики" — ищем по заголовку
    const headers = document.querySelectorAll('h2, h3, h4, .section-title, .block-title');
    headers.forEach(h => {
        const text = h.innerText.toLowerCase();
        if (text.includes('характеристик') || text.includes('параметр')) {
            const container = h.nextElementSibling;
            if (container) {
                container.querySelectorAll('tr').forEach(tr => {
                    const cells = tr.querySelectorAll('td');
                    if (cells.length >= 2) {
                        const k = cleanText(cells[0]);
                        const v = cleanText(cells[1]);
                        if (k && v && v.length < 300 && !v.includes('\\n')) charSection[k] = v;
                    }
                });
            }
        }
    });

    return { pairs, charSection };
}
"""


class ProjectsService:
    """Парсинг проектов с vitrina.gge.ru"""

    def __init__(self, session: SessionManager):
        self.session = session
        self.config = get_config()
        self.scraper = Scraper(session)
        self.client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> None:
        """Инициализировать HTTP клиент"""
        self.client = httpx.AsyncClient(
            base_url=self.config.vitrina_url,
            timeout=30.0,
        )

    async def close(self) -> None:
        """Закрыть HTTP клиент"""
        if self.client:
            await self.client.aclose()

    async def fetch_list(
        self, limit: int = 100,
        categories: Optional[List[str]] = None,
        regions: Optional[List[str]] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
    ) -> List[Project]:
        """
        Получить список проектов с применением фильтров.

        Если указан диапазон лет (year_from/year_to), использует браузерный поиск
        для фильтрации на стороне сервера. Иначе попытается использовать API.
        """
        effective_categories = categories if categories is not None else self.config.filter_categories
        effective_regions = regions if regions is not None else self.config.filter_regions

        # Если задан диапазон лет, использовать браузерный поиск с фильтрацией
        if year_from or year_to:
            return await self._fetch_with_year_range(
                limit, effective_categories, effective_regions, year_from, year_to
            )

        try:
            # Попробовать получить через API
            token = await self.session.get_api_token()
            if token:
                return await self._fetch_via_api(token, limit, effective_categories, effective_regions)
        except Exception as e:
            logger.warning(f"API fetch failed: {e}, falling back to browser search")

        # Fallback на браузерный поиск (без фильтра по году)
        return await self._fetch_via_browser_search(
            effective_categories, effective_regions, year=None, limit=limit
        )

    async def _fetch_via_api(
        self, token: str, limit: int,
        categories: Optional[List[str]] = None,
        regions: Optional[List[str]] = None,
    ) -> List[Project]:
        """Получить проекты через API"""
        logger.info("Fetching projects via API")

        params = {
            "limit": limit,
            "offset": 0,
        }

        # Добавить фильтры
        if categories:
            params["categories"] = ",".join(categories)
        if regions:
            params["regions"] = ",".join(regions)

        headers = {"Authorization": f"Bearer {token}"}

        try:
            response = await self.client.get(
                "/api/projects",
                params=params,
                headers=headers,
            )
            response.raise_for_status()

            data = response.json()
            projects = []

            for item in data.get("items", []):
                project = Project(
                    vitrina_id=str(item.get("id", "")),
                    expertise_num=item.get("expertise_num"),
                    object_name=item.get("name"),
                    expert_org=item.get("expert_org"),
                    developer=item.get("developer"),
                    tech_customer=item.get("tech_customer"),
                    region=item.get("region"),
                    category=item.get("category"),
                    published_at=item.get("published_at"),
                    updated_at=item.get("updated_at"),
                    url=item.get("url"),
                )
                projects.append(project)

            logger.info(f"Fetched {len(projects)} projects via API")
            return projects

        except httpx.HTTPError as e:
            logger.error(f"API error: {e}")
            raise

    async def _fetch_via_dom(
        self, limit: int = 100,
        categories: Optional[List[str]] = None,
        regions: Optional[List[str]] = None,
    ) -> List[Project]:
        """Получить проекты через POST /projects/search (JSON API)"""
        logger.info("Fetching projects via search API")

        await self.session.ensure_logged_in()
        page = self.session.page

        # Перейти на страницу проектов для инициализации сессии
        try:
            await page.goto(f"{self.config.vitrina_url}/projects/", wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            logger.warning(f"Navigation warning: {e}")

        await page.wait_for_timeout(2000)

        # Данные для поиска (пустой поиск = все проекты)
        search_data = {
            "name": "",
            "function": [],
            "region": [],
            "developer": "",
            "address": "",
            "limit": limit,
            "offset": 0,
        }

        # Добавить фильтры
        if categories:
            search_data["function"] = categories
        if regions:
            search_data["region"] = regions

        try:
            response = await page.request.post(
                f"{self.config.vitrina_url}/projects/search",
                data=search_data
            )

            # Получить JSON ответ
            json_data = await response.json()
            
            # Распарсить JSON для извлечения проектов
            projects = await self._parse_search_json(json_data)
            logger.info(f"Fetched {len(projects)} projects via search API")
            return projects

        except Exception as e:
            logger.error(f"Search API error: {e}")
            # Fallback на парсинг DOM
            return await self._parse_dom_projects()

    async def _parse_search_json(self, json_data: dict) -> List[Project]:
        """Распарсить JSON результаты поиска"""
        projects = []
        
        data = json_data.get("data", [])
        for item in data:
            project_id = item.get("id", "")
            name = item.get("name", "")
            
            project = Project(
                vitrina_id=project_id,
                object_name=name,
                url=f"{self.config.vitrina_url}/projects/{project_id}",
            )
            projects.append(project)
        
        return projects

    async def _parse_dom_projects(self) -> List[Project]:
        """Fallback: распарсить DOM страницы проектов"""
        logger.info("Parsing projects from DOM")

        # Найти таблицу на странице
        table = await self.session.page.query_selector('#projects-table-id, table tbody')
        if not table:
            logger.warning("No projects table found")
            return []

        rows = await self.session.page.query_selector_all('tr')
        projects = []

        for row in rows[1:]:  # Пропустить заголовок
            try:
                link = await row.query_selector('a[href*="/project/"]')
                if link:
                    href = await link.get_attribute('href')
                    text = await link.inner_text()
                    vitrina_id = href.split('/project/')[-1].split('/')[0] if '/project/' in href else ''

                    project = Project(
                        vitrina_id=vitrina_id,
                        object_name=text,
                        url=f"{self.config.vitrina_url}{href}" if href.startswith('/') else href,
                    )
                    projects.append(project)
            except Exception:
                continue

        return projects

    async def _fetch_with_year_range(
        self, limit: int,
        categories: Optional[List[str]],
        regions: Optional[List[str]],
        year_from: Optional[int],
        year_to: Optional[int],
    ) -> List[Project]:
        """
        Получить проекты для диапазона лет через браузерный поиск.

        Если указан диапазон лет, запрашивает каждый год отдельно и объединяет результаты.
        """
        all_projects = {}  # dict для дедупликации по vitrina_id

        # Определить диапазон лет
        year_from = year_from or 2000
        year_to = year_to or datetime.now().year

        logger.info(f"Fetching projects for years {year_from}-{year_to}")

        # Для каждого года отправить отдельный запрос
        for year in range(year_from, year_to + 1):
            logger.info(f"Fetching projects for year {year}")
            try:
                projects = await self._fetch_via_browser_search(
                    categories, regions, year=year, limit=limit
                )
                for project in projects:
                    all_projects[project.vitrina_id] = project
            except Exception as e:
                logger.error(f"Error fetching projects for year {year}: {e}")
                continue

        result = list(all_projects.values())
        logger.info(f"Total projects fetched for years {year_from}-{year_to}: {len(result)}")
        return result

    async def _fetch_via_browser_search(
        self,
        categories: Optional[List[str]],
        regions: Optional[List[str]],
        year: Optional[int],
        limit: int = 100,
    ) -> List[Project]:
        """
        Получить проекты через браузерный поиск с парсингом карточек.

        После отправки формы с фильтрами на странице отображаются карточки проектов.
        Каждую карточку кликают, открывается sidebar с деталями (#object-* элементы),
        извлекаются данные и sidebar закрывается.
        """
        logger.info(f"Fetching projects via browser search (year={year}, categories={categories}, regions={regions})")

        await self.session.ensure_logged_in()
        page = self.session.page

        try:
            # Перейти на страницу поиска
            # Сначала убедимся что мы на главной странице (для правильной инициализации сессии)
            try:
                logger.debug(f"Navigating to {self.config.vitrina_url}/")
                await page.goto(f"{self.config.vitrina_url}/", wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(1000)
            except Exception as e:
                logger.debug(f"Initial navigation note: {e}")

            # Теперь перейти на страницу проектов
            try:
                logger.debug(f"Navigating to {self.config.vitrina_url}/projects/")
                await page.goto(f"{self.config.vitrina_url}/projects/", wait_until="domcontentloaded", timeout=30000)
                logger.debug(f"Navigation complete, current URL: {page.url}")
            except Exception as e:
                logger.warning(f"Projects page navigation: {e}")
                logger.debug(f"Current URL: {page.url}")
                # Пробуем перейти через клик вместо прямой навигации
                try:
                    logger.debug("Trying navigation via link click")
                    await page.click('a[href*="/projects"]', timeout=5000)
                    await page.wait_for_timeout(2000)
                except Exception as e2:
                    logger.warning(f"Link click navigation also failed: {e2}")

            await page.wait_for_timeout(2000)

            # Проверить что мы на странице проектов
            current_url = page.url
            if "/projects" not in current_url:
                logger.warning(f"Expected /projects page but got: {current_url}")

            # Установить фильтры через JS
            if categories:
                logger.debug(f"Setting category filter: {categories}")
                await self._set_slimselect_filter(page, "Категория", categories)
            if regions:
                logger.debug(f"Setting region filter: {regions}")
                await self._set_slimselect_filter(page, "Регион", regions)
            if year:
                logger.debug(f"Setting expertise year: {year}")
                await self._set_expertise_year_input(page, year)

            # Отправить форму
            await self._submit_search_form(page)

            # Парсить карточки из результатов поиска
            projects = await self._parse_cards_from_search_page(page)
            logger.info(f"Fetched {len(projects)} projects via browser search")
            return projects

        except Exception as e:
            logger.error(f"Browser search error: {e}")
            return []

    async def _set_slimselect_filter(
        self, page, filter_name: str, values: List[str]
    ) -> None:
        """
        Установить фильтр SlimSelect по текстовому поиску (по имени и значениям).

        Алгоритм:
        1. Найти .ss-main содержащий текст filter_name (например "Категория" или "Регион")
        2. Кликнуть на него чтобы открыть дропдаун
        3. Для каждого значения найти .ss-option по тексту и кликнуть
        """
        logger.debug(f"Setting {filter_name} filter: {values}")

        try:
            # Найти и кликнуть нужный SS дропдаун по тексту filter_name
            await page.evaluate(f"""
                () => {{
                    const keyword = '{filter_name}'.toLowerCase();
                    const mains = document.querySelectorAll('.ss-main');
                    for (const main of mains) {{
                        const text = main.textContent.toLowerCase();
                        if (text.includes(keyword)) {{
                            main.click();
                            break;
                        }}
                    }}
                }}
            """)
            await page.wait_for_timeout(500)

            # Кликнуть каждую нужную опцию по тексту
            for value in values:
                # Экранируем кавычки в названии
                safe_value = value.replace("'", "\\'")
                await page.evaluate(f"""
                    () => {{
                        const options = document.querySelectorAll('.ss-option');
                        for (const opt of options) {{
                            const text = opt.textContent.trim();
                            if (text.includes('{safe_value}')) {{
                                opt.click();
                                break;
                            }}
                        }}
                    }}
                """)
                await page.wait_for_timeout(100)

        except Exception as e:
            logger.warning(f"Error setting {filter_name} filter: {e}")

    async def _set_expertise_year_input(self, page, year: int) -> None:
        """
        Заполнить поле "Номер заключения экспертизы:" (год в формате ХХХХ).
        Это поле используется для фильтрации по году экспертизы.
        """
        logger.debug(f"Setting expertise year: {year}")

        try:
            await page.evaluate(f"""
                (year) => {{
                    // Поиск input элемента для поля года
                    // Ищем по разным селекторам, которые могут быть на странице
                    const selectors = [
                        'input[name*="year"]',
                        'input[name*="expertise"]',
                        'input[name*="number"]',
                        'input[placeholder*="202"]',  // Примерный год
                        'input[id*="year"]',
                        'input[id*="expertise"]',
                    ];

                    let found = false;
                    for (const selector of selectors) {{
                        const input = document.querySelector(selector);
                        if (input) {{
                            input.value = String(year);
                            input.dispatchEvent(new Event('input', {{bubbles: true}}));
                            input.dispatchEvent(new Event('change', {{bubbles: true}}));
                            found = true;
                            break;
                        }}
                    }}

                    // Fallback: ищем по label текстов
                    if (!found) {{
                        const labels = document.querySelectorAll('label, th, td, dt, span');
                        for (const label of labels) {{
                            const text = label.textContent.toLowerCase();
                            if (text.includes('номер') && (text.includes('заключения') || text.includes('экспертизы'))) {{
                                let input = label.nextElementSibling?.querySelector('input');
                                if (!input) input = label.parentElement?.querySelector('input');
                                if (!input) input = label.querySelector('input');

                                if (input && input.tagName === 'INPUT') {{
                                    input.value = String(year);
                                    input.dispatchEvent(new Event('input', {{bubbles: true}}));
                                    input.dispatchEvent(new Event('change', {{bubbles: true}}));
                                    break;
                                }}
                            }}
                        }}
                    }}
                }}
            """, year)
        except Exception as e:
            logger.warning(f"Error setting expertise year: {e}")

    async def _submit_search_form(self, page) -> None:
        """
        Отправить форму поиска (кликнуть кнопку или нажать Enter).
        """
        logger.debug("Submitting search form")

        try:
            # Попробовать несколько вариантов кнопки поиска
            selectors = [
                "button[type='submit']",
                ".search-button",
                "button.btn-primary",
                "button[name='search']",
                "input[type='submit']",
                "[data-action='search']",
                "button:has-text('Поиск')",
                "button:visible",  # Первая видимая кнопка
                "form button:last-of-type",  # Последняя кнопка в форме
                "form button",  # Любая кнопка в форме
            ]

            logger.debug("Trying button selectors for form submission")
            for selector in selectors:
                try:
                    elements = await page.locator(selector).count()
                    if elements > 0:
                        logger.debug(f"Found {elements} element(s) with selector: {selector}")
                        await page.click(selector, timeout=2000)
                        logger.debug(f"Successfully clicked: {selector}")
                        await page.wait_for_timeout(500)
                        return
                except Exception:
                    logger.debug(f"Selector {selector} failed, trying next")
                    continue

            # Попробовать найти форму и отправить через JavaScript
            logger.debug("Trying JavaScript form submission")
            try:
                await page.evaluate("""
                    () => {
                        const form = document.querySelector('form');
                        if (form) {
                            form.submit();
                        }
                    }
                """)
                await page.wait_for_timeout(500)
                return
            except Exception as e:
                logger.debug(f"JavaScript form submission failed: {e}")

            # Fallback: нажать Enter (может быть что форма в фокусе)
            logger.debug("Using Enter key fallback")
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(500)

        except Exception as e:
            logger.warning(f"Error submitting search form: {e}")

    def _map_labels_to_fields(self, raw_pairs: dict) -> dict:
        """Сопоставить извлечённые пары лейбл-значение с полями проекта"""
        result = {}
        characteristics = {}

        for raw_label, value in raw_pairs.items():
            value_stripped = value.strip()

            # Фильтровать значения "Не выбрано" и аналогичные
            if value_stripped in ("Не выбрано", "Сведения отсутствуют", "-", ""):
                continue

            label_lower = raw_label.lower().strip()
            matched_field = None

            # Точное совпадение
            if label_lower in LABEL_MAPPING:
                matched_field = LABEL_MAPPING[label_lower]
            else:
                # Нечёткое: ключ маппинга как подстрока лейбла
                for key, field in LABEL_MAPPING.items():
                    if key in label_lower:
                        matched_field = field
                        break

            if matched_field:
                if matched_field not in result:  # не перезаписывать более конкретное
                    result[matched_field] = value_stripped
            else:
                characteristics[raw_label] = value_stripped

        result["characteristics"] = characteristics if characteristics else None
        return result

    def _map_by_ids_result(self, data: dict) -> dict:
        """
        Преобразить результат JS_EXTRACT_BY_IDS в формат,
        совместимый с ожиданиями scheduler'а.
        """
        characteristics = {}
        if data.get("characteristics"):
            # Отфильтровать пустые значения
            characteristics = {
                k: v for k, v in data["characteristics"].items()
                if v and v != "Сведения отсутствуют"
            }

        teps = {}
        if data.get("teps"):
            # Отфильтровать пустые значения
            teps = {
                k: v for k, v in data["teps"].items()
                if v and v != "Сведения отсутствуют"
            }

        return {
            "expertise_num": data.get("expertise_num"),
            "object_name": data.get("object_name"),
            "developer": data.get("developer"),
            "region": data.get("region"),
            "category": data.get("category"),
            "vitrina_id": data.get("vitrina_id"),
            "characteristics": characteristics if characteristics else None,
            "teps": teps if teps else None,
        }

    async def _parse_cards_from_search_page(self, page) -> List[Project]:
        """
        Парсить карточки из результатов поиска на странице.

        После отправки формы поиска карточки отображаются на странице.
        При клике на карточку открывается sidebar с #object-* ID элементами.
        Этот метод кликает на каждую карточку, извлекает данные и закрывает sidebar.
        """
        logger.info("Parsing cards from search results page")

        projects = []

        try:
            # Дождаться появления карточек (таймаут 30 сек)
            await page.wait_for_selector('div.uk-card.uk-card-small', timeout=30000)

            # Получить все карточки
            cards = await page.query_selector_all('div.uk-card.uk-card-default.uk-card-small.uk-card-hover')
            logger.info(f"Found {len(cards)} cards on search page")

            if not cards:
                logger.warning("No cards found on search page")
                return projects

            for i, card in enumerate(cards):
                try:
                    # Извлечь ID из атрибута data-src (формат: /projects/ID/image.jpg)
                    data_src = await card.get_attribute("data-src")
                    vitrina_id_from_src = None

                    if data_src and "/projects/" in data_src:
                        # Извлечь ID: /projects/12345/image.jpg → 12345
                        parts = data_src.split("/")
                        for j, part in enumerate(parts):
                            if part == "projects" and j + 1 < len(parts):
                                vitrina_id_from_src = parts[j + 1]
                                break

                    logger.debug(f"Processing card {i + 1}/{len(cards)}, vitrina_id from src: {vitrina_id_from_src}")

                    # Кликнуть на карточку чтобы открыть sidebar
                    await card.click()

                    # Дождаться появления #object-name в sidebar (таймаут 5 сек)
                    try:
                        await page.wait_for_selector("#object-name", timeout=5000)
                    except Exception as e:
                        logger.warning(f"Timeout waiting for sidebar on card {i + 1}: {e}")
                        await page.keyboard.press("Escape")
                        continue

                    await page.wait_for_timeout(500)

                    # Извлечь данные из sidebar
                    raw_data = await page.evaluate(JS_EXTRACT_BY_IDS)
                    logger.debug(f"Raw data from card {i + 1}: {raw_data}")

                    # Мэппировать данные
                    mapped_data = self._map_by_ids_result(raw_data)

                    # Использовать ID из sidebar если есть, иначе из data-src
                    final_vitrina_id = mapped_data.get("vitrina_id") or vitrina_id_from_src
                    if not final_vitrina_id:
                        logger.warning(f"Could not extract vitrina_id from card {i + 1}")
                        await page.keyboard.press("Escape")
                        continue

                    # Создать проект
                    project = Project(
                        vitrina_id=final_vitrina_id,
                        expertise_num=mapped_data.get("expertise_num"),
                        object_name=mapped_data.get("object_name"),
                        developer=mapped_data.get("developer"),
                        region=mapped_data.get("region"),
                        category=mapped_data.get("category"),
                        characteristics=mapped_data.get("characteristics"),
                        url=f"{self.config.vitrina_url}/projects/{final_vitrina_id}",
                    )
                    # Сохранить teps из sidebar как временный атрибут (fallback для полной страницы)
                    project._teps = mapped_data.get("teps")
                    projects.append(project)
                    logger.debug(f"Card {i + 1} parsed: {project.vitrina_id} - {project.object_name}")

                    # Закрыть sidebar (нажать Escape)
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(300)

                except Exception as e:
                    logger.error(f"Error processing card {i + 1}: {e}")
                    try:
                        await page.keyboard.press("Escape")
                    except:
                        pass
                    continue

            logger.info(f"Successfully parsed {len(projects)} projects from search page")
            return projects

        except Exception as e:
            logger.error(f"Error parsing cards from search page: {e}")
            return projects

    async def fetch_details(self, project_url: str) -> Optional[dict]:
        """Получить детали проекта через умный парсинг страницы"""
        try:
            await self.session.goto(project_url)
            # session.goto уже использует wait_until="networkidle"
            # Небольшая задержка для динамически подгружаемых блоков
            await self.session.page.wait_for_timeout(500)

            # Приоритет 1: парсинг по ID (новая структура sidebar)
            raw_data_ids = await self.session.page.evaluate(JS_EXTRACT_BY_IDS)
            logger.debug(f"Raw data from ID parsing for {project_url}: {raw_data_ids}")

            if raw_data_ids.get("object_name") or raw_data_ids.get("vitrina_id"):
                # Успешно извлекли данные через новый метод
                result = self._map_by_ids_result(raw_data_ids)
                logger.debug(f"Details (from IDs) for {project_url}: {list(result.keys())}")
                return result

            # Fallback: парсинг через пары лейбл-значение (старая структура)
            logger.debug(f"ID parsing didn't yield results, trying legacy label parsing for {project_url}")
            raw_data = await self.session.page.evaluate(JS_EXTRACT_PAIRS)

            # DEBUG: показать все найденные лейблы
            all_labels = list(raw_data.get("pairs", {}).keys())
            logger.debug(f"Raw pairs from {project_url}: {all_labels}")

            if not raw_data.get("pairs"):
                logger.warning(f"No label-value pairs found on {project_url}")

            result = self._map_labels_to_fields(raw_data.get("pairs", {}))

            # Добавить данные из секции характеристик
            char_section = raw_data.get("charSection", {})
            if char_section:
                if result.get("characteristics"):
                    result["characteristics"].update(char_section)
                else:
                    result["characteristics"] = char_section

            logger.debug(f"Details (from labels) for {project_url}: {list(result.keys())}")
            return result

        except Exception as e:
            logger.error(f"Error fetching details from {project_url}: {e}")
            return None

    async def filter_by_last_run(
        self, projects: List[Project], last_run_at: Optional[str] = None
    ) -> List[Project]:
        """
        Отфильтровать проекты по дате последнего запуска.

        Остаются только проекты, опубликованные/обновленные
        после последнего успешного запуска.
        """
        if not last_run_at:
            # Если нет последнего запуска, возвращаем все проекты
            return projects

        try:
            cutoff_date = datetime.fromisoformat(last_run_at)
        except ValueError:
            logger.warning(f"Could not parse last_run_at: {last_run_at}")
            return projects

        filtered = []
        for project in projects:
            # Проверяем published_at и updated_at
            date_to_check = project.updated_at or project.published_at
            if date_to_check:
                try:
                    pub_date = datetime.fromisoformat(date_to_check)
                    if pub_date > cutoff_date:
                        filtered.append(project)
                except ValueError:
                    logger.debug(
                        f"Could not parse date: {date_to_check} for project {project.vitrina_id}"
                    )
                    # Если не можем распарсить дату, всё равно добавляем
                    filtered.append(project)
            else:
                # Если даты нет, всё равно добавляем (на всякий случай)
                filtered.append(project)

        logger.info(
            f"Filtered {len(projects)} projects to {len(filtered)} "
            f"(since {last_run_at})"
        )
        return filtered

    def filter_by_expertise_year(
        self, projects: List[Project], year_from: Optional[int] = None,
        year_to: Optional[int] = None
    ) -> List[Project]:
        """
        Отфильтровать проекты по году экспертизы.

        Год извлекается из номера экспертизы (последние цифры).
        Формат: XXXX-...-ГГГГ
        """
        if year_from is None and year_to is None:
            # Фильтр не задан, возвращаем все
            return projects

        filtered = []
        for project in projects:
            if not project.expertise_num:
                # Нет номера экспертизы — пропускаем
                continue

            # Извлекаем год из номера экспертизы (последние цифры после последнего дефиса)
            year = self._extract_year_from_expertise(project.expertise_num)
            if year is None:
                # Не удалось извлечь год — пропускаем
                continue

            # Проверяем диапазон
            if year_from and year < year_from:
                continue
            if year_to and year > year_to:
                continue

            filtered.append(project)

        logger.info(
            f"Filtered {len(projects)} projects to {len(filtered)} "
            f"(expertise years: {year_from or '—'} - {year_to or '—'})"
        )
        return filtered

    def _extract_year_from_expertise(self, expertise_num: str) -> Optional[int]:
        """
        Извлечь год из номера экспертизы.

        Формат номера: 00-0-0-0-000000-2020
        Год — последние цифры после последнего дефиса.
        """
        if not expertise_num:
            return None

        parts = expertise_num.split("-")
        if not parts:
            return None

        year_str = parts[-1].strip()
        try:
            return int(year_str)
        except ValueError:
            logger.debug(f"Could not extract year from expertise number: {expertise_num}")
            return None
