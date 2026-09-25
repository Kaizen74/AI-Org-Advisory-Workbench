"""Verify the app can run the AI pipeline against a LOCAL LLM via LM Studio (D11).

LM Studio serves an OpenAI-compatible API at http://localhost:1234/v1. These tests configure the
local provider with an LM Studio URL + a Qwen model and confirm the full pipeline routes there.
The HTTP seam (`_post_local`) is stubbed so no real local server is required for the test.
"""
from __future__ import annotations

import json

import pytest

from app.services import settings_service as ss
from app.services.claude_service import claude_service

LMSTUDIO_URL = "http://localhost:1234/v1"
QWEN_MODEL = "qwen3-27b-instruct"


@pytest.fixture(autouse=True)
def _reset():
    ss.reset_cache_for_tests()
    claude_service._anthropic_client = None
    claude_service._anthropic_key_used = None
    yield
    ss.reset_cache_for_tests()


def _lmstudio_stub(capture):
    """A fake LM Studio /chat/completions: echoes work-activities into extraction JSON."""
    def _post(url, payload, headers):
        capture["url"] = url
        capture["model"] = payload["model"]
        content = payload["messages"][0]["content"]
        if "INPUT:\n```json" in content:
            items = json.loads(content.split("INPUT:\n```json\n")[1].split("\n```")[0])
            body = json.dumps({"extractions": [
                {"employee_key": it["employee_key"],
                 "tasks": [s.strip() for s in it["work_activities"].split(";") if s.strip()]}
                for it in items]})
        else:
            body = "ok"
        # LM Studio returns the standard OpenAI chat-completion shape.
        return {"choices": [{"message": {"role": "assistant", "content": body}}]}
    return _post


def test_complete_routes_to_lmstudio(monkeypatch):
    ss._cache["llm_provider"] = "local"
    ss._cache["local_base_url"] = LMSTUDIO_URL
    ss._cache["local_model"] = QWEN_MODEL
    cap = {}
    monkeypatch.setattr(claude_service, "_post_local", _lmstudio_stub(cap))

    out = claude_service.complete(model="claude-opus-4-8",
                                  messages=[{"role": "user", "content": "ping"}])
    assert out == "ok"
    assert cap["url"] == "http://localhost:1234/v1/chat/completions"  # LM Studio endpoint
    assert cap["model"] == QWEN_MODEL  # uses the configured Qwen model, not the Anthropic one


def test_has_api_key_true_for_lmstudio_without_anthropic_key():
    ss._cache["llm_provider"] = "local"
    ss._cache["anthropic_api_key"] = ""
    ss._cache["local_base_url"] = LMSTUDIO_URL
    assert claude_service.has_api_key is True  # local provider needs no Anthropic key


async def test_full_extract_pipeline_through_lmstudio(api_client, async_session, monkeypatch):
    # Point the app at LM Studio + Qwen, as Eric would in Settings.
    await api_client.put("/api/v1/settings", json={
        "llm_provider": "local", "local_base_url": LMSTUDIO_URL, "local_model": QWEN_MODEL,
    })
    cap = {}
    monkeypatch.setattr(claude_service, "_post_local", _lmstudio_stub(cap))

    c = await api_client.post("/api/v1/engagements/clients", json={"name": "PAX"})
    e = await api_client.post("/api/v1/engagements",
                              json={"client_id": c.json()["id"], "name": "TOM"})
    csv = ("Name,Job Title,Grade,Department,Level,Line Manager,Salary,Employee ID,Work Activities\n"
           "Joe,Officer,AO,Cargo,1,Top of Org,80000,E1,Process waybills; Reconcile manifests\n")
    ds = await api_client.post(f"/api/v1/engagements/{e.json()['id']}/datasets",
                               files={"file": ("o.csv", csv.encode(), "text/csv")})

    r = await api_client.post("/api/v1/task-intel/extract", params={"dataset_id": ds.json()["id"]})
    assert r.status_code == 200
    assert r.json()["tasks_created"] == 2  # extracted via LM Studio/Qwen
    assert cap["url"].endswith("/v1/chat/completions") and cap["model"] == QWEN_MODEL


async def test_test_llm_button_against_lmstudio(api_client, monkeypatch):
    await api_client.put("/api/v1/settings", json={
        "llm_provider": "local", "local_base_url": LMSTUDIO_URL, "local_model": QWEN_MODEL,
    })
    monkeypatch.setattr(claude_service, "_post_local",
                        lambda url, payload, headers: {"choices": [{"message": {"content": "ok"}}]})
    r = await api_client.post("/api/v1/settings/test-llm")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["provider"] == "local"
