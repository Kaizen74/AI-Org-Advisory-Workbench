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


def _fake_client(monkeypatch, content_blocks, captured=None, stop_reason="end_turn"):
    class FakeMessages:
        def create(self, *, model, max_tokens, messages):
            if captured is not None:
                captured["model"] = model
                captured["max_tokens"] = max_tokens
            return SimpleNamespace(content=content_blocks, stop_reason=stop_reason)

    monkeypatch.setattr(claude_service, "_build_anthropic_client",
                        lambda key: SimpleNamespace(messages=FakeMessages()))


def test_anthropic_path(monkeypatch):
    ss._cache["llm_provider"] = "anthropic"
    ss._cache["anthropic_api_key"] = "sk-test"

    captured = {}
    _fake_client(monkeypatch, [SimpleNamespace(type="text", text="anthropic-reply")], captured)

    out = claude_service.complete(model="claude-sonnet-5",
                                  messages=[{"role": "user", "content": "hi"}])
    assert out == "anthropic-reply"
    assert captured["model"] == "claude-sonnet-5"


def test_anthropic_thinking_blocks_are_skipped(monkeypatch):
    """D44 regression: Claude 5-family models return ThinkingBlock(s) BEFORE the TextBlock.
    `response.content[0].text` crashed with AttributeError ('ThinkingBlock' object has no
    attribute 'text') and 500'd the pipeline. complete() must return the text block(s) only."""
    ss._cache["llm_provider"] = "anthropic"
    ss._cache["anthropic_api_key"] = "sk-test"

    # Mimic a real Claude 5 response: thinking first (no .text attr — accessing it raises), then text.
    class ThinkingBlock:
        type = "thinking"
        thinking = "internal reasoning..."
        # NOTE: no `text` attribute, like the real anthropic ThinkingBlock (pydantic raises).

    _fake_client(monkeypatch, [
        ThinkingBlock(),
        SimpleNamespace(type="text", text='{"extractions": []}'),
    ])

    out = claude_service.complete(model="claude-sonnet-5",
                                  messages=[{"role": "user", "content": "hi"}])
    assert out == '{"extractions": []}'


def test_anthropic_multiple_text_blocks_joined(monkeypatch):
    ss._cache["llm_provider"] = "anthropic"
    ss._cache["anthropic_api_key"] = "sk-test"
    _fake_client(monkeypatch, [
        SimpleNamespace(type="thinking", thinking="…"),
        SimpleNamespace(type="text", text='{"a":'),
        SimpleNamespace(type="text", text=' 1}'),
    ])
    out = claude_service.complete(model="claude-opus-4-8",
                                  messages=[{"role": "user", "content": "hi"}])
    assert out == '{"a": 1}'


def test_anthropic_no_text_raises_informative_error(monkeypatch):
    """A refusal / thinking-only response must raise a clear RuntimeError, not AttributeError."""
    ss._cache["llm_provider"] = "anthropic"
    ss._cache["anthropic_api_key"] = "sk-test"
    _fake_client(monkeypatch, [SimpleNamespace(type="thinking", thinking="…")],
                 stop_reason="max_tokens")
    with pytest.raises(RuntimeError, match="no text content.*max_tokens"):
        claude_service.complete(model="claude-sonnet-5",
                                messages=[{"role": "user", "content": "hi"}])


def test_anthropic_typeless_text_block_still_works(monkeypatch):
    """Back-compat: duck-typed blocks with only `.text` (older mocks/fixtures) still parse."""
    ss._cache["llm_provider"] = "anthropic"
    ss._cache["anthropic_api_key"] = "sk-test"
    _fake_client(monkeypatch, [SimpleNamespace(text="plain")])
    out = claude_service.complete(model="claude-sonnet-5",
                                  messages=[{"role": "user", "content": "hi"}])
    assert out == "plain"


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


def test_pipeline_uses_ui_configured_model(monkeypatch):
    """D44: the extraction pipeline must use the Settings-managed model (UI override → env fallback),
    not the env value directly — previously the UI 'Extraction model' field only affected Test-LLM."""
    from app.config import settings as env
    from app.services import task_intelligence_service as tis

    captured = {}

    def fake_complete(*, model, max_tokens=4096, messages):  # noqa: ARG001
        captured["model"] = model
        return '{"extractions": []}'

    monkeypatch.setattr(claude_service, "complete", fake_complete)

    # Default: falls back to the env-configured model (now claude-sonnet-5).
    tis._extract_batch([])
    assert captured["model"] == env.MODEL_EXTRACT == "claude-sonnet-5"

    # UI override via Settings: the pipeline must honour it.
    ss._cache["model_extract"] = "claude-opus-4-8"
    tis._extract_batch([])
    assert captured["model"] == "claude-opus-4-8"

    # Blank stored value falls back to env (never sends an empty model string).
    ss._cache["model_extract"] = ""
    tis._extract_batch([])
    assert captured["model"] == env.MODEL_EXTRACT


def test_anthropic_missing_key_raises(monkeypatch):
    ss._cache["llm_provider"] = "anthropic"
    ss._cache["anthropic_api_key"] = ""
    monkeypatch.setattr(claude_service, "_build_anthropic_client", lambda key: None)
    with pytest.raises(RuntimeError):
        claude_service.complete(model="m", messages=[{"role": "user", "content": "x"}])
