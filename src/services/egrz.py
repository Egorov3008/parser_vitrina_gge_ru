"""Клиент API ЕГРЗ (egrz.ru) для обогащения данных проектов"""

import asyncio
import ssl
from typing import List, Optional

import httpx

from src.utils.logger import get_logger

logger = get_logger()

EGRZ_API_URL = "https://open-api.egrz.ru/api/PublicRegistrationBook"

EGRZ_SELECT_FIELDS = ",".join([
    "ExpertiseNumber",
    "ExpertiseObjectName",
    "ExpertiseOrganizatioInfo",
    "DeveloperOrganizationInfo",
    "TechnicalCustomerOrganizationInfo",
    "PlannerOrganizationInfo",
    "WorkType",
    "SubjectRf",
    "ExpertiseConclusionDate",
    "ExpertiseResultType",
    "ExpertiseType",
    "ExpertiseDocumentType",
    "ExpertiseObjectAddress",
    "Tpr",
    "TprList",
    "IsTpr",
])

# Маппинг полей API → русские названия
FIELD_MAPPING = {
    "ExpertiseNumber": "Номер заключения",
    "ExpertiseObjectName": "Наименование объекта",
    "ExpertiseOrganizatioInfo": "Экспертная организация",
    "DeveloperOrganizationInfo": "Застройщик",
    "TechnicalCustomerOrganizationInfo": "Технический заказчик",
    "PlannerOrganizationInfo": "Проектировщик",
    "ExpertiseResultType": "Результат экспертизы",
    "ExpertiseType": "Вид экспертизы",
    "ExpertiseConclusionDate": "Дата заключения",
    "ExpertiseObjectAddress": "Адрес объекта",
    "WorkType": "Вид работ",
    "ExpertiseDocumentType": "Тип документа",
    "SubjectRf": "Субъект РФ",
    "TprList": "ТЭП",
    "IsTpr": "Наличие ТЭП",
}


class EgrzService:
    """Сервис для запросов к публичному OData API ЕГРЗ"""

    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> None:
        """Инициализировать HTTP клиент"""
        # ЕГРЗ использует legacy SSL renegotiation
        ssl_context = ssl.create_default_context()
        ssl_context.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
        self.client = httpx.AsyncClient(timeout=30.0, verify=ssl_context)
        logger.info("EGRZ service initialized")

    async def close(self) -> None:
        """Закрыть HTTP клиент"""
        if self.client:
            await self.client.aclose()
            logger.info("EGRZ service closed")

    def _parse_response(self, item: dict) -> dict:
        """Маппинг полей API-ответа в русские названия"""
        result = {}
        for api_field, ru_name in FIELD_MAPPING.items():
            value = item.get(api_field)
            if value is not None and value != "" and value != []:
                result[ru_name] = value
        return result

    async def fetch_by_number(self, expertise_num: str) -> Optional[dict]:
        """Запросить данные по номеру экспертизы из ЕГРЗ API"""
        if not self.client:
            logger.warning("EGRZ client not initialized")
            return None

        try:
            params = {
                "$filter": f"ExpertiseNumber eq '{expertise_num}'",
                "$select": EGRZ_SELECT_FIELDS,
            }
            response = await self.client.get(EGRZ_API_URL, params=params)
            response.raise_for_status()

            data = response.json()
            items = data.get("value", [])

            if not items:
                logger.debug(f"EGRZ: no results for {expertise_num}")
                return None

            parsed = self._parse_response(items[0])
            logger.debug(f"EGRZ: found data for {expertise_num}: {len(parsed)} fields")
            return parsed

        except httpx.HTTPStatusError as e:
            logger.warning(f"EGRZ API HTTP error for {expertise_num}: {e.response.status_code}")
            return None
        except Exception as e:
            logger.warning(f"EGRZ API error for {expertise_num}: {e}")
            return None

    async def fetch_all(self, expertise_nums: List[str]) -> List[dict]:
        """Запросить данные по всем номерам экспертиз с задержкой между запросами"""
        results = []
        for num in expertise_nums:
            result = await self.fetch_by_number(num)
            if result:
                results.append(result)
            # Задержка между запросами
            if num != expertise_nums[-1]:
                await asyncio.sleep(0.5)
        return results
