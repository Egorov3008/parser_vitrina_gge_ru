from typing import List, Optional

from aiogram import Bot
from aiogram.types import BotCommand
from aiogram.enums import ParseMode

from src.config import get_config
from src.utils.formatters import format_alert, format_stats, format_status, format_summary
from src.utils.logger import get_logger

logger = get_logger()


class TelegramService:
    """Отправка уведомлений через Telegram бот"""

    def __init__(self):
        self.config = get_config()
        self.bot = Bot(token=self.config.telegram_bot_token)
        self.chat_id = self.config.telegram_chat_id

    async def send_notification(self, message: str, chat_ids: Optional[List[str]] = None) -> None:
        """Отправить уведомление о новом проекте"""
        target_chats = chat_ids if chat_ids else [self.chat_id]

        for chat_id in target_chats:
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=False,
                )
            except Exception as e:
                logger.error(f"Error sending notification to {chat_id}: {e}")

    async def send_summary(self, new_count: int, chat_ids: Optional[List[str]] = None) -> None:
        """Отправить сводку по результатам парсинга"""
        message = format_summary(new_count)
        target_chats = chat_ids if chat_ids else [self.chat_id]

        for chat_id in target_chats:
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=ParseMode.HTML,
                )
            except Exception as e:
                logger.error(f"Error sending summary to {chat_id}: {e}")

    async def send_alert(self, error_message: str, chat_ids: Optional[List[str]] = None) -> None:
        """Отправить оповещение об ошибке"""
        message = format_alert(error_message)
        target_chats = chat_ids if chat_ids else [self.chat_id]

        for chat_id in target_chats:
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=ParseMode.HTML,
                )
            except Exception as e:
                logger.error(f"Error sending alert to {chat_id}: {e}")

    async def send_status(self, run_log: Optional[dict], chat_ids: Optional[List[str]] = None) -> None:
        """Отправить статус последнего запуска"""
        message = format_status(run_log)
        target_chats = chat_ids if chat_ids else [self.chat_id]

        for chat_id in target_chats:
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=ParseMode.HTML,
                )
            except Exception as e:
                logger.error(f"Error sending status to {chat_id}: {e}")

    async def send_stats(self, stats: dict, recent_errors: Optional[list] = None, chat_ids: Optional[List[str]] = None) -> None:
        """Отправить статистику"""
        message = format_stats(stats, recent_errors)
        target_chats = chat_ids if chat_ids else [self.chat_id]

        for chat_id in target_chats:
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=ParseMode.HTML,
                )
            except Exception as e:
                logger.error(f"Error sending stats to {chat_id}: {e}")

    async def setup_commands(self) -> None:
        """Настроить команды бота"""
        commands = [
            BotCommand(command="start", description="Основное меню"),
            BotCommand(command="admin", description="Админ-панель"),
            BotCommand(command="status", description="Последний запуск парсера"),
            BotCommand(command="run_now", description="Запустить парсер немедленно"),
            BotCommand(command="stats", description="Статистика проектов"),
            BotCommand(command="help", description="Справка по командам"),
        ]

        try:
            await self.bot.set_my_commands(commands)
            logger.info("Bot commands configured")
        except Exception as e:
            logger.error(f"Error setting up commands: {e}")

    async def send_file(self, file_content: str, filename: str, chat_ids: Optional[List[str]] = None, caption: Optional[str] = None) -> None:
        """Отправить файл через Telegram"""
        from aiogram.types import BufferedInputFile

        target_chats = chat_ids if chat_ids else [self.chat_id]

        for chat_id in target_chats:
            try:
                file_bytes = file_content.encode('utf-8')
                input_file = BufferedInputFile(file_bytes, filename=filename)

                await self.bot.send_document(
                    chat_id=chat_id,
                    document=input_file,
                    caption=caption,
                    parse_mode=ParseMode.HTML if caption else None,
                )
            except Exception as e:
                logger.error(f"Error sending file to {chat_id}: {e}")

    async def close(self) -> None:
        """Закрыть сессию бота"""
        await self.bot.close()
        logger.info("Telegram bot closed")
