"""Application configuration.

All secrets and model strings come from the environment (Build Spec A4) — never hardcoded in
service code. Sensible defaults keep the app runnable without an API key for non-AI endpoints.
"""
from __future__ import annotations

import os


class Settings:
    """Environment-backed settings. Read once at import time."""

    # Anthropic / Claude. The key is optional so non-AI endpoints work without it (Build Spec B2).
    ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY") or None

    # Model strings are env-configurable with sensible defaults (Build Spec A4 / PRD §6).
    MODEL_EXTRACT: str = os.getenv("MODEL_EXTRACT", "claude-sonnet-4-6")
    MODEL_SYNTH: str = os.getenv("MODEL_SYNTH", "claude-opus-4-8")

    # Database. SQLite for dev; Postgres-ready via the same SQLAlchemy models (PRD §7).
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./advisory_workbench.db")

    # Salt for stable anonymization pseudonyms (P7/M7). Override in production via env.
    ANON_SALT: str = os.getenv("ANON_SALT", "dev-anon-salt-change-me")

    # CORS origins for the local frontend dev server.
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")


settings = Settings()
