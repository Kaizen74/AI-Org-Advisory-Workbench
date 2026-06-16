"""P5.3 + P5.5 — Workflow Mapper + Transition Planner API (mocked AI)."""
from __future__ import annotations

import json

from sqlalchemy import select

from app.models import Task
from app.services.claude_service import claude_service
from app.services.taxonomy_loader import load_taxonomies

CSV = (
    "Name,Job Title,Grade,Department,Level,Line Manager,Salary,Employee ID,Work Activities\n"
    "Boss,Director,SVP,Cargo,1,Top of Org,300000,E1,Lead the cargo function\n"
    "Cargo Joe,Cargo Officer,AO,Cargo,2,Boss,80000,E2,Process air waybills and customs documents\n"
)


def _ai(*, model, max_tokens=2048, messages):  # noqa: ARG001
    c = messages[0]["content"]
    if "GROUNDING:" in c:  # benchmark
        tasks = json.loads(c.split("TASKS:\n```json\n")[1].split("\n```")[0])
        return json.dumps({"benchmarks": [
            {"task_id": t["task_id"], "status": "MATCHED", "matched_task_ref": "SFW_AT_CGO_01",
             "onet_task_code": "43-5011.00", "taxonomy_source_code": "SFW_AIR_TRANSPORT",
             "source": "SFw", "confidence": 0.85} for t in tasks]})
    if "INPUT:\n```json" in c:  # extraction
        items = json.loads(c.split("INPUT:\n```json\n")[1].split("\n```")[0])
        return json.dumps({"extractions": [
            {"employee_key": it["employee_key"],
             "tasks": [s.strip() for s in it["work_activities"].split(";") if s.strip()]}
            for it in items]})
    if "reskilling pathways" in c or "ROLES:" in c:  # transition pathways
        roles = json.loads(c.split("ROLES:\n```json\n")[1].split("\n```")[0])
        return json.dumps({"pathways": [
            {"employee_key": r["employee_key"], "skill_gaps": ["AI literacy"],
             "suggested_pathway": "SFw AI Associate pathway"} for r in roles]})
    # priority/complexity narrative
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
    await api_client.post("/api/v1/diagnostics/compute", params={"dataset_id": ds_id})
    return eng_id, ds_id


async def test_workflow_mapping_and_opportunity_matrix(api_client, async_session, monkeypatch):
    eng_id, ds_id = await _setup(api_client, async_session, monkeypatch)

    proc = await api_client.post("/api/v1/workflows",
                                 json={"engagement_id": eng_id, "name": "Cargo Acceptance",
                                       "value_stream": "Cargo"})
    pid = proc.json()["id"]
    step = await api_client.post(f"/api/v1/workflows/{pid}/steps", json={"name": "Documentation"})
    step_id = step.json()["id"]

    task_ids = [t.id for t in await async_session.scalars(select(Task))]
    mapped = await api_client.post(f"/api/v1/workflows/steps/{step_id}/map-tasks",
                                   json={"task_ids": task_ids})
    assert mapped.json()["linked"] == len(task_ids)

    matrix = await api_client.post(f"/api/v1/workflows/{pid}/opportunity-matrix")
    body = matrix.json()
    assert body["matrix"]["L3"] >= 1  # cargo doc task scored L3
    assert body["assessment"]["priority"] == "High"
    assert body["assessment"]["review_state"] == "unreviewed"
    assert any("occupation-level" in c for c in body["caveats"])


async def test_steps_listed_with_counts_and_matrix_reflects_linked_count(
    api_client, async_session, monkeypatch
):
    """GET steps must surface each step + its linked-task count, and the matrix must aggregate
    exactly the linked tasks (the Workflow Mapper relies on this to show a connected result)."""
    eng_id, ds_id = await _setup(api_client, async_session, monkeypatch)

    proc = await api_client.post("/api/v1/workflows",
                                 json={"engagement_id": eng_id, "name": "Cargo Acceptance"})
    pid = proc.json()["id"]

    # New process has no steps.
    assert (await api_client.get(f"/api/v1/workflows/{pid}/steps")).json()["steps"] == []

    step = await api_client.post(f"/api/v1/workflows/{pid}/steps", json={"name": "Documentation"})
    step_id = step.json()["id"]
    assert step.json()["linked_tasks"] == 0

    task_ids = [t.id for t in await async_session.scalars(select(Task))]
    assert len(task_ids) >= 2
    # Link only a subset and confirm the count + matrix total track it exactly.
    subset = task_ids[:2]
    await api_client.post(f"/api/v1/workflows/steps/{step_id}/map-tasks",
                          json={"task_ids": subset})

    listed = (await api_client.get(f"/api/v1/workflows/{pid}/steps")).json()["steps"]
    assert len(listed) == 1
    assert listed[0]["linked_tasks"] == len(subset)
    # linked_task_ids drives the coverage view (what's linked vs left); ids match the count + set.
    assert sorted(listed[0]["linked_task_ids"]) == sorted(subset)

    body = (await api_client.post(f"/api/v1/workflows/{pid}/opportunity-matrix")).json()
    assert sum(body["matrix"].values()) == len(subset)  # matrix reflects exactly the linked tasks
    # Evidencing tasks tie the counts back to real task text.
    evidencing = [t for lvl in body["evidencing_tasks"].values() for t in lvl]
    assert len(evidencing) == len(subset)


async def test_steps_404_for_missing_process(api_client, monkeypatch):
    monkeypatch.setattr(type(claude_service), "has_api_key", property(lambda self: True))
    r = await api_client.get("/api/v1/workflows/nope/steps")
    assert r.status_code == 404


async def test_transition_compute_and_register(api_client, async_session, monkeypatch):
    eng_id, ds_id = await _setup(api_client, async_session, monkeypatch)

    s = await api_client.post("/api/v1/scenarios",
                              json={"engagement_id": eng_id, "dataset_id": ds_id, "name": "Lean"})
    sid = s.json()["id"]
    await api_client.post(f"/api/v1/scenarios/{sid}/moves",
                          json={"move_type": "CHANGE_GRADE",
                                "params": {"employee_key": "E2", "grade": "H5"}})
    await api_client.post(f"/api/v1/scenarios/{sid}/moves",
                          json={"move_type": "ADD_POSITION",
                                "params": {"employee_key": "E3", "manager_key": "E1",
                                           "grade": "H6", "level": 2, "salary": 100000}})

    comp = await api_client.post("/api/v1/transition/compute", params={"scenario_id": sid})
    body = comp.json()
    assert body["summary"]["augmented"] == 1  # E2 regrade
    assert body["summary"]["new"] == 1        # E3 added
    assert body["summary"]["unchanged"] == 1  # E1 untouched

    e2 = next(r for r in body["register"] if r["employee_key"] == "E2")
    assert e2["impact_class"] == "augmented"
    assert e2["suggested_pathway"] == "SFw AI Associate pathway"
    assert e2["source"] == "model-inferred" and e2["review_state"] == "unreviewed"

    # xlsx export.
    xlsx = await api_client.get("/api/v1/transition/register.xlsx", params={"scenario_id": sid})
    assert xlsx.status_code == 200
    assert xlsx.content[:2] == b"PK"


async def test_transition_requires_key(api_client, monkeypatch):
    monkeypatch.setattr(type(claude_service), "has_api_key", property(lambda self: False))
    r = await api_client.post("/api/v1/transition/compute", params={"scenario_id": "x"})
    assert r.status_code == 400
