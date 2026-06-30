"""Workflow Mapper board + drag-to-remap API (board / move-task / unmap-task).

These endpoints back the visual Workflow Mapper. They read persisted task→step links and
per-task AI scores (no Anthropic key needed for the board itself). The AI mock mirrors
test_workflow_transition_api.py so extract/benchmark/ai-opportunity populate real scores.
"""
from __future__ import annotations

import json

from sqlalchemy import select

from app.models import Task
from app.services.claude_service import claude_service
from app.services.taxonomy_loader import load_taxonomies

CSV = (
    "Name,Job Title,Grade,Department,Level,Line Manager,Salary,Employee ID,Work Activities\n"
    "Boss,Director,SVP,Cargo,1,Top of Org,300000,E1,Lead the cargo function\n"
    "Cargo Joe,Cargo Officer,AO,Cargo,2,Boss,80000,E2,Process air waybills; reconcile customs documents\n"
)


def _ai(*, model, max_tokens=2048, messages):  # noqa: ARG001
    c = messages[0]["content"]
    if "GROUNDING:" in c:
        tasks = json.loads(c.split("TASKS:\n```json\n")[1].split("\n```")[0])
        return json.dumps({"benchmarks": [
            {"task_id": t["task_id"], "status": "MATCHED", "matched_task_ref": "SFW_AT_CGO_01",
             "onet_task_code": "43-5011.00", "taxonomy_source_code": "SFW_AIR_TRANSPORT",
             "source": "SFw", "confidence": 0.85} for t in tasks]})
    if "INPUT:\n```json" in c:
        items = json.loads(c.split("INPUT:\n```json\n")[1].split("\n```")[0])
        return json.dumps({"extractions": [
            {"employee_key": it["employee_key"],
             "tasks": [s.strip() for s in it["work_activities"].split(";") if s.strip()]}
            for it in items]})
    return json.dumps({"priority": "High", "complexity": "Medium", "rationale": "Many L3 tasks."})


async def _setup(api_client, async_session, monkeypatch):
    monkeypatch.setattr(type(claude_service), "has_api_key", property(lambda self: True))
    monkeypatch.setattr(claude_service, "complete", _ai)
    await load_taxonomies(async_session)
    c = await api_client.post("/api/v1/engagements/clients", json={"name": "PAX"})
    e = await api_client.post("/api/v1/engagements",
                              json={"client_id": c.json()["id"], "name": "TOM"})
    eng_id = e.json()["id"]
    ds = await api_client.post(f"/api/v1/engagements/{eng_id}/datasets",
                               files={"file": ("o.csv", CSV.encode(), "text/csv")})
    ds_id = ds.json()["id"]
    await api_client.post("/api/v1/task-intel/extract", params={"dataset_id": ds_id})
    await api_client.post("/api/v1/task-intel/benchmark", params={"dataset_id": ds_id})
    await api_client.post("/api/v1/task-intel/ai-opportunity", params={"dataset_id": ds_id})
    return eng_id, ds_id


