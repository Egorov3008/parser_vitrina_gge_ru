import asyncio
from typing import Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from src.config import get_config
from src.utils.logger import get_logger

logger = get_logger()


class SessionManager:
    """Управление браузер-сессией (singleton pattern)"""

    _instance: Optional["SessionManager"] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.config = get_config()
        self._pw_context = None
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.api_token: Optional[str] = None
        self.is_logged_in = False

    async def initialize(self) -> None:
        """Инициализировать браузер"""
        if self.browser is not None:
            logger.debug("Browser already initialized")
            return

        try:
            self._pw_context = async_playwright()
            self.playwright = await self._pw_context.__aenter__()
            self.browser = await self.playwright.chromium.launch(
                headless=self.config.headless
            )
            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()

            # Перехватывать API запросы для получения Bearer токена
            self.page.on(
                "response",
                lambda response: asyncio.create_task(
                    self._capture_api_token(response)
                ),
            )

            logger.info("Browser initialized")
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            raise

    async def close(self) -> None:
        """Закрыть браузер"""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self._pw_context:
            await self._pw_context.__aexit__(None, None, None)
        self.is_logged_in = False
        logger.info("Browser closed")

    async def login(self) -> None:
        """Авторизоваться на портале"""
        if self.is_logged_in:
            logger.debug("Already logged in")
            return

        if self.page is None:
            await self.initialize()

        try:
            logger.info(f"Logging in to {self.config.vitrina_url}")

            # Открыть страницу
            await self.page.goto(
                f"{self.config.vitrina_url}/", wait_until="networkidle"
            )

            # Нажать кнопку "Вход" для открытия модального окна
            await self.page.click('a[href="#modal-auth"]', timeout=10000)
            await self.page.wait_for_selector('#modal-auth', state='visible', timeout=5000)

            # Заполнить форму входа
            login_field = await self.page.query_selector('#form-login-text')
            password_field = await self.page.query_selector('#form-passwd-text')
            submit_button = await self.page.query_selector('#login-button-id')

            if not login_field or not password_field or not submit_button:
                logger.warning(
                    "Could not find login form elements. "
                    "DOM selectors may need adjustment."
                )
                await self._try_alternative_login()
                return

            await login_field.fill(self.config.vitrina_login)
            await password_field.fill(self.config.vitrina_password)

            # Нажать кнопку входа
            await submit_button.click()

            # Дождаться закрытия модального окна и загрузки
            await self.page.wait_for_load_state("networkidle", timeout=30000)

            # Проверить успешность входа
            current_url = self.page.url
            if "login" not in current_url.lower() and "modal-auth" not in current_url.lower():
                self.is_logged_in = True
                logger.info("Login successful")
            else:
                raise Exception("Login failed - still on login page")

        except Exception as e:
            logger.error(f"Login error: {e}")
            raise

    async def _try_alternative_login(self) -> None:
        """Попробовать альтернативные селекторы для входа"""
        logger.info("Trying alternative login selectors")

        try:
            # Открыть модальное окно если ещё не открыто
            await self.page.click('a[href="#modal-auth"]', timeout=5000)
            await self.page.wait_for_selector('#modal-auth', state='visible', timeout=5000)

            await self.page.locator('#form-login-text').fill(
                self.config.vitrina_login, timeout=5000
            )
            await self.page.locator('#form-passwd-text').fill(
                self.config.vitrina_password, timeout=5000
            )
            await self.page.locator('#login-button-id').click()

            await self.page.wait_for_load_state("networkidle", timeout=30000)
            self.is_logged_in = True
            logger.info("Alternative login successful")
        except Exception as e:
            logger.error(f"Alternative login also failed: {e}")
            raise

    async def ensure_logged_in(self) -> None:
        """Убедиться, что авторизованы"""
        if not self.is_logged_in:
            await self.login()

    async def _capture_api_token(self, response) -> None:
        """Перехватить Bearer токен из API ответов"""
        if response.status == 401:
            logger.warning("Got 401 response - may need re-authentication")
            self.is_logged_in = False
            return

        try:
            # Получить заголовки запроса
            request = response.request
            auth_header = request.headers.get("Authorization", "")

            if auth_header.startswith("Bearer "):
                self.api_token = auth_header.replace("Bearer ", "")
                logger.debug("API token captured")
        except Exception:
            pass  # Игнорировать ошибки при перехвате токена

    async def get_api_token(self) -> Optional[str]:
        """Получить API токен для direct API запросов"""
        if self.api_token:
            return self.api_token

        # Если токен не был перехвачен, попробовать сделать запрос к API
        try:
            await self.ensure_logged_in()
            # После входа API запросы должны содержать токен
            # Перехват произойдет в _capture_api_token
            response = await self.page.goto(
                f"{self.config.vitrina_url}/api/projects", wait_until="networkidle"
            )
            if response and self.api_token:
                return self.api_token
        except Exception as e:
            logger.debug(f"Could not capture API token: {e}")

        return None

    async def goto(self, url: str):
        """Перейти на страницу"""
        await self.ensure_logged_in()
        return await self.page.goto(url, wait_until="networkidle")
