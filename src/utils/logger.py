import sys
from pathlib import Path

from loguru import logger

from src.config import get_config


def setup_logger() -> None:
    """Настроить логирование через loguru"""
    config = get_config()

    # Убрать стандартный обработчик
    logger.remove()

    # Убедиться что директория логов существует
    log_dir = Path(config.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Формат логов
    log_format = (
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # Консоль (stderr)
    logger.add(
        sink=sys.stderr,
        format=log_format,
        level=config.log_level,
        colorize=True,
    )

    # Файл с ротацией
    log_file = log_dir / "parser-{time:YYYY-MM-DD}.log"
    logger.add(
        sink=str(log_file),
        format=log_format,
        level=config.log_level,
        rotation="00:00",  # Ротация в полночь
        retention="30 days",
        encoding="utf-8",
    )


def get_logger():
    """Получить logger для использования в модулях"""
    return logger
