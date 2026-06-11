"""Phase 0 smoke tests — prove the scaffold runs and the Claude mock works offline."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    """The app boots and /health returns ok — no API key required (B2)."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_mock_claude_returns_canned_json(mock_claude):
    """The mock_claude fixture returns fixed, valid JSON from a fixture file — no network."""
    from app.services.claude_service import claude_service

    raw = claude_service.complete(
        model="any-model", messages=[{"role": "user", "content": "extract tasks"}]
    )
    payload = json.loads(raw)  # must be valid JSON
    assert "tasks" in payload
    assert payload["tasks"][0]["source"] == "model-inferred"
    # Provenance fields present on every AI-derived row (A4 / A3 Rule 5).
    for task in payload["tasks"]:
        assert {"source", "confidence", "review_state"} <= set(task)


def test_mock_claude_response_is_overridable(mock_claude):
    """A test can swap the canned response for a different fixture."""
    mock_claude.set_text('{"ok": true}')
    from app.services.claude_service import claude_service

    raw = claude_service.complete(model="m", messages=[{"role": "user", "content": "x"}])
    assert json.loads(raw) == {"ok": True}
