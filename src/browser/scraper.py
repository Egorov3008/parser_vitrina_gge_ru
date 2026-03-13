from typing import List, Optional

from src.browser.session import SessionManager
from src.utils.logger import get_logger

logger = get_logger()


class Scraper:
    """Вспомогательные методы для парсинга DOM"""

    def __init__(self, session: SessionManager):
        self.session = session

    async def extract_text(self, selector: str) -> Optional[str]:
        """Извлечь текст по селектору"""
        try:
            element = await self.session.page.query_selector(selector)
            if element:
                return await element.text_content()
        except Exception as e:
            logger.debug(f"Error extracting text from {selector}: {e}")
        return None

    async def extract_attr(self, selector: str, attr: str) -> Optional[str]:
        """Извлечь атрибут элемента"""
        try:
            element = await self.session.page.query_selector(selector)
            if element:
                return await element.get_attribute(attr)
        except Exception as e:
            logger.debug(f"Error extracting attribute {attr} from {selector}: {e}")
        return None

    async def extract_all_text(self, selector: str) -> List[str]:
        """Извлечь все тексты по селектору"""
        try:
            elements = await self.session.page.query_selector_all(selector)
            texts = []
            for element in elements:
                text = await element.text_content()
                if text:
                    texts.append(text.strip())
            return texts
        except Exception as e:
            logger.debug(f"Error extracting all text from {selector}: {e}")
            return []

    async def wait_for_element(self, selector: str, timeout: int = 5000) -> bool:
        """Дождаться появления элемента"""
        try:
            await self.session.page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            return False

    async def is_element_visible(self, selector: str) -> bool:
        """Проверить видимость элемента"""
        try:
            element = await self.session.page.query_selector(selector)
            if element:
                return await element.is_visible()
        except Exception:
            pass
        return False
