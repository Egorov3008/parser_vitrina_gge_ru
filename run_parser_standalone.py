#!/usr/bin/env python3
"""
Запуск парсера отдельно без бота.

Использование:
    python run_parser_standalone.py
    LOG_LEVEL=DEBUG python run_parser_standalone.py
"""

import asyncio
import sys

from src.browser.session import SessionManager
from src.config import get_config
from src.db.database import Database
from src.db.repository import Repository
from src.services.scheduler import SchedulerService
from src.services.telegram import TelegramService
from src.utils.logger import get_logger, setup_logger

logger = get_logger()


async def main():
    """Инициализировать сервисы и запустить парсер"""
    db = None
    session = None
    telegram = None
    sched = None

    try:
        # Настроить логирование
        setup_logger()
        logger.info("=" * 60)
        logger.info("ЗАПУСК ПАРСЕРА В РЕЖИМЕ STANDALONE")
        logger.info("=" * 60)

        config = get_config()

        # Инициализировать БД
        db = Database(config.db_path)
        db.init_schema()
        db.init_default_settings()
        repository = Repository(db)

        # Мигрировать TELEGRAM_CHAT_ID из .env в таблицу notification_chats
        if config.telegram_chat_id:
            existing_chats = repository.get_all_notification_chats()
            if not existing_chats:
                for chat_id in config.telegram_chat_id.split(","):
                    chat_id = chat_id.strip()
                    if chat_id:
                        repository.add_notification_chat(chat_id, "из .env")
                        logger.info(f"Migrated TELEGRAM_CHAT_ID to notification_chats: {chat_id}")

        # Мигрировать учетные данные из .env в таблицу credentials
        existing_credentials = repository.get_all_credentials()
        if not existing_credentials:
            repository.add_credential(config.vitrina_login, config.vitrina_password, "из .env")
            creds = repository.get_all_credentials()
            if creds:
                repository.set_active_credential(creds[0].id)
            logger.info(f"Migrated credentials from .env: {config.vitrina_login}")

        logger.info("Database initialized")

        # Инициализировать браузер
        session = SessionManager()

        # Установить активную учетку из БД
        active_cred = repository.get_active_credential()
        if active_cred:
            session.set_credentials(active_cred.login, active_cred.password)
            logger.info(f"Using credential from DB: {active_cred.login}")

        await session.initialize()
        logger.info("Browser session initialized")

        # Инициализировать Telegram
        telegram = TelegramService()
        logger.info("Telegram service initialized")

        # Инициализировать планировщик
        sched = SchedulerService(telegram, session, db, repository)
        await sched.initialize()

        # Ограничить количество карточек (0 = все)
        import os
        max_cards = int(os.environ.get("MAX_CARDS", "0"))
        if max_cards > 0:
            sched._max_cards = max_cards
            logger.info(f"Max cards limit: {max_cards}")
        logger.info("Scheduler initialized")

        # Запустить парсер
        logger.info("=" * 60)
        logger.info("ЗАПУСК ПАРСЕРА")
        logger.info("=" * 60)
        await sched.run_immediately()

        logger.info("=" * 60)
        logger.info("ПАРСЕР ЗАВЕРШЕН")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)

    finally:
        # Закрыть сервисы
        try:
            if sched:
                await sched.stop()
                logger.info("Scheduler stopped")
            if session:
                await session.close()
                logger.info("Browser session closed")
            if db:
                db.close()
                logger.info("Database closed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)

        logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
