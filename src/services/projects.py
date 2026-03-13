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
    "экспертная организация": "expert_org",
    "орган экспертизы": "expert_org",
    "застройщик": "developer",
    "технический заказчик": "tech_customer",
    "техзаказчик": "tech_customer",
    "регион": "region",
    "субъект": "region",
    "категория": "category",
    "функциональное назначение": "category",
    "наименование объекта": "object_name",
    "наименование": "object_name",
    "объект капитального строительства": "object_name",
}

# JS-код для извлечения всех пар лейбл-значение + секции характеристик
JS_EXTRACT_PAIRS = """
() => {
    const pairs = {};
    const charSection = {};

    // Структура 1: таблицы <tr><td>Лейбл</td><td>Значение</td></tr>
    document.querySelectorAll('tr').forEach(tr => {
        const cells = tr.querySelectorAll('td, th');
        if (cells.length >= 2) {
            const label = cells[0].innerText.trim();
            const value = cells[1].innerText.trim();
            if (label && value && label.length < 150) pairs[label] = value;
        }
    });

    // Структура 2: dl/dt/dd
    document.querySelectorAll('dl').forEach(dl => {
        const items = dl.querySelectorAll('dt, dd');
        for (let i = 0; i < items.length - 1; i++) {
            if (items[i].tagName === 'DT' && items[i+1].tagName === 'DD') {
                const label = items[i].innerText.trim();
                const value = items[i+1].innerText.trim();
                if (label && value) pairs[label] = value;
            }
        }
    });

    // Структура 3: div-пары с классами label/value
    ['[class*="label"]', '[class*="field-name"]', '[class*="prop-name"]'].forEach(sel => {
        document.querySelectorAll(sel).forEach(labelEl => {
            const valueEl = labelEl.nextElementSibling;
            if (valueEl) {
                const label = labelEl.innerText.trim();
                const value = valueEl.innerText.trim();
                if (label && value && label.length < 150) pairs[label] = value;
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
                        const k = cells[0].innerText.trim();
                        const v = cells[1].innerText.trim();
                        if (k && v) charSection[k] = v;
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

    async def fetch_list(self, limit: int = 100) -> List[Project]:
        """
        Получить список проектов с применением фильтров.

        Попытается использовать API, если доступен, иначе парсит DOM.
        """
        try:
            # Попробовать получить через API
            token = await self.session.get_api_token()
            if token:
                return await self._fetch_via_api(token, limit)
        except Exception as e:
            logger.warning(f"API fetch failed: {e}, falling back to DOM parsing")

        # Fallback на DOM парсинг
        return await self._fetch_via_dom(limit)

    async def _fetch_via_api(self, token: str, limit: int) -> List[Project]:
        """Получить проекты через API"""
        logger.info("Fetching projects via API")

        params = {
            "limit": limit,
            "offset": 0,
        }

        # Добавить фильтры
        if self.config.filter_categories:
            params["categories"] = ",".join(self.config.filter_categories)
        if self.config.filter_regions:
            params["regions"] = ",".join(self.config.filter_regions)

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

    async def _fetch_via_dom(self, limit: int = 100) -> List[Project]:
        """Получить проекты через POST /projects/search (JSON API)"""
        logger.info("Fetching projects via search API")

        await self.session.ensure_logged_in()

        # Перейти на страницу проектов для инициализации сессии
        await self.session.goto(f"{self.config.vitrina_url}/projects/")
        await self.session.page.wait_for_timeout(2000)

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
        if self.config.filter_categories:
            search_data["function"] = self.config.filter_categories
        if self.config.filter_regions:
            search_data["region"] = self.config.filter_regions

        try:
            response = await self.session.page.request.post(
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

    def _map_labels_to_fields(self, raw_pairs: dict) -> dict:
        """Сопоставить извлечённые пары лейбл-значение с полями проекта"""
        result = {}
        characteristics = {}

        for raw_label, value in raw_pairs.items():
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
                    result[matched_field] = value.strip()
            else:
                characteristics[raw_label] = value.strip()

        result["characteristics"] = characteristics if characteristics else None
        return result

    async def fetch_details(self, project_url: str) -> Optional[dict]:
        """Получить детали проекта через умный парсинг страницы"""
        try:
            await self.session.goto(project_url)
            # session.goto уже использует wait_until="networkidle"
            # Небольшая задержка для динамически подгружаемых блоков
            await self.session.page.wait_for_timeout(500)

            raw_data = await self.session.page.evaluate(JS_EXTRACT_PAIRS)

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

            logger.debug(f"Details for {project_url}: {list(result.keys())}")
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
