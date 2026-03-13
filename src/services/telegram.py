from typing import Optional

from telegram import Bot, BotCommand
from telegram.constants import ParseMode

from src.config import get_config
from src.utils.formatters import format_alert, format_stats, format_status
from src.utils.logger import get_logger

logger = get_logger()


class TelegramService:
    """Отправка уведомлений через Telegram бот"""

    def __init__(self):
        self.config = get_config()
        self.bot = Bot(token=self.config.telegram_bot_token)
        self.chat_id = self.config.telegram_chat_id

    async def send_notification(self, message: str) -> None:
        """Отправить уведомление о новом проекте"""
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False,
            )
            logger.debug("Notification sent")
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            raise

    async def send_summary(self, new_count: int) -> None:
        """Отправить сводку по результатам парсинга"""
        message = format_summary(new_count)
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.HTML,
            )
            logger.debug(f"Summary sent: {new_count} new projects")
        except Exception as e:
            logger.error(f"Error sending summary: {e}")

    async def send_alert(self, error_message: str) -> None:
        """Отправить оповещение об ошибке"""
        message = format_alert(error_message)
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.HTML,
            )
            logger.error(f"Alert sent: {error_message}")
        except Exception as e:
            logger.error(f"Error sending alert: {e}")

    async def send_status(self, run_log: Optional[dict]) -> None:
        """Отправить статус последнего запуска"""
        message = format_status(run_log)
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.HTML,
            )
            logger.debug("Status sent")
        except Exception as e:
            logger.error(f"Error sending status: {e}")

    async def send_stats(self, stats: dict, recent_errors: Optional[list] = None) -> None:
        """Отправить статистику"""
        message = format_stats(stats, recent_errors)
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.HTML,
            )
            logger.debug("Stats sent")
        except Exception as e:
            logger.error(f"Error sending stats: {e}")

    async def setup_commands(self) -> None:
        """Настроить команды бота"""
        commands = [
            BotCommand("status", "Последний запуск парсера"),
            BotCommand("run_now", "Запустить парсер немедленно"),
            BotCommand("stats", "Статистика проектов"),
            BotCommand("help", "Справка по командам"),
        ]

        try:
            await self.bot.set_my_commands(commands)
            logger.info("Bot commands configured")
        except Exception as e:
            logger.error(f"Error setting up commands: {e}")

    async def close(self) -> None:
        """Закрыть сессию бота"""
        await self.bot.close()
        logger.info("Telegram bot closed")
