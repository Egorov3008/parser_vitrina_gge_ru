import sqlite3
from pathlib import Path
from typing import Optional

from src.utils.logger import get_logger

logger = get_logger()


class Database:
    """Управление SQLite подключением и инициализацией"""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        """Открыть подключение к БД"""
        if self.conn is None:
            self.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                detect_types=sqlite3.PARSE_DECLTYPES,
            )
            self.conn.row_factory = sqlite3.Row
            # Включить foreign keys
            self.conn.execute("PRAGMA foreign_keys = ON")
        return self.conn

    def close(self) -> None:
        """Закрыть подключение"""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Database connection closed")

    def init_schema(self) -> None:
        """Инициализировать таблицы"""
        conn = self.connect()
        cursor = conn.cursor()

        # Таблица проектов
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                vitrina_id      TEXT UNIQUE NOT NULL,
                expertise_num   TEXT,
                object_name     TEXT,
                expert_org      TEXT,
                developer       TEXT,
                tech_customer   TEXT,
                region          TEXT,
                category        TEXT,
                characteristics TEXT,
                published_at    TEXT,
                updated_at      TEXT,
                url             TEXT,
                notified_at     TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            )
            """
        )

        # Таблица логов запусков
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS run_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at  TEXT NOT NULL,
                finished_at TEXT,
                status      TEXT,
                new_count   INTEGER DEFAULT 0,
                error_msg   TEXT
            )
            """
        )

        # Таблица настроек парсера
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS parser_settings (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                key             TEXT UNIQUE NOT NULL,
                value           TEXT,
                description     TEXT,
                updated_at      TEXT DEFAULT (datetime('now'))
            )
            """
        )

        # Таблица админов
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS admins (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id     TEXT UNIQUE NOT NULL,
                username        TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            )
            """
        )

        # Таблица чатов для уведомлений
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS notification_chats (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id         TEXT UNIQUE NOT NULL,
                chat_name       TEXT,
                is_active       BOOLEAN DEFAULT 1,
                created_at      TEXT DEFAULT (datetime('now'))
            )
            """
        )

        # Таблица учетных записей для авторизации
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS credentials (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                login           TEXT UNIQUE NOT NULL,
                password        TEXT NOT NULL,
                label           TEXT,
                is_active       BOOLEAN DEFAULT 0,
                created_at      TEXT DEFAULT (datetime('now'))
            )
            """
        )

        # Индексы для быстрого поиска
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_projects_vitrina_id
            ON projects(vitrina_id)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_projects_notified_at
            ON projects(notified_at)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_projects_created_at
            ON projects(created_at)
            """
        )

        conn.commit()
        logger.info(f"Database schema initialized at {self.db_path}")

    def init_default_settings(self) -> None:
        """Инициализировать настройки по умолчанию если они не существуют"""
        conn = self.connect()
        cursor = conn.cursor()

        # Проверить есть ли уже настройки
        cursor.execute("SELECT COUNT(*) FROM parser_settings")
        if cursor.fetchone()[0] > 0:
            return  # Настройки уже существуют

        # Инициализировать настройки по умолчанию
        default_settings = [
            ("filter_categories", "[]", "Фильтр по категориям (JSON массив)"),
            ("filter_regions", "[]", "Фильтр по регионам (JSON массив)"),
            ("expertise_year", "", "Год экспертизы — пустое = без фильтра"),
            ("last_successful_run", "", "Последний успешный запуск"),
            ("cron_schedule", "0 6 * * *", "Расписание (cron, UTC)"),
            ("run_on_start", "false", "Запуск при старте"),
            ("headless", "true", "Режим браузера (headless)"),
        ]

        cursor.executemany(
            """
            INSERT OR IGNORE INTO parser_settings (key, value, description)
            VALUES (?, ?, ?)
            """,
            default_settings,
        )

        conn.commit()
        logger.info("Default parser settings initialized")

    def execute(self, query: str, params: tuple = ()):
        """Выполнить запрос (INSERT/UPDATE/DELETE)"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor

    def execute_many(self, query: str, params_list: list):
        """Выполнить множество запросов"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.executemany(query, params_list)
        conn.commit()
        return cursor

    def fetch_one(self, query: str, params: tuple = ()):
        """Получить одну строку"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()

    def fetch_all(self, query: str, params: tuple = ()):
        """Получить все строки"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()
