"""FA.1 — settings_service: DB persistence, in-memory cache, secret masking."""
from __future__ import annotations

import pytest

from app.services import settings_service as ss


@pytest.fixture(autouse=True)
def _reset():
    ss.reset_cache_for_tests()
    yield
    ss.reset_cache_for_tests()


async def test_update_persists_and_caches(async_session):
    await ss.update_settings(async_session, {"llm_provider": "local", "local_model": "llama3.1"})
    # Cache updated synchronously.
    assert ss.llm_provider() == "local"
    assert ss.local_config()["model"] == "llama3.1"

    # Reload from DB into a fresh cache → values persisted.
    ss.reset_cache_for_tests()
    assert ss.llm_provider() == "anthropic"  # back to default before load
    await ss.load_from_db(async_session)
    assert ss.llm_provider() == "local"


async def test_secrets_are_masked_in_public_view(async_session):
    await ss.update_settings(async_session, {"anthropic_api_key": "sk-ant-secret-1234"})
    view = ss.public_view()
    assert "anthropic_api_key" not in view  # raw secret never surfaced
    assert view["anthropic_api_key_set"] is True
    assert view["anthropic_api_key_last4"] == "1234"
    # Non-secret values are surfaced as-is.
    assert view["llm_provider"] == "anthropic"


async def test_unknown_keys_ignored(async_session):
    await ss.update_settings(async_session, {"bogus": "x", "brand_name": "PAX"})
    assert "bogus" not in ss.current()
    assert ss.get("brand_name") == "PAX"


def test_brand_palette_parses_json():
    ss.reset_cache_for_tests()
    ss._cache["brand_palette"] = '{"ink": "111111", "accent": "2F6F6A"}'
    assert ss.brand_palette()["accent"] == "2F6F6A"
    ss._cache["brand_palette"] = "not-json"
    assert ss.brand_palette() == {}
