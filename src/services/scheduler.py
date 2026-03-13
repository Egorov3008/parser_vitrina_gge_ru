from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.browser.session import SessionManager
from src.config import get_config
from src.db.database import Database
from src.db.repository import Repository
from src.services.projects import ProjectsService
from src.services.telegram import TelegramService
from src.utils.formatters import format_project_notification, format_teps_file
from src.utils.logger import get_logger

logger = get_logger()


class SchedulerService:
    """Планировщик парсинга проектов"""

    def __init__(
        self,
        telegram: TelegramService,
        session: SessionManager,
        db: Database,
        repository: Repository,
    ):
        self.config = get_config()
        self.telegram = telegram
        self.session = session
        self.db = db
        self.repository = repository
        self.projects_service: Optional[ProjectsService] = None
        self.scheduler: Optional[AsyncIOScheduler] = None

    async def initialize(self) -> None:
        """Инициализировать планировщик"""
        self.projects_service = ProjectsService(self.session)
        await self.projects_service.initialize()

        self.scheduler = AsyncIOScheduler()
        self.scheduler.add_job(
            self.run_parser,
            trigger=CronTrigger.from_crontab(self.config.cron_schedule),
            id="vitrina_parser",
            name="Vitrina Parser",
            misfire_grace_time=60,
        )

        logger.info(
            f"Scheduler initialized with cron: {self.config.cron_schedule}"
        )

    def start(self) -> None:
        """Запустить планировщик"""
        if self.scheduler:
            self.scheduler.start()
            logger.info("Scheduler started")

    async def stop(self) -> None:
        """Остановить планировщик"""
        if self.scheduler:
            self.scheduler.shutdown(wait=True)
            await self.projects_service.close()
            logger.info("Scheduler stopped")

    async def run_parser(self) -> None:
        """Основной pipeline парсинга проектов"""
        run = self.repository.start_run()
        new_count = 0
        notified_count = 0

        try:
            logger.info("Starting parser run")

            # Получить настройки
            settings = self.repository.get_all_settings()
            last_run_at = settings.last_successful_run
            year_from = settings.expertise_year_from
            year_to = settings.expertise_year_to

            logger.info(f"Last run: {last_run_at or 'never'}")
            logger.info(f"Expertise year filter: {year_from or '—'} - {year_to or '—'}")
            logger.info(f"Category filter: {settings.filter_categories or 'all'}")
            logger.info(f"Region filter: {settings.filter_regions or 'all'}")

            # Получить чаты для отправки уведомлений
            notification_chats = self.repository.get_notification_chats()
            chat_ids = [chat.chat_id for chat in notification_chats] if notification_chats else None
            logger.info(f"Notification chats: {len(notification_chats) if notification_chats else 0}")

            # Убедиться, что авторизованы
            await self.session.ensure_logged_in()

            # Получить список проектов с фильтрами из БД
            # Год экспертизы теперь фильтруется на стороне сервера при браузерном поиске
            projects = await self.projects_service.fetch_list(
                categories=settings.filter_categories or None,
                regions=settings.filter_regions or None,
                year_from=year_from,
                year_to=year_to,
            )
            logger.info(f"Fetched {len(projects)} projects")

            # Фильтр по дате последнего запуска
            projects = await self.projects_service.filter_by_last_run(projects, last_run_at)
            logger.info(f"After date filter: {len(projects)} projects")

            # Обработать каждый проект
            for project in projects:
                if self.repository.is_known(project.vitrina_id):
                    logger.debug(f"Project already known: {project.vitrina_id}")
                    continue

                logger.info(f"Processing new project: {project.vitrina_id}")

                # Сохранить teps из sidebar до перезаписи деталями
                initial_teps = getattr(project, '_teps', None)

                # Получить детали проекта
                details = None
                if project.url:
                    details = await self.projects_service.fetch_details(
                        project.url
                    )

                # Применить детали к объекту project перед сохранением
                if details:
                    project.expertise_num = details.get("expertise_num") or project.expertise_num
                    project.object_name = details.get("object_name") or project.object_name
                    project.expert_org = details.get("expert_org") or project.expert_org
                    project.developer = details.get("developer") or project.developer
                    project.tech_customer = details.get("tech_customer") or project.tech_customer
                    project.region = details.get("region") or project.region
                    project.category = details.get("category") or project.category
                    project.characteristics = details.get("characteristics")

                # Если с полной страницы не пришли ТЭП — добавить из sidebar
                teps = (details.get("teps") if details else None) or initial_teps
                if teps and isinstance(project.characteristics, dict):
                    # Слить teps в characteristics для сохранения в БД
                    project.characteristics.update(teps)
                elif teps and project.characteristics is None:
                    project.characteristics = dict(teps)

                # Сохранить в БД (теперь project заполнен)
                self.repository.save_project(project)

                # Отправить уведомление
                message = format_project_notification(project, details)
                await self.telegram.send_notification(message, chat_ids)
                notified_count += 1

                # Отправить ТЭП файл если есть
                if teps:
                    file_content = format_teps_file(project, teps)
                    filename = f"teps_{project.vitrina_id}.txt"
                    await self.telegram.send_file(file_content, filename, chat_ids)

                # Отметить как уведомленный
                self.repository.mark_notified(project.vitrina_id)
                new_count += 1

            # Завершить запуск
            self.repository.finish_run(run.id, "success", new_count)

            logger.info(f"Parser run completed: {new_count} new projects, {notified_count} notified")

        except Exception as e:
            logger.error(f"Parser error: {e}", exc_info=True)
            self.repository.finish_run(run.id, "error", error_msg=str(e))
            # Получить чаты для отправки алерта
            notification_chats = self.repository.get_notification_chats()
            chat_ids = [chat.chat_id for chat in notification_chats] if notification_chats else None
            await self.telegram.send_alert(str(e), chat_ids)

    async def run_immediately(self) -> None:
        """Запустить парсер немедленно (для команды /run_now)"""
        await self.run_parser()
