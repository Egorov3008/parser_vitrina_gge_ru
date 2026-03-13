import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from src.db.database import Database
from src.utils.logger import get_logger

logger = get_logger()


@dataclass
class Project:
    """Модель проекта"""

    vitrina_id: str
    expertise_num: Optional[str] = None
    object_name: Optional[str] = None
    expert_org: Optional[str] = None
    developer: Optional[str] = None
    tech_customer: Optional[str] = None
    region: Optional[str] = None
    category: Optional[str] = None
    characteristics: Optional[Dict] = None
    published_at: Optional[str] = None
    updated_at: Optional[str] = None
    url: Optional[str] = None


@dataclass
class RunLog:
    """Модель лога запуска"""

    id: Optional[int] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    status: Optional[str] = None
    new_count: int = 0
    error_msg: Optional[str] = None


@dataclass
class ParserSetting:
    """Модель настройки парсера"""

    key: str
    value: Optional[str] = None
    description: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class Admin:
    """Модель администратора"""

    telegram_id: str
    username: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class NotificationChat:
    """Модель чата для отправки уведомлений"""

    chat_id: str
    chat_name: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None


@dataclass
class ParserSettings:
    """Группа настроек парсера"""

    filter_categories: List[str] = field(default_factory=list)
    filter_regions: List[str] = field(default_factory=list)
    expertise_year_from: Optional[int] = None
    expertise_year_to: Optional[int] = None
    last_successful_run: Optional[str] = None
    cron_schedule: str = "0 6 * * *"
    run_on_start: bool = False
    headless: bool = True


