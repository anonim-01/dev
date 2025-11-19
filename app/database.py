from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Any, Generator, Iterable, Optional

try:
    from psycopg import connect as pg_connect  # type: ignore
    from psycopg.rows import dict_row  # type: ignore
except ImportError:  # pragma: no cover - optional dependency for SQLite-only installs
    pg_connect = None
    dict_row = None

from .config import AppConfig

_SCHEMA_PATCHES = (
    ("sazan", "toplam_limit", "INTEGER", "0"),
    ("sazan", "guncel_limit", "INTEGER", "0"),
)

USING_POSTGRES = bool(AppConfig.database_url)


def _ensure_schema_sqlite(connection: sqlite3.Connection) -> None:
    cursor = connection.cursor()
    for table_name, column_name, column_type, default in _SCHEMA_PATCHES:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = {row[1] for row in cursor.fetchall()}
        if column_name not in columns:
            cursor.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} DEFAULT {default}"
            )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS cloudflared_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command TEXT NOT NULL,
            stdout TEXT,
            stderr TEXT,
            status TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS domain_aliases (
            id TEXT PRIMARY KEY,
            base_domain TEXT NOT NULL,
            subdomain TEXT NOT NULL DEFAULT '',
            masked_subdomain TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_domain_alias_masked
            ON domain_aliases(masked_subdomain)
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_domain_alias_real
            ON domain_aliases(base_domain, subdomain)
        """
    )
    connection.commit()
    cursor.close()


def _ensure_schema_postgres(connection: Any) -> None:
    cursor = connection.cursor()
    for table_name, column_name, column_type, default in _SCHEMA_PATCHES:
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = %s
              AND column_name = %s
            """,
            (table_name, column_name),
        )
        if cursor.fetchone() is None:
            cursor.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} DEFAULT {default}"
            )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS cloudflared_logs (
            id BIGSERIAL PRIMARY KEY,
            command TEXT NOT NULL,
            stdout TEXT,
            stderr TEXT,
            status TEXT,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS domain_aliases (
            id TEXT PRIMARY KEY,
            base_domain TEXT NOT NULL,
            subdomain TEXT NOT NULL DEFAULT '',
            masked_subdomain TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_domain_alias_masked
            ON domain_aliases(masked_subdomain)
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_domain_alias_real
            ON domain_aliases(base_domain, subdomain)
        """
    )
    connection.commit()
    cursor.close()


def _ensure_schema(connection: Any) -> None:
    if USING_POSTGRES:
        if not AppConfig.database_url:
            raise RuntimeError("DATABASE_URL must be defined for PostgreSQL connections.")
        if pg_connect is None:
            raise RuntimeError("psycopg is not installed. Please run 'pip install psycopg[binary]'.")
        _ensure_schema_postgres(connection)
    else:
        _ensure_schema_sqlite(connection)


def _row_to_dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return row
    return dict(row)


def _prepare_query(query: str) -> str:
    if USING_POSTGRES:
        return query.replace("?", "%s")
    return query


def get_connection() -> Any:
    if USING_POSTGRES:
        if not AppConfig.database_url:
            raise RuntimeError("DATABASE_URL is not configured but PostgreSQL mode is enabled.")
        if pg_connect is None or dict_row is None:
            raise RuntimeError("psycopg is required for PostgreSQL connections. Install psycopg[binary].")
        connection = pg_connect(AppConfig.database_url, row_factory=dict_row)
    else:
        connection = sqlite3.connect(AppConfig.database_path)
        connection.row_factory = sqlite3.Row
    _ensure_schema(connection)
    return connection


@contextmanager
def get_cursor() -> Generator[sqlite3.Cursor, None, None]:
    connection = get_connection()
    try:
        cursor = connection.cursor()
        yield cursor
        connection.commit()
    finally:
        connection.close()


def execute(query: str, params: Optional[Iterable[Any]] = None) -> int:
    with get_cursor() as cursor:
        cursor.execute(_prepare_query(query), params or ())
        last_insert_id = getattr(cursor, "lastrowid", None)
        return int(last_insert_id or 0)


def fetch_one(query: str, params: Optional[Iterable[Any]] = None) -> Optional[dict[str, Any]]:
    with get_cursor() as cursor:
        cursor.execute(_prepare_query(query), params or ())
        row = cursor.fetchone()
        return _row_to_dict(row) if row else None


def fetch_all(query: str, params: Optional[Iterable[Any]] = None) -> list[dict[str, Any]]:
    with get_cursor() as cursor:
        cursor.execute(_prepare_query(query), params or ())
        rows = cursor.fetchall()
        return [_row_to_dict(row) for row in rows]
