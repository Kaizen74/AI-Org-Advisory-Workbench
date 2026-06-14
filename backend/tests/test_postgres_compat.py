"""P7.4 — Postgres compatibility + env hardening checks (no live DB needed)."""
from __future__ import annotations

import importlib

from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.schema import CreateTable

from app.db_url import to_sync_url
from app.models.database import Base


def test_models_create_against_postgres_dialect_metadata():
    """All models compile under the Postgres dialect (no SQLite-only constructs)."""
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        assert "CREATE TABLE" in ddl


def test_async_engine_accepts_postgres_url():
    """An asyncpg URL builds an engine (driver importable); no connection is opened."""
    engine = create_async_engine("postgresql+asyncpg://u:p@localhost:5432/db")
    assert engine.dialect.name == "postgresql"


def test_async_urls_translate_to_sync_for_migrations():
    """Migrations run on sync drivers; the URL helper maps async URLs correctly."""
    assert to_sync_url("sqlite+aiosqlite:///x.db") == "sqlite:///x.db"
    assert to_sync_url("postgresql+asyncpg://u:p@h/db") == "postgresql+psycopg2://u:p@h/db"


def test_anon_salt_from_env(monkeypatch):
    monkeypatch.setenv("ANON_SALT", "super-secret-salt")
    import app.config as cfg
    importlib.reload(cfg)
    assert cfg.settings.ANON_SALT == "super-secret-salt"
    monkeypatch.delenv("ANON_SALT", raising=False)
    importlib.reload(cfg)