class Repository:
    """Работа с данными в БД"""

    def __init__(self, db: Database):
        self.db = db

    def is_known(self, vitrina_id: str) -> bool:
        """Проверить, известен ли проект"""
        row = self.db.fetch_one(
            "SELECT 1 FROM projects WHERE vitrina_id = ?", (vitrina_id,)
        )
        return row is not None

    def save_project(self, project: Project) -> None:
        """Сохранить проект в БД"""
        characteristics_json = None
        if project.characteristics:
            characteristics_json = json.dumps(
                project.characteristics, ensure_ascii=False
            )

        try:
            self.db.execute(
                """
                INSERT OR IGNORE INTO projects
                (vitrina_id, expertise_num, object_name, expert_org, developer,
                 tech_customer, region, category, characteristics, published_at,
                 updated_at, url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project.vitrina_id,
                    project.expertise_num,
                    project.object_name,
                    project.expert_org,
                    project.developer,
                    project.tech_customer,
                    project.region,
                    project.category,
                    characteristics_json,
                    project.published_at,
                    project.updated_at,
                    project.url,
                ),
            )
            logger.debug(f"Project saved: {project.vitrina_id}")
        except Exception as e:
            logger.error(f"Error saving project {project.vitrina_id}: {e}")
            raise

    def mark_notified(self, vitrina_id: str) -> None:
        """Отметить проект как уведомленный"""
        self.db.execute(
            "UPDATE projects SET notified_at = datetime('now') WHERE vitrina_id = ?",
            (vitrina_id,),
        )
        logger.debug(f"Project marked as notified: {vitrina_id}")

    def get_unnotified_projects(self) -> List[dict]:
        """Получить проекты, которым еще не отправлены уведомления"""
        rows = self.db.fetch_all(
            """
            SELECT * FROM projects
            WHERE notified_at IS NULL
            ORDER BY created_at DESC
            """
        )
        return [dict(row) for row in rows] if rows else []

    def get_all_projects(self) -> List[dict]:
        """Получить все проекты из БД"""
        rows = self.db.fetch_all(
            """
            SELECT * FROM projects
            ORDER BY created_at DESC
            """
        )
        return [dict(row) for row in rows] if rows else []

    def start_run(self) -> RunLog:
        """Начать новый запуск парсера"""
        cursor = self.db.execute(
            "INSERT INTO run_logs (started_at, status) VALUES (datetime('now'), 'running')"
        )
        run_id = cursor.lastrowid
        logger.info(f"Run started: {run_id}")
        return RunLog(id=run_id, started_at=datetime.now().isoformat())

    def finish_run(
        self, run_id: int, status: str, new_count: int = 0, error_msg: Optional[str] = None
    ) -> None:
        """Завершить запуск парсера"""
        # Обновить last_successful_run если успех
        if status == "success":
            self.set_setting(
                "last_successful_run",
                datetime.now().isoformat(timespec="seconds"),
                "Последний успешный запуск",
            )
        
        self.db.execute(
            """
            UPDATE run_logs
            SET finished_at = datetime('now'), status = ?, new_count = ?, error_msg = ?
            WHERE id = ?
            """,
            (status, new_count, error_msg, run_id),
        )
        logger.info(f"Run finished: {run_id} - {status} (new: {new_count})")

    def get_last_run(self) -> Optional[dict]:
        """Получить последний запуск"""
        row = self.db.fetch_one(
            "SELECT * FROM run_logs ORDER BY started_at DESC LIMIT 1"
        )
        return dict(row) if row else None

    def get_stats(self) -> dict:
        """Получить статистику"""
        total = self.db.fetch_one("SELECT COUNT(*) as count FROM projects")
        notified = self.db.fetch_one(
            "SELECT COUNT(*) as count FROM projects WHERE notified_at IS NOT NULL"
        )
        today = self.db.fetch_one(
            """
            SELECT COUNT(*) as count FROM projects
            WHERE DATE(created_at) = DATE('now')
            """
        )

        return {
            "total_projects": total["count"] if total else 0,
            "notified_projects": notified["count"] if notified else 0,
            "today_projects": today["count"] if today else 0,
        }

    def get_projects_since(self, hours: int) -> List[dict]:
        """Получить проекты за последние N часов"""
        rows = self.db.fetch_all(
            """
            SELECT * FROM projects
            WHERE created_at > datetime('now', ? || ' hours')
            ORDER BY created_at DESC
            """,
            (f"-{hours}",),
        )
        return [dict(row) for row in rows] if rows else []

    def get_recent_errors(self, limit: int = 5) -> List[dict]:
        """Получить последние ошибки"""
        rows = self.db.fetch_all(
            """
            SELECT * FROM run_logs
            WHERE status = 'error'
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in rows] if rows else []

    # ========== Настройки парсера ==========

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Получить значение настройки"""
        row = self.db.fetch_one(
            "SELECT value FROM parser_settings WHERE key = ?", (key,)
        )
        return row["value"] if row else default

    def set_setting(self, key: str, value: str, description: Optional[str] = None) -> None:
        """Установить значение настройки"""
        try:
            self.db.execute(
                """
                INSERT INTO parser_settings (key, value, description)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = datetime('now')
                """,
                (key, value, description),
            )
            logger.debug(f"Setting saved: {key} = {value}")
        except Exception as e:
            logger.error(f"Error saving setting {key}: {e}")
            raise

    def get_all_settings(self) -> ParserSettings:
        """Получить все настройки парсера"""
        settings = ParserSettings()

        rows = self.db.fetch_all("SELECT key, value FROM parser_settings")
        if rows:
            for row in rows:
                key, value = row["key"], row["value"]

                if key == "filter_categories":
                    settings.filter_categories = json.loads(value) if value else []
                elif key == "filter_regions":
                    settings.filter_regions = json.loads(value) if value else []
                elif key == "expertise_year_from":
                    settings.expertise_year_from = int(value) if value else None
                elif key == "expertise_year_to":
                    settings.expertise_year_to = int(value) if value else None
                elif key == "last_successful_run":
                    settings.last_successful_run = value if value else None
                elif key == "cron_schedule":
                    settings.cron_schedule = value or "0 6 * * *"
                elif key == "run_on_start":
                    settings.run_on_start = value == "true"
                elif key == "headless":
                    settings.headless = value != "false"

        return settings

    def save_settings(self, settings: ParserSettings) -> None:
        """Сохранить все настройки"""
        self.set_setting(
            "filter_categories",
            json.dumps(settings.filter_categories, ensure_ascii=False),
            "Фильтр по категориям",
        )
        self.set_setting(
            "filter_regions",
            json.dumps(settings.filter_regions, ensure_ascii=False),
            "Фильтр по регионам",
        )
        self.set_setting(
            "expertise_year_from",
            str(settings.expertise_year_from) if settings.expertise_year_from else "",
            "Год экспертизы (от)",
        )
        self.set_setting(
            "expertise_year_to",
            str(settings.expertise_year_to) if settings.expertise_year_to else "",
            "Год экспертизы (до)",
        )
        self.set_setting(
            "last_successful_run",
            settings.last_successful_run or "",
            "Последний успешный запуск",
        )
        self.set_setting(
            "cron_schedule",
            settings.cron_schedule,
            "Расписание (cron)",
        )
        self.set_setting(
            "run_on_start",
            "true" if settings.run_on_start else "false",
            "Запуск при старте",
        )

    # ========== Администраторы ==========

    def add_admin(self, telegram_id: str, username: Optional[str] = None) -> None:
        """Добавить администратора"""
        try:
            self.db.execute(
                """
                INSERT INTO admins (telegram_id, username)
                VALUES (?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    username = excluded.username
                """,
                (telegram_id, username),
            )
            logger.info(f"Admin added: {telegram_id} ({username})")
        except Exception as e:
            logger.error(f"Error adding admin {telegram_id}: {e}")
            raise

    def remove_admin(self, telegram_id: str) -> None:
        """Удалить администратора"""
        self.db.execute("DELETE FROM admins WHERE telegram_id = ?", (telegram_id,))
        logger.info(f"Admin removed: {telegram_id}")

    def is_admin(self, telegram_id: str) -> bool:
        """Проверить, является ли пользователь администратором"""
        row = self.db.fetch_one(
            "SELECT 1 FROM admins WHERE telegram_id = ?", (telegram_id,)
        )
        return row is not None

    def get_admins(self) -> List[Admin]:
        """Получить список администраторов"""
        rows = self.db.fetch_all("SELECT * FROM admins ORDER BY created_at DESC")
        return [
            Admin(
                telegram_id=row["telegram_id"],
                username=row["username"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    # ========== Чаты для уведомлений ==========

    def add_notification_chat(self, chat_id: str, chat_name: Optional[str] = None) -> None:
        """Добавить чат для отправки уведомлений"""
        try:
            self.db.execute(
                """
                INSERT INTO notification_chats (chat_id, chat_name, is_active)
                VALUES (?, ?, 1)
                ON CONFLICT(chat_id) DO UPDATE SET
                    chat_name = excluded.chat_name,
                    is_active = 1
                """,
                (chat_id, chat_name),
            )
            logger.info(f"Notification chat added: {chat_id} ({chat_name})")
        except Exception as e:
            logger.error(f"Error adding notification chat {chat_id}: {e}")
            raise

    def remove_notification_chat(self, chat_id: str) -> None:
        """Удалить чат для отправки уведомлений"""
        self.db.execute("DELETE FROM notification_chats WHERE chat_id = ?", (chat_id,))
        logger.info(f"Notification chat removed: {chat_id}")

    def get_notification_chats(self) -> List[NotificationChat]:
        """Получить список активных чатов для отправки"""
        rows = self.db.fetch_all(
            "SELECT * FROM notification_chats WHERE is_active = 1 ORDER BY created_at DESC"
        )
        return [
            NotificationChat(
                chat_id=row["chat_id"],
                chat_name=row["chat_name"],
                is_active=row["is_active"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def get_all_notification_chats(self) -> List[NotificationChat]:
        """Получить все чаты (включая неактивные)"""
        rows = self.db.fetch_all(
            "SELECT * FROM notification_chats ORDER BY created_at DESC"
        )
        return [
            NotificationChat(
                chat_id=row["chat_id"],
                chat_name=row["chat_name"],
                is_active=row["is_active"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    # ========== Очистка данных ==========

    def clear_all_data(self) -> dict:
        """Очистить все данные (проекты и логи запусков)"""
        try:
            # Получить количество удаляемых записей перед удалением
            projects_count = self.db.fetch_one("SELECT COUNT(*) as count FROM projects")
            run_logs_count = self.db.fetch_one("SELECT COUNT(*) as count FROM run_logs")

            projects_total = projects_count["count"] if projects_count else 0
            logs_total = run_logs_count["count"] if run_logs_count else 0

            # Удалить данные
            self.db.execute("DELETE FROM projects")
            self.db.execute("DELETE FROM run_logs")

            logger.info(f"Data cleared: {projects_total} projects, {logs_total} run logs deleted")

            return {
                "success": True,
                "projects_deleted": projects_total,
                "logs_deleted": logs_total,
            }
        except Exception as e:
            logger.error(f"Error clearing data: {e}")
            raise
