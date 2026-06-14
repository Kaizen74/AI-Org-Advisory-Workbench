"""FA.2 — claude_service provider routing (anthropic | local) + availability.

No real network: the Anthropic client builder and the local HTTP POST are patched seams.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import settings_service as ss
from app.services.claude_service import claude_service


@pytest.fixture(autouse=True)
def _reset():
    ss.reset_cache_for_tests()
    claude_service._anthropic_client = None
    claude_service._anthropic_key_used = None
    yield
    ss.reset_cache_for_tests()
    claude_service._anthropic_client = None
    claude_service._anthropic_key_used = None


def test_anthropic_path(monkeypatch):
    ss._cache["llm_provider"] = "anthropic"
    ss._cache["anthropic_api_key"] = "sk-test"

    captured = {}

    class FakeMessages:
        def create(self, *, model, max_tokens, messages):
            captured["model"] = model
            return SimpleNamespace(content=[SimpleNamespace(text="anthropic-reply")])

    monkeypatch.setattr(claude_service, "_build_anthropic_client",
                        lambda key: SimpleNamespace(messages=FakeMessages()))

    out = claude_service.complete(model="claude-sonnet-4-6",
                                  messages=[{"role": "user", "content": "hi"}])
    assert out == "anthropic-reply"
    assert captured["model"] == "claude-sonnet-4-6"


def test_local_path_uses_local_model_and_endpoint(monkeypatch):
    ss._cache["llm_provider"] = "local"
    ss._cache["local_base_url"] = "http://localhost:11434/v1"
    ss._cache["local_model"] = "llama3.1"

    captured = {}

    def fake_post(url, payload, headers):
        captured["url"] = url
        captured["payload"] = payload
        return {"choices": [{"message": {"content": "local-reply"}}]}

    monkeypatch.setattr(claude_service, "_post_local", fake_post)

    out = claude_service.complete(model="claude-opus-4-8",
                                  messages=[{"role": "user", "content": "hi"}])
    assert out == "local-reply"
    assert captured["url"] == "http://localhost:11434/v1/chat/completions"
    assert captured["payload"]["model"] == "llama3.1"  # Anthropic model overridden by local model


def test_has_api_key_is_provider_aware():
    # Local provider: available when a base URL is set, even with no Anthropic key.
    ss._cache["llm_provider"] = "local"
    ss._cache["anthropic_api_key"] = ""
    ss._cache["local_base_url"] = "http://localhost:11434/v1"
    assert claude_service.has_api_key is True

    # Anthropic provider: needs a key.
    ss._cache["llm_provider"] = "anthropic"
    ss._cache["anthropic_api_key"] = ""
    assert claude_service.has_api_key is False
    ss._cache["anthropic_api_key"] = "sk-test"
    assert claude_service.has_api_key is True


def test_anthropic_missing_key_raises(monkeypatch):
    ss._cache["llm_provider"] = "anthropic"
    ss._cache["anthropic_api_key"] = ""
    monkeypatch.setattr(claude_service, "_build_anthropic_client", lambda key: None)
    with pytest.raises(RuntimeError):
        claude_service.complete(model="m", messages=[{"role": "user", "content": "x"}])
