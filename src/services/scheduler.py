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
        self._max_cards: int = 0  # 0 = без ограничения

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
            logger.info("=" * 60)
            logger.info("ЗАПУСК ПАРСЕРА")
            logger.info("=" * 60)

            # Получить настройки
            settings = self.repository.get_all_settings()
            last_run_at = settings.last_successful_run
            year_from = settings.expertise_year_from
            year_to = settings.expertise_year_to

            # Получить чаты для отправки уведомлений
            notification_chats = self.repository.get_notification_chats()
            chat_ids = [chat.chat_id for chat in notification_chats] if notification_chats else None

            # Сводка параметров фильтров
            logger.info("ПАРАМЕТРЫ ЗАПУСКА ПАРСЕРА:")
            logger.info(f"  Категории ({len(settings.filter_categories) if settings.filter_categories else 0}): {settings.filter_categories or 'все'}")
            logger.info(f"  Регионы ({len(settings.filter_regions) if settings.filter_regions else 0}): {settings.filter_regions or 'все'}")
            logger.info(f"  Год экспертизы: {year_from or '—'} — {year_to or '—'}")
            logger.info(f"  Последний успешный запуск: {last_run_at or 'первый запуск'}")
            logger.info(f"  Чаты для уведомлений ({len(chat_ids) if chat_ids else 0}): {chat_ids}")
            logger.info("=" * 60)

            # Убедиться, что авторизованы
            await self.session.ensure_logged_in()

            # Получить список проектов с серверными фильтрами (категория, регион)
            projects = await self.projects_service.fetch_list(
                categories=settings.filter_categories or None,
                regions=settings.filter_regions or None,
                max_cards=self._max_cards,
            )
            total_fetched = len(projects)
            logger.info(f"[1/4] ПОЛУЧЕНО с сайта: {total_fetched} объектов")

            # Клиентская фильтрация по году экспертизы
            if year_from or year_to:
                projects_before_year = len(projects)
                projects = self.projects_service.filter_by_expertise_year(
                    projects, year_from=year_from, year_to=year_to
                )
                dropped_by_year = projects_before_year - len(projects)
                logger.info(f"  После фильтра по году: {len(projects)} объектов (отсеяно: {dropped_by_year})")

            # Фильтр по дате последнего запуска
            projects_before_date_filter = len(projects)
            projects = await self.projects_service.filter_by_last_run(projects, last_run_at)
            dropped_by_date = projects_before_date_filter - len(projects)
            logger.info(f"[2/4] ПОСЛЕ фильтра по дате: {len(projects)} объектов (отсеяно: {dropped_by_date})")

            # Обработать каждый проект
            logger.info(f"[3/4] НОВЫХ объектов для обработки: {len(projects)}")

            for i, project in enumerate(projects, 1):
                if self.repository.is_known(project.vitrina_id):
                    logger.debug(f"  ПРОПУЩЕН (уже в БД): {project.vitrina_id} — {project.object_name}")
                    continue

                # Данные уже извлечены из sidebar при парсинге карточек
                # fetch_details() не используется — отдельных страниц карточек нет,
                # а навигация на /projects/{id} перезаписывает данные пустыми значениями

                # Добавить teps из sidebar в characteristics
                teps = getattr(project, '_teps', None)
                if teps and isinstance(project.characteristics, dict):
                    project.characteristics.update(teps)
                elif teps and project.characteristics is None:
                    project.characteristics = dict(teps)

                # Логирование карточки проекта
                logger.info(f"[ОБЪЕКТ] {project.vitrina_id}")
                logger.info(f"  Название:   {project.object_name or '—'}")
                logger.info(f"  Категория:  {project.category or '—'}")
                logger.info(f"  Регион:     {project.region or '—'}")
                logger.info(f"  Застройщик: {project.developer or '—'}")
                logger.info(f"  Экспертиза: {project.expertise_num or '—'}")
                logger.info(f"  Дата:       {project.published_at or project.updated_at or '—'}")
                logger.info(f"  URL:        {project.url}")
                logger.info(f"  ТЭП:        {'есть' if teps else 'нет'}")

                # Сохранить в БД (теперь project заполнен)
                self.repository.save_project(project)

                # Отправить уведомление
                message = format_project_notification(project, None)
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

                # Логирование отправки уведомления
                if chat_ids:
                    logger.info(f"[4/4] УВЕДОМЛЕНИЕ отправлено: {project.vitrina_id} → чат {chat_ids}")
                else:
                    logger.info(f"[4/4] УВЕДОМЛЕНИЕ не отправлено (нет чатов): {project.vitrina_id}")

            # Завершить запуск
            self.repository.finish_run(run.id, "success", new_count)

            # Финальная сводка
            logger.info("=" * 60)
            logger.info(f"ИТОГ: обработано {new_count}/{total_fetched} объектов, отправлено в {len(chat_ids) if chat_ids else 0} чат(ов)")
            logger.info("=" * 60)

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
