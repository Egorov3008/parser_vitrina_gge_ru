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
