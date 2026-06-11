"""Claude API singleton.

Feature services CONSUME this singleton and never modify it (Build Spec B2). Every Claude call in
the app routes through `ClaudeService.complete(...)`, which is the single method tests monkeypatch
via the `mock_claude` fixture (Build Spec A3, Rule 1) so the suite runs offline, deterministically,
and free.

In Phase 0 this is intentionally minimal: it lazily constructs the Anthropic client (only if an API
key is configured) and exposes one method. Real prompt/parse logic arrives with the AI pipeline in
Phase 2.
"""
from __future__ import annotations

from ..config import settings


class ClaudeService:
    """Thin wrapper around the Anthropic client. Model strings come from env config (A4)."""

    def __init__(self) -> None:
        self._client = None  # lazily created so the app runs with no API key

    @property
    def has_api_key(self) -> bool:
        return bool(settings.ANTHROPIC_API_KEY)

    def _get_client(self):
        """Lazily build the Anthropic client. Raises if no API key is configured."""
        if self._client is None:
            if not settings.ANTHROPIC_API_KEY:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY is not set — AI endpoints require an API key (B2)."
                )
            from anthropic import Anthropic  # imported lazily to keep non-AI paths key-free

            self._client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        return self._client

    def complete(self, *, model: str, max_tokens: int = 2048, messages: list[dict]) -> str:
        """Send a messages request and return the first text block.

        This is the single seam tests patch. Returns the raw text of `response.content[0].text`;
        callers parse JSON via the shared `_json_utils` helpers (ported in Phase 0 from legacy).
        """
        client = self._get_client()
        response = client.messages.create(
            model=model, max_tokens=max_tokens, messages=messages
        )
        return response.content[0].text


# Module-level singleton consumed (never modified) by feature services.
claude_service = ClaudeService()
