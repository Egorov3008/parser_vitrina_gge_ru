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
        expertise_links: [],
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
            const href = link.href || '';
            if (text) {
                result.expertise_nums.push(text);
                if (href) {
                    result.expertise_links.push({num: text, url: href});
                }
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
        max_cards: int = 0,
        expertise_years: Optional[List[int]] = None,
    ) -> List[Project]:
        """
        Получить список проектов с применением серверных фильтров (категория, регион, год экспертизы).

        Когда expertise_years указан, API пропускается (не поддерживает этот фильтр)
        и используется браузерный поиск с полем #filter-conclusion-text-id.

        Фильтры categories/regions передаются явно из scheduler (берутся из БД).
        """
        effective_categories = categories if categories is not None else []
        effective_regions = regions if regions is not None else []

        # Если указаны годы экспертизы — сразу идём в браузерный поиск (API не поддерживает этот фильтр)
        if expertise_years:
            logger.info(f"Using browser search (expertise_years={expertise_years}), categories={effective_categories}, regions={effective_regions}")
            return await self._fetch_via_browser_search(
                effective_categories, effective_regions, limit=limit, max_cards=max_cards,
                expertise_years=expertise_years,
            )

        try:
            # Попробовать получить через API
            token = await self.session.get_api_token()
            if token:
                logger.info(f"Using API with token, categories={effective_categories}, regions={effective_regions}")
                return await self._fetch_via_api(token, limit, effective_categories, effective_regions)
        except Exception as e:
            logger.warning(f"API fetch failed: {e}, falling back to browser search")

        # Fallback на браузерный поиск
        logger.info(f"Using browser search, categories={effective_categories}, regions={effective_regions}")
        return await self._fetch_via_browser_search(
            effective_categories, effective_regions, limit=limit, max_cards=max_cards
        )

    async def _fetch_via_api(
        self, token: str, limit: int,
        categories: Optional[List[str]] = None,
        regions: Optional[List[str]] = None,
    ) -> List[Project]:
        """Получить проекты через API"""
        logger.info(f"Fetching projects via API: categories={categories}, regions={regions}")

        params = {
            "limit": limit,
            "offset": 0,
        }

        # Добавить фильтры
        if categories:
            params["categories"] = ",".join(categories)
        if regions:
            params["regions"] = ",".join(regions)

        logger.info(f"API request params: {params}")

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

    async def _fetch_via_browser_search(
        self,
        categories: Optional[List[str]],
        regions: Optional[List[str]],
        limit: int = 100,
        max_cards: int = 0,
        expertise_years: Optional[List[int]] = None,
    ) -> List[Project]:
        """
        Получить проекты через браузерный поиск с парсингом карточек.

        После отправки формы с фильтрами на странице отображаются карточки проектов.
        Каждую карточку кликают, открывается sidebar с деталями (#object-* элементы),
        извлекаются данные и sidebar закрывается.
        """
        logger.info(f"Fetching projects via browser search (categories={categories}, regions={regions}, expertise_years={expertise_years})")

        await self.session.ensure_logged_in()
        page = self.session.page

        # Если указаны годы экспертизы — итерируем по каждому году отдельно
        if expertise_years:
            all_projects = []
            seen_ids = set()
            for year in expertise_years:
                logger.info(f"Fetching projects for expertise year {year}")
                try:
                    year_projects = await self._fetch_browser_search_single(
                        page, categories, regions, max_cards=max_cards,
                        expertise_year=str(year),
                    )
                    # Дедупликация по vitrina_id
                    for p in year_projects:
                        if p.vitrina_id not in seen_ids:
                            seen_ids.add(p.vitrina_id)
                            all_projects.append(p)
                    logger.info(f"Year {year}: {len(year_projects)} cards, {len(all_projects)} unique total")
                except Exception as e:
                    logger.error(f"Error fetching year {year}: {e}")
                    continue
            logger.info(f"Fetched {len(all_projects)} unique projects via browser search (years: {expertise_years})")
            return all_projects

        # Без фильтра по году — обычный одиночный запрос
        try:
            projects = await self._fetch_browser_search_single(
                page, categories, regions, max_cards=max_cards,
            )
            logger.info(f"Fetched {len(projects)} projects via browser search")
            return projects
        except Exception as e:
            logger.error(f"Browser search error: {e}")
            return []

    async def _fetch_browser_search_single(
        self,
        page,
        categories: Optional[List[str]],
        regions: Optional[List[str]],
        max_cards: int = 0,
        expertise_year: Optional[str] = None,
    ) -> List[Project]:
        """
        Выполнить один поиск в браузере (с опциональным фильтром по году экспертизы).

        Навигирует на /projects/, устанавливает фильтры, отправляет форму и парсит карточки.
        """
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
                # Переходим на чистую страницу проектов без фильтров
                await page.goto(f"{self.config.vitrina_url}/projects/", wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(2000)
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

            # Сбросить существующие фильтры перед установкой новых
            logger.debug("Resetting existing filters")
            await self._reset_filters(page)

            # Установить фильтры через ID элементов
            if categories:
                logger.debug(f"Setting category filter: {categories}")
                await self._set_filter_by_select_id(page, "filter-function-select-id", categories)
            if regions:
                logger.debug(f"Setting region filter: {regions}")
                await self._set_filter_by_select_id(page, "filter-region-select-id", regions)

            # Установить фильтр по году экспертизы (если указан)
            if expertise_year:
                await self._set_expertise_year_filter(page, expertise_year)

            # Отправить форму (расширенный поиск если есть год, обычный иначе)
            if expertise_year:
                await self._submit_advanced_search_form(page)
            else:
                await self._submit_search_form(page)

            # Дождаться обновления URL или появления индикатора загрузки
            await page.wait_for_timeout(3000)
            logger.info(f"Current URL after search: {page.url}")

            # Проверить что фильтры применены - посмотреть на selected options
            cat_selected = await page.evaluate("""
                () => {
                    const sel = document.querySelector('#filter-function-select-id');
                    return sel ? Array.from(sel.selectedOptions).map(o => o.text) : [];
                }
            """)
            reg_selected = await page.evaluate("""
                () => {
                    const sel = document.querySelector('#filter-region-select-id');
                    return sel ? Array.from(sel.selectedOptions).map(o => o.text) : [];
                }
            """)
            logger.info(f"Active filters - Category: {cat_selected}, Region: {reg_selected}" +
                        (f", Expertise year: {expertise_year}" if expertise_year else ""))

            # Парсить карточки из результатов поиска
            try:
                projects = await self._parse_cards_from_search_page(page, max_cards=max_cards)
            except Exception as e:
                logger.warning(f"No cards found for search (expertise_year={expertise_year}): {e}")
                projects = []
            return projects

        except Exception as e:
            logger.error(f"Browser search error (expertise_year={expertise_year}): {e}")
            return []

    async def _set_expertise_year_filter(self, page, year_str: str) -> None:
        """Fill #filter-conclusion-text-id with year value for server-side filtering.

        The input lives inside a UIkit accordion panel that is collapsed by default.
        We must expand it before filling.
        """
        selector = '#filter-conclusion-text-id'

        # Step 1: Expand the advanced-search accordion so the input becomes visible
        expanded = await self._expand_advanced_search_accordion(page)
        if not expanded:
            logger.warning("Could not confirm accordion expanded; will attempt fill anyway")

        # Step 2: Wait for the input to become visible
        try:
            await page.wait_for_selector(selector, state='visible', timeout=3000)
        except Exception:
            logger.debug(f"wait_for_selector visible timed out for {selector}, proceeding")

        # Step 3: Fill the value
        try:
            await page.fill(selector, "")
            await page.fill(selector, year_str)
            logger.debug(f"Set expertise conclusion filter to: {year_str}")
        except Exception as e:
            logger.warning(f"Could not set expertise year filter: {e}")

    async def _expand_advanced_search_accordion(self, page) -> bool:
        """Expand the advanced-search UIkit accordion so hidden inputs become visible.

        Tries: UIkit JS API → click accordion title → direct DOM unhide.
        """
        # Check if already open
        already_open = await page.evaluate("""
            () => {
                const input = document.querySelector('#filter-conclusion-text-id');
                if (!input) return false;
                let el = input;
                while (el && !el.classList.contains('uk-accordion-content')) {
                    el = el.parentElement;
                }
                if (!el) return false;
                return !el.hasAttribute('hidden') && el.offsetParent !== null;
            }
        """)
        if already_open:
            logger.debug("Advanced search accordion already open")
            return True

        # Strategy 1: UIkit JS API
        try:
            toggled = await page.evaluate("""
                () => {
                    const input = document.querySelector('#filter-conclusion-text-id');
                    if (!input) return false;
                    let panel = input;
                    while (panel && !panel.classList.contains('uk-accordion-content')) {
                        panel = panel.parentElement;
                    }
                    if (!panel) return false;
                    const item = panel.parentElement;
                    if (!item) return false;
                    let accordionEl = item.parentElement;
                    while (accordionEl && !accordionEl.hasAttribute('uk-accordion')) {
                        accordionEl = accordionEl.parentElement;
                    }
                    if (!accordionEl || !window.UIkit) return false;
                    const accordion = UIkit.accordion(accordionEl);
                    const items = Array.from(accordionEl.children);
                    const idx = items.indexOf(item);
                    if (idx >= 0) {
                        accordion.toggle(idx, true);
                        return true;
                    }
                    return false;
                }
            """)
            if toggled:
                await page.wait_for_timeout(500)
                logger.debug("Expanded accordion via UIkit JS API")
                return True
        except Exception as e:
            logger.debug(f"UIkit API accordion toggle failed: {e}")

        # Strategy 2: Click the accordion title via JS
        try:
            title_clicked = await page.evaluate("""
                () => {
                    const input = document.querySelector('#filter-conclusion-text-id');
                    if (!input) return false;
                    let el = input;
                    while (el && el.tagName !== 'LI') {
                        el = el.parentElement;
                    }
                    if (!el) return false;
                    const title = el.querySelector('.uk-accordion-title, [uk-accordion-title]');
                    if (title) { title.click(); return true; }
                    return false;
                }
            """)
            if title_clicked:
                await page.wait_for_timeout(500)
                logger.debug("Expanded accordion via title click (JS)")
                return True
        except Exception as e:
            logger.debug(f"JS title click failed: {e}")

        # Strategy 2b: Playwright click on accordion title by text
        for text_pattern in ["Расширенный поиск", "Дополнительные параметры", "Расширенный"]:
            try:
                title_loc = page.locator(
                    f'.uk-accordion-title:has-text("{text_pattern}"), '
                    f'a[uk-accordion-title]:has-text("{text_pattern}")'
                )
                if await title_loc.count() > 0:
                    await title_loc.first.click()
                    await page.wait_for_timeout(500)
                    logger.debug(f"Expanded accordion via Playwright click on title: {text_pattern}")
                    return True
            except Exception as e:
                logger.debug(f"Playwright title click ({text_pattern}) failed: {e}")

        # Strategy 3: Direct DOM manipulation — remove 'hidden', add 'uk-open'
        try:
            forced = await page.evaluate("""
                () => {
                    const input = document.querySelector('#filter-conclusion-text-id');
                    if (!input) return false;
                    let panel = input;
                    while (panel && !panel.classList.contains('uk-accordion-content')) {
                        panel = panel.parentElement;
                    }
                    if (!panel) return false;
                    panel.removeAttribute('hidden');
                    panel.style.display = '';
                    const item = panel.parentElement;
                    if (item) item.classList.add('uk-open');
                    return true;
                }
            """)
            if forced:
                await page.wait_for_timeout(200)
                logger.debug("Expanded accordion via direct DOM manipulation (fallback)")
                return True
        except Exception as e:
            logger.debug(f"Direct DOM accordion expansion failed: {e}")

        logger.warning("All accordion expansion strategies failed for advanced search")
        return False

    async def _submit_advanced_search_form(self, page) -> None:
        """Submit the advanced search form by clicking #set-filter-advanced-button-id."""
        logger.debug("Submitting advanced search form via #set-filter-advanced-button-id")
        btn_selector = '#set-filter-advanced-button-id'
        try:
            await page.wait_for_selector(btn_selector, state='visible', timeout=3000)
            await page.click(btn_selector, timeout=5000)
            logger.debug("Successfully clicked #set-filter-advanced-button-id")
            await page.wait_for_timeout(2000)
        except Exception as e:
            logger.warning(f"Error clicking #set-filter-advanced-button-id: {e}, falling back to regular search")
            await self._submit_search_form(page)

    async def _set_filter_by_select_id(
        self, page, select_id: str, values: List[str]
    ) -> None:
        """
        Установить фильтр SlimSelect по ID базового <select> элемента.

        Использует Playwright .click() вместо JS evaluate для корректной
        эмуляции пользовательских кликов (mousedown → mouseup → click),
        что необходимо для активации обработчиков SlimSelect.
        """
        logger.debug(f"Setting filter by select #{select_id}: {values}")

        try:
            # Найти SlimSelect .ss-main через JS — он может быть на любом уровне DOM
            # SlimSelect хранит ссылку на экземпляр в свойстве .slim оригинального <select>
            ss_main_handle = await page.evaluate_handle(f"""
                () => {{
                    const select = document.querySelector('#{select_id}');
                    if (!select) return null;
                    // Вариант 1: .ss-main как sibling <select> в родителе
                    const parent = select.parentElement;
                    if (parent) {{
                        const ssMain = parent.querySelector('.ss-main');
                        if (ssMain) return ssMain;
                    }}
                    // Вариант 2: SlimSelect хранит data-id, ищем по нему
                    const ssId = select.dataset.ssid || select.id;
                    const allMains = document.querySelectorAll('.ss-main');
                    for (const m of allMains) {{
                        // Проверяем что .ss-main следует сразу за нашим select
                        if (m.previousElementSibling === select) return m;
                    }}
                    // Вариант 3: вернуть первый найденный в родителе
                    return null;
                }}
            """)

            # Преобразовать JSHandle в ElementHandle
            ss_main_el = ss_main_handle.as_element()
            if not ss_main_el:
                logger.warning(f"Could not find SlimSelect .ss-main for #{select_id}")
                return

            # Открыть дропдаун реальным кликом Playwright
            await ss_main_el.click()
            await page.wait_for_timeout(500)

            # Проверить что дропдаун открылся — ищем .ss-content.ss-open глобально
            ss_content_open = page.locator('.ss-content.ss-open')
            if await ss_content_open.count() == 0:
                # Попробовать ещё раз: иногда класс ss-open-below / ss-open-above
                ss_content_open = page.locator('.ss-content.ss-open-below, .ss-content.ss-open-above')

            if await ss_content_open.count() == 0:
                logger.warning(f"SlimSelect dropdown did not open for #{select_id}, trying click again")
                await ss_main_el.click()
                await page.wait_for_timeout(800)

            # Кликнуть каждую нужную опцию по тексту
            for value in values:
                # Искать опции внутри видимого дропдауна
                option = page.locator('.ss-option:not(.ss-disabled)').filter(has_text=value)
                option_count = await option.count()

                if option_count == 0:
                    logger.warning(f"  Option not found: {value}")
                    continue

                # Если найдено несколько — выбрать точное совпадение
                clicked = False
                for idx in range(option_count):
                    opt = option.nth(idx)
                    text = (await opt.text_content()).strip()
                    if text == value:
                        await opt.click()
                        clicked = True
                        logger.debug(f"  Selected option (exact): {value}")
                        break

                # Fallback: кликнуть первый частичный вариант
                if not clicked:
                    await option.first.click()
                    first_text = (await option.first.text_content()).strip()
                    logger.debug(f"  Selected option (partial): {first_text}")

                await page.wait_for_timeout(300)

            # Закрыть дропдаун
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(300)

            # Проверить что фильтр установлен — проверить оригинальный <select>
            selected_values = await page.evaluate(f"""
                () => {{
                    const select = document.querySelector('#{select_id}');
                    if (!select) return [];
                    return Array.from(select.selectedOptions).map(opt => opt.value);
                }}
            """)
            logger.debug(f"  Selected values in <select>: {selected_values}")

        except Exception as e:
            logger.warning(f"Error setting filter #{select_id}: {e}")

    async def _reset_filters(self, page) -> None:
        """
        Сбросить все фильтры на странице проектов.

        Кликает кнопку "Сбросить" если она есть, или перезагружает страницу.
        """
        try:
            # Попробовать найти и кликнуть кнопку "Сбросить" / "Reset"
            reset_button = page.locator(
                'button:has-text("Сбросить"), button:has-text("Reset"), '
                'a:has-text("Сбросить"), .reset-btn, #reset-btn'
            )
            if await reset_button.count() > 0:
                await reset_button.first.click()
                await page.wait_for_timeout(500)
                logger.debug("Filters reset via button")
            else:
                # Fallback: перезагрузить страницу
                logger.debug("Reset button not found, reloading page")
        except Exception as e:
            logger.debug(f"Could not reset filters: {e}")

    async def _submit_search_form(self, page) -> None:
        """Отправить форму поиска — кликнуть кнопку #search-button-id"""
        logger.debug("Submitting search form via #search-button-id")

        try:
            await page.click('#search-button-id', timeout=5000)
            logger.debug("Successfully clicked #search-button-id")
            await page.wait_for_timeout(2000)
        except Exception as e:
            logger.warning(f"Error clicking #search-button-id: {e}, trying fallback")
            try:
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(2000)
            except Exception as e2:
                logger.warning(f"Fallback Enter also failed: {e2}")

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
            "expertise_nums": data.get("expertise_nums", []),
            "expertise_links": data.get("expertise_links", []),
        }

    async def _parse_cards_from_search_page(self, page, max_cards: int = 0) -> List[Project]:
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

            # Проверить сколько карточек видно сразу
            initial_cards = await page.query_selector_all('div.uk-card.uk-card-default.uk-card-small.uk-card-hover')
            logger.info(f"Initial cards visible: {len(initial_cards)}")
            
            # Проверить наличие кнопки "Показать ещё"
            show_more_button = page.locator('button#button-show-more')
            show_more_count = await show_more_button.count()
            logger.info(f"Show more button found: {show_more_count > 0}")
            if show_more_count > 0:
                more_attr = await show_more_button.first.get_attribute('more')
                logger.info(f"Show more button 'more' attribute: {more_attr}")
                more_text = await show_more_button.first.text_content()
                logger.info(f"Show more button text: {more_text.strip()}")

            # Загрузить карточки кликая "показать ещё"
            # При max_cards > 0 пропускаем пагинацию — хватит первой страницы
            load_more_clicks = 0
            if max_cards == 0:
                prev_card_count = 0
                max_attempts = 50  # Максимум 50 попыток загрузки
                attempt = 0
                
                while attempt < max_attempts:
                    attempt += 1
                    show_more = page.locator('button#button-show-more')
                    if await show_more.count() == 0:
                        logger.info("Show more button not found, stopping pagination")
                        break
                    
                    # Проверить видима ли кнопка
                    is_visible = await show_more.first.is_visible()
                    
                    # Кликать если кнопка видима (независимо от атрибута more)
                    more_text = await show_more.first.text_content()
                    
                    if 'показать ещё' not in more_text.lower() and 'show more' not in more_text.lower():
                        logger.info(f"Show more button text changed: '{more_text.strip()}', stopping")
                        break
                    
                    # Прокрутить к кнопке перед кликом
                    try:
                        await show_more.first.scroll_into_view_if_needed(timeout=5000)
                        await page.wait_for_timeout(500)
                        
                        # Попробовать обычный клик
                        try:
                            await show_more.first.click(timeout=5000)
                        except Exception:
                            # Fallback: JavaScript клик (для невидимых элементов)
                            logger.debug("Regular click failed, trying JS click")
                            await page.evaluate("""
                                () => {
                                    const btn = document.querySelector('button#button-show-more');
                                    if (btn) btn.click();
                                }
                            """)
                        
                        load_more_clicks += 1
                        logger.info(f"Clicked 'показать ещё' #{load_more_clicks}")
                        
                        # Ждать дольше после клика
                        await page.wait_for_timeout(5000)
                    except Exception as e:
                        logger.debug(f"Could not click show more: {e}")
                        # Fallback: прокрутить страницу вниз для lazy loading
                        logger.debug("Trying scroll down for lazy loading")
                        await page.evaluate("window.scrollBy(0, window.innerHeight)")
                        await page.wait_for_timeout(5000)
                    
                    # Проверить что карточек стало больше — иначе прекратить
                    current_cards = await page.query_selector_all('div.uk-card.uk-card-default.uk-card-small.uk-card-hover')
                    current_count = len(current_cards)
                    logger.info(f"After attempt #{attempt}: {current_count} cards (prev: {prev_card_count})")
                    if current_count <= prev_card_count:
                        logger.info(f"No new cards loaded after click #{load_more_clicks}, stopping pagination")
                        break
                    prev_card_count = current_count
                    
                    # Небольшая пауза между кликами
                    await page.wait_for_timeout(1000)
            else:
                logger.debug(f"Skipping pagination (max_cards={max_cards})")

            if load_more_clicks > 0:
                logger.info(f"Loaded all cards after {load_more_clicks} 'показать ещё' clicks")

            # Получить все карточки
            cards = await page.query_selector_all('div.uk-card.uk-card-default.uk-card-small.uk-card-hover')
            logger.info(f"Found {len(cards)} cards on search page")

            if not cards:
                logger.warning("No cards found on search page")
                return projects

            cards_to_process = cards[:max_cards] if max_cards > 0 else cards
            if max_cards > 0:
                logger.info(f"Limiting to {max_cards} cards (of {len(cards)} total)")

            for i, card in enumerate(cards_to_process):
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

                    # Логирование структуры найденных полей
                    found_fields = {k: v for k, v in mapped_data.items() if v and k != "characteristics"}
                    missing_fields = [k for k, v in mapped_data.items() if not v and k != "characteristics"]
                    logger.debug(f"  Карточка {i + 1}: найдено полей={len(found_fields)}, пустых={len(missing_fields)}")
                    if missing_fields:
                        logger.debug(f"    Пустые поля: {missing_fields}")

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
                    # Сохранить teps, expertise_nums и expertise_links из sidebar как временные атрибуты
                    project._teps = mapped_data.get("teps")
                    project._expertise_nums = mapped_data.get("expertise_nums", [])
                    project._expertise_links = mapped_data.get("expertise_links", [])
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
                phase1_fields = {k: v for k, v in raw_data_ids.items() if v and k != "characteristics"}
                characteristics_count = len(result.get("characteristics") or {})
                logger.debug(f"  fetch_details {project_url}:")
                logger.debug(f"    Фаза 1 (ID-based): {len(phase1_fields)} полей — {list(phase1_fields.keys())}")
                logger.debug(f"    Characteristics: {characteristics_count} доп. полей")
                logger.debug(f"Details (from IDs) for {project_url}: {list(result.keys())}")
                return result

            # Fallback: парсинг через пары лейбл-значение (старая структура)
            logger.debug(f"ID parsing didn't yield results, trying legacy label parsing for {project_url}")
            raw_data = await self.session.page.evaluate(JS_EXTRACT_PAIRS)

            # DEBUG: показать все найденные лейблы
            all_labels = list(raw_data.get("pairs", {}).keys())
            pairs_count = len(raw_data.get("pairs", {}))
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

            characteristics_count = len(result.get("characteristics") or {})
            logger.debug(f"  fetch_details {project_url}:")
            logger.debug(f"    Фаза 2 (label-pairs): {pairs_count} пар найдено")
            logger.debug(f"    Characteristics: {characteristics_count} доп. полей")
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
                        logger.debug(f"  ОСТАВЛЕН: {project.vitrina_id} ({date_to_check})")
                    else:
                        logger.debug(f"  ОТСЕЯН по дате: {project.vitrina_id} ({date_to_check}) < {last_run_at}")
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
        self, projects: List[Project], expertise_year: Optional[int] = None
    ) -> List[Project]:
        """
        Отфильтровать проекты по году экспертизы.

        Год извлекается из номера экспертизы (последние цифры).
        Формат: XXXX-...-ГГГГ
        """
        if expertise_year is None:
            return projects

        filtered = []
        for project in projects:
            if not project.expertise_num:
                continue

            year = self._extract_year_from_expertise(project.expertise_num)
            if year is None:
                continue

            if year == expertise_year:
                filtered.append(project)

        logger.info(
            f"Filtered {len(projects)} projects to {len(filtered)} "
            f"(expertise year: {expertise_year})"
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
