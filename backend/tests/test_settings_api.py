"""FA.3 — settings API: read (masked), update, brand-logo upload, test-llm."""
from __future__ import annotations

import base64

import pytest

from app.services import settings_service as ss
from app.services.claude_service import claude_service

PNG_1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


@pytest.fixture(autouse=True)
def _reset():
    ss.reset_cache_for_tests()
    yield
    ss.reset_cache_for_tests()


async def test_get_and_update_settings_masks_secret(api_client):
    g = await api_client.get("/api/v1/settings")
    assert g.status_code == 200
    assert g.json()["llm_provider"] == "anthropic"
    assert g.json()["anthropic_api_key_set"] is False

    up = await api_client.put("/api/v1/settings", json={
        "llm_provider": "local", "local_model": "llama3.1", "anthropic_api_key": "sk-abcd1234",
    })
    body = up.json()
    assert body["llm_provider"] == "local"
    assert body["anthropic_api_key_set"] is True
    assert body["anthropic_api_key_last4"] == "1234"
    assert "anthropic_api_key" not in body  # raw secret never returned


async def test_brand_logo_upload_and_fetch(api_client):
    up = await api_client.post("/api/v1/settings/brand-logo",
                               files={"file": ("logo.png", PNG_1x1, "image/png")})
    assert up.status_code == 200
    assert up.json()["brand_logo_path"].endswith("logo.png")

    got = await api_client.get("/api/v1/settings/brand-logo")
    assert got.status_code == 200
    assert got.content[:8] == PNG_1x1[:8]  # PNG signature


async def test_brand_logo_rejects_bad_type(api_client):
    bad = await api_client.post("/api/v1/settings/brand-logo",
                                files={"file": ("evil.exe", b"MZ", "application/octet-stream")})
    assert bad.status_code == 400


async def test_test_llm_uses_current_provider(api_client, monkeypatch):
    # Configure local provider, then stub the HTTP call.
    await api_client.put("/api/v1/settings", json={
        "llm_provider": "local", "local_base_url": "http://localhost:11434/v1",
        "local_model": "llama3.1",
    })
    monkeypatch.setattr(claude_service, "_post_local",
                        lambda url, payload, headers: {"choices": [{"message": {"content": "ok"}}]})
    r = await api_client.post("/api/v1/settings/test-llm")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["provider"] == "local"


async def test_test_llm_400_when_unconfigured(api_client):
    await api_client.put("/api/v1/settings", json={"llm_provider": "anthropic",
                                                   "anthropic_api_key": ""})
    r = await api_client.post("/api/v1/settings/test-llm")
    assert r.status_code == 400
