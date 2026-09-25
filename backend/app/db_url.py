"""Database URL helpers.

Migrations run on SYNCHRONOUS drivers while the app runs async; `to_sync_url` translates an async
URL to its sync equivalent. Kept in its own importable module so it is unit-testable without
importing the Alembic env (which runs migrations on import).
"""
from __future__ import annotations


def to_sync_url(url: str) -> str:
    """Translate an async SQLAlchemy URL to its sync equivalent for Alembic migrations."""
    return (
        url.replace("+aiosqlite", "")
        .replace("+asyncpg", "+psycopg2")
        .replace("+aiomysql", "+pymysql")
    )
