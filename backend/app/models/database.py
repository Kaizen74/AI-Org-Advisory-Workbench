"""Database configuration and async session management.

Adapted from the legacy v1 app (`legacy/backend/app/models/database.py`) — the DB URL now comes
from the central `app.config.settings` (Build Spec A4: env-config, no hardcoding). SQLite for dev,
Postgres-ready via the same SQLAlchemy models (PRD §7).
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from ..config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def generate_uuid() -> str:
    """String UUID primary key (Build Spec B1: uuid string PK via generate_uuid)."""
    return str(uuid.uuid4())


async def get_session():
    """FastAPI dependency yielding an async session, committing on success."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables (used by tests; production uses Alembic migrations)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    await engine.dispose()