async def test_board_lists_unmapped_then_mapped(api_client, async_session, monkeypatch):
    eng_id, ds_id = await _setup(api_client, async_session, monkeypatch)
    proc = await api_client.post("/api/v1/workflows",
                                 json={"engagement_id": eng_id, "name": "Cargo Acceptance",
                                       "value_stream": "Cargo"})
    pid = proc.json()["id"]
    s1 = (await api_client.post(f"/api/v1/workflows/{pid}/steps", json={"name": "Acceptance"})).json()
    s2 = (await api_client.post(f"/api/v1/workflows/{pid}/steps", json={"name": "Documentation"})).json()

    # Fresh board: every extracted task is unmapped, steps are empty.
    board = (await api_client.get(f"/api/v1/workflows/{pid}/board",
                                  params={"dataset_id": ds_id})).json()
    assert board["task_count"] >= 1
    assert board["mapped_count"] == 0
    assert len(board["unmapped"]) == board["task_count"]
    # Real per-task fields are present and carry the role (job_title), not a name.
    t0 = board["unmapped"][0]
    # role drives the role-rollup; capability_score/desire_score drive the landscape axes (D42).
    for key in ("id", "text", "role", "human_agency_level", "ai_level", "review_state", "step_id",
                "capability_score", "desire_score"):
        assert key in t0
    assert t0["role"] in {"Director", "Cargo Officer", "Unassigned"}
    assert t0["step_id"] is None
    # Headline AI-potential is the WORKBank Human Agency Scale (H0-H5); L0-L3 retained as secondary.
    assert all(t["human_agency_level"] in {"H0", "H1", "H2", "H3", "H4", "H5"}
               for t in board["unmapped"])
    assert set(board["human_agency_scale"]) == {"H0", "H1", "H2", "H3", "H4", "H5"}

    # Map a task to step 1, re-fetch: it appears under the step, not in unmapped.
    tid = t0["id"]
    await api_client.post(f"/api/v1/workflows/steps/{s1['id']}/map-tasks",
                          json={"task_ids": [tid]})
    board = (await api_client.get(f"/api/v1/workflows/{pid}/board",
                                  params={"dataset_id": ds_id})).json()
    step1 = next(s for s in board["steps"] if s["id"] == s1["id"])
    assert any(t["id"] == tid for t in step1["tasks"])
    assert board["mapped_count"] == 1
    assert all(t["id"] != tid for t in board["unmapped"])

    # Move the task from step 1 -> step 2.
    mv = await api_client.post(f"/api/v1/workflows/{pid}/move-task",
                               json={"task_id": tid, "to_step_id": s2["id"]})
    assert mv.json()["step_id"] == s2["id"]
    board = (await api_client.get(f"/api/v1/workflows/{pid}/board",
                                  params={"dataset_id": ds_id})).json()
    step1 = next(s for s in board["steps"] if s["id"] == s1["id"])
    step2 = next(s for s in board["steps"] if s["id"] == s2["id"])
    assert all(t["id"] != tid for t in step1["tasks"])
    assert any(t["id"] == tid for t in step2["tasks"])

    # Unmap it: back to the unmapped tray.
    await api_client.post(f"/api/v1/workflows/{pid}/unmap-task", json={"task_id": tid})
    board = (await api_client.get(f"/api/v1/workflows/{pid}/board",
                                  params={"dataset_id": ds_id})).json()
    assert any(t["id"] == tid for t in board["unmapped"])
    assert board["mapped_count"] == 0


async def test_reset_board_clears_all_mappings(api_client, async_session, monkeypatch):
    eng_id, ds_id = await _setup(api_client, async_session, monkeypatch)
    proc = await api_client.post("/api/v1/workflows",
                                 json={"engagement_id": eng_id, "name": "Cargo Acceptance"})
    pid = proc.json()["id"]
    s1 = (await api_client.post(f"/api/v1/workflows/{pid}/steps", json={"name": "Acceptance"})).json()
    board = (await api_client.get(f"/api/v1/workflows/{pid}/board",
                                  params={"dataset_id": ds_id})).json()
    tids = [t["id"] for t in board["unmapped"][:2]]
    await api_client.post(f"/api/v1/workflows/steps/{s1['id']}/map-tasks", json={"task_ids": tids})

    reset = await api_client.post(f"/api/v1/workflows/{pid}/reset-board")
    assert reset.status_code == 200
    assert reset.json()["unmapped"] == len(tids)
    board = (await api_client.get(f"/api/v1/workflows/{pid}/board",
                                  params={"dataset_id": ds_id})).json()
    assert board["mapped_count"] == 0
    assert all(len(s["tasks"]) == 0 for s in board["steps"])

    # Idempotent + 404 guard.
    assert (await api_client.post(f"/api/v1/workflows/{pid}/reset-board")).json()["unmapped"] == 0
    assert (await api_client.post("/api/v1/workflows/nope/reset-board")).status_code == 404


async def test_board_404_for_unknown_process(api_client, async_session, monkeypatch):
    _eng, ds_id = await _setup(api_client, async_session, monkeypatch)
    r = await api_client.get("/api/v1/workflows/does-not-exist/board",
                             params={"dataset_id": ds_id})
    assert r.status_code == 404


async def test_move_task_rejects_foreign_step(api_client, async_session, monkeypatch):
    eng_id, ds_id = await _setup(api_client, async_session, monkeypatch)
    p1 = (await api_client.post("/api/v1/workflows",
                                json={"engagement_id": eng_id, "name": "P1"})).json()
    p2 = (await api_client.post("/api/v1/workflows",
                                json={"engagement_id": eng_id, "name": "P2"})).json()
    foreign_step = (await api_client.post(f"/api/v1/workflows/{p2['id']}/steps",
                                          json={"name": "Other"})).json()
    tid = (await async_session.scalars(select(Task))).first().id
    r = await api_client.post(f"/api/v1/workflows/{p1['id']}/move-task",
                              json={"task_id": tid, "to_step_id": foreign_step["id"]})
    assert r.status_code == 404
