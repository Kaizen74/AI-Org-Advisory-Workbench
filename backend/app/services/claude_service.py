"""LLM access singleton (named `claude_service` for back-compat).

Feature services CONSUME this singleton and never modify it (Build Spec B2). Every model call routes
through `complete(...)`, the single seam tests monkeypatch via `mock_claude` (A3 Rule 1) so the suite
runs offline, deterministically, and free.

Provider routing (D11): `complete(...)` keeps its public signature/return shape but dispatches on the
`llm_provider` setting (managed via the UI / `settings_service`):
  * `anthropic` — the Anthropic Messages API (key from settings, env fallback).
  * `local` — an OpenAI-compatible endpoint (Ollama / LM Studio) for use during frontier outages,
    called via `httpx` (no heavy ML deps). The passed Anthropic `model` is replaced by `local_model`.
"""
from __future__ import annotations

from ..config import settings
from . import settings_service


class ClaudeService:
    """Provider-routing LLM wrapper. Public surface: `has_api_key`, `complete(...)`."""

    def __init__(self) -> None:
        self._anthropic_client = None
        self._anthropic_key_used: str | None = None

    # ── availability ─────────────────────────────────────────────────────────
    @property
    def has_api_key(self) -> bool:
        """Whether an AI call can be made under the current provider."""
        if settings_service.llm_provider() == "local":
            return bool(settings_service.local_config().get("base_url"))
        return bool(self._anthropic_key())

    def _anthropic_key(self) -> str:
        # UI-managed key (settings) wins; env is the fallback.
        return settings_service.anthropic_key() or (settings.ANTHROPIC_API_KEY or "")

    # ── seams (patchable in tests) ────────────────────────────────────────────
    def _build_anthropic_client(self, api_key: str):
        from anthropic import Anthropic  # lazy import keeps non-AI paths dependency-light

        return Anthropic(api_key=api_key)

    def _post_local(self, url: str, payload: dict, headers: dict) -> dict:
        import httpx

        resp = httpx.post(url, json=payload, headers=headers, timeout=120.0)
        resp.raise_for_status()
        return resp.json()

    # ── public API ────────────────────────────────────────────────────────────
    def complete(self, *, model: str, max_tokens: int = 4096, messages: list[dict]) -> str:
        """Send a chat/messages request and return the response TEXT (thinking blocks skipped)."""
        if settings_service.llm_provider() == "local":
            return self._complete_local(messages=messages, max_tokens=max_tokens)
        return self._complete_anthropic(model=model, max_tokens=max_tokens, messages=messages)

    @staticmethod
    def _response_text(response) -> str:
        """Extract the text from a Messages API response, robust across model generations (D44).

        Claude 5-family models (e.g. claude-sonnet-5, which runs adaptive thinking by default)
        return `thinking` blocks BEFORE the `text` block, so `response.content[0].text` raises
        AttributeError ('ThinkingBlock' object has no attribute 'text'). Per the Claude API docs,
        content must be walked and filtered by `block.type == "text"`. Blocks without a `type`
        but with `.text` are accepted for back-compat with older duck-typed fixtures.
        """
        texts: list[str] = []
        for block in getattr(response, "content", []) or []:
            btype = getattr(block, "type", None)
            if btype == "text" or (btype is None and hasattr(block, "text")):
                texts.append(block.text)
        if not texts:
            stop = getattr(response, "stop_reason", None)
            raise RuntimeError(
                f"LLM returned no text content (stop_reason={stop}). "
                "If stop_reason is 'max_tokens', raise the call's max_tokens; if 'refusal', "
                "rephrase the request or switch models in Settings."
            )
        return "".join(texts)

    def _complete_anthropic(self, *, model: str, max_tokens: int, messages: list[dict]) -> str:
        key = self._anthropic_key()
        if not key:
            raise RuntimeError("Anthropic API key is not set — configure it in Settings (B2/D11).")
        # Rebuild the client if the key changed via the UI.
        if self._anthropic_client is None or self._anthropic_key_used != key:
            self._anthropic_client = self._build_anthropic_client(key)
            self._anthropic_key_used = key
        response = self._anthropic_client.messages.create(
            model=model, max_tokens=max_tokens, messages=messages
        )
        return self._response_text(response)

    def _complete_local(self, *, messages: list[dict], max_tokens: int) -> str:
        cfg = settings_service.local_config()
        base_url = (cfg.get("base_url") or "").rstrip("/")
        if not base_url:
            raise RuntimeError("Local LLM base URL is not set — configure it in Settings (D11).")
        headers = {"Content-Type": "application/json"}
        if cfg.get("api_key"):
            headers["Authorization"] = f"Bearer {cfg['api_key']}"
        payload = {
            "model": cfg.get("model") or "local-model",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0,
            "stream": False,
        }
        data = self._post_local(f"{base_url}/chat/completions", payload, headers)
        return data["choices"][0]["message"]["content"]


# Module-level singleton consumed (never modified) by feature services.
claude_service = ClaudeService()
