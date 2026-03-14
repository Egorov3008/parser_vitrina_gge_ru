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
from src.utils.logger import get_logger

logger = get_logger()


async def main():
    """Инициализировать сервисы и запустить парсер"""
    db = None
    session = None
    telegram = None
    sched = None

    try:
        logger.info("=" * 60)
        logger.info("ЗАПУСК ПАРСЕРА В РЕЖИМЕ STANDALONE")
        logger.info("=" * 60)

        config = get_config()

        # Инициализировать БД
        db = Database(config.db_path)
        db.init_schema()
        repository = Repository(db)
        logger.info("Database initialized")

        # Инициализировать браузер
        session = SessionManager()
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
