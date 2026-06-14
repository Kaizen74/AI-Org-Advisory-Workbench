"""Shared pytest fixtures.

`mock_claude` is the heart of the test protocol (Build Spec A3, Rule 1): it monkeypatches the
Claude seam so `messages.create(...)` returns a canned object whose `.content[0].text` is fixed,
valid JSON loaded from `backend/tests/fixtures/*.json`. Every AI-touching test uses it. No test may
make a real network call — the suite runs offline, deterministic, and free.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture_text(name: str) -> str:
    """Return the raw text of a fixture JSON file (validated as JSON on load)."""
    path = FIXTURES_DIR / name
    text = path.read_text(encoding="utf-8")
    json.loads(text)  # fail fast if a fixture is not valid JSON
    return text


def _make_canned_response(text: str):
    """Mimic the shape of an Anthropic Messages response: `.content[0].text`."""
    return SimpleNamespace(content=[SimpleNamespace(text=text)])


@pytest.fixture
def mock_claude(monkeypatch):
    """Patch the Claude singleton so every call returns canned fixture JSON — no network.

    Default canned response is `sample_extract.json`. A test can override what the next call
    returns via the returned controller's `.set_response(fixture_name)` or `.set_text(raw)`.
    """
    from app.services.claude_service import claude_service

    state = {"text": load_fixture_text("sample_extract.json")}

    def fake_complete(*, model, max_tokens=2048, messages):  # noqa: ARG001 - signature parity
        return state["text"]

    # Patch the public seam used by feature services.
    monkeypatch.setattr(claude_service, "complete", fake_complete)
    # Also pretend a key is present so AI endpoints don't 400 in tests.
    monkeypatch.setattr(type(claude_service), "has_api_key", property(lambda self: True))

    class Controller:
        def set_response(self, fixture_name: str) -> None:
            state["text"] = load_fixture_text(fixture_name)

        def set_text(self, raw: str) -> None:
            state["text"] = raw

        @property
        def last_text(self) -> str:
            return state["text"]

        def raw_response(self):
            """Return an Anthropic-shaped object for tests patching the lower-level client."""
            return _make_canned_response(state["text"])

    return Controller()


# ── Async DB + API client fixtures (Phase 1) ─────────────────────────────────
@pytest_asyncio.fixture
async def async_session():
    """A fresh in-memory SQLite (StaticPool keeps one connection so tables persist)."""
    from app.models.database import Base

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def api_client(async_session):
    """httpx client wired to the app, authenticated as an owner (auth gate overridden)."""
    from app.api.auth_dep import require_auth
    from app.main import app
    from app.models import get_session

    async def _override():
        yield async_session

    app.dependency_overrides[get_session] = _override
    app.dependency_overrides[require_auth] = lambda: {"email": "test@example.com", "owner": True}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def anon_client(async_session):
    """httpx client with the REAL auth gate active (for login + 401 tests)."""
    from app.main import app
    from app.models import get_session

    async def _override():
        yield async_session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
