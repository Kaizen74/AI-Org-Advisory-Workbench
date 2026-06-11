"""Alembic migration environment.

Runs migrations SYNCHRONOUSLY (Alembic does not need async). The runtime app uses an async driver
(`sqlite+aiosqlite` / `postgresql+asyncpg`); here we translate that to the matching sync driver so
the same configured URL works for both. The URL comes from `app.config.settings` unless an explicit
`sqlalchemy.url` is set on the Alembic config (used by the migration round-trip test).
"""
from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make `app` importable when alembic runs from the backend/ dir.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.models import Base  # noqa: E402  (imports all models so metadata is populated)
import app.models.models  # noqa: E402,F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _sync_url(url: str) -> str:
    """Translate an async DB URL to its sync equivalent for migrations."""
    return (
        url.replace("+aiosqlite", "")
        .replace("+asyncpg", "+psycopg2")
        .replace("+aiomysql", "+pymysql")
    )


def _get_url() -> str:
    # An explicit url on the config (e.g. from tests) wins; otherwise use app settings.
    override = config.get_main_option("sqlalchemy.url")
    if override:
        return _sync_url(override)
    return _sync_url(settings.DATABASE_URL)


def run_migrations_offline() -> None:
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = _get_url()
    connectable = engine_from_config(
        section, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite-friendly ALTERs
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
