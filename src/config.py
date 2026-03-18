from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Конфигурация приложения из .env"""

    # Портал витрины
    vitrina_url: str = "https://vitrina.gge.ru"
    vitrina_login: str
    vitrina_password: str

    # Telegram
    telegram_bot_token: str
    telegram_chat_id: str = None

    # Расписание
    cron_schedule: str = "0 6 * * *"

    # БД
    db_path: str = "./data/vitrina.db"

    # Запуск
    run_on_start: bool = False

    # Браузер
    headless: bool = Field(default=True, alias="HEADLESS")

    # Администраторы
    admin_id: str = ""

    # Логирование
    log_level: str = "INFO"
    log_dir: str = "./logs"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

    @classmethod
    def from_env(cls) -> "Settings":
        """Загрузить конфиг из .env"""
        import os

        load_dotenv()

        # Парсить булевы значения
        headless_str = os.getenv("HEADLESS", "true").lower()
        headless = headless_str in ("true", "1", "yes")

        run_on_start_str = os.getenv("RUN_ON_START", "false").lower()
        run_on_start = run_on_start_str in ("true", "1", "yes")

        # Парсить список админов
        admin_id_str = os.getenv("ADMIN_ID", "")
        admin_ids = [x.strip() for x in admin_id_str.split(",") if x.strip()]

        # Создать экземпляр с переопределением
        instance = cls(
            headless=headless,
            run_on_start=run_on_start,
        )
        instance.admin_id = ",".join(admin_ids)
        return instance

    def get_admin_ids(self) -> list[str]:
        """Получить список ID администраторов"""
        if not self.admin_id:
            return []
        return [x.strip() for x in self.admin_id.split(",") if x.strip()]


def get_config() -> Settings:
    """Получить глобальный экземпляр конфига"""
    return Settings.from_env()
