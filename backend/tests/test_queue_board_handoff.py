"""D40 — alignment/handoff: a queue approval (manual override OR approve-as-suggested) must flow to the
Workflow Mapper board (review_state + H-band) and the AI-opportunity analysis."""
from __future__ import annotations

import json

from sqlalchemy import select

from app.models import Task
from app.services.claude_service import claude_service
from app.services.taxonomy_loader import load_taxonomies


def _ai(*, model, max_tokens=2048, messages):  # noqa: ARG001
    c = messages[0]["content"]
    if "HUMAN AGENCY SCALE BENCHMARK" in c:  # inference: H3/GREEN for all unmatched
        payload = json.loads(c.split("TASKS:\n```json\n")[1].split("\n```")[0])
        return json.dumps({"scores": [
            {"task_id": t["task_id"], "has_level": 3, "capability_score": 0.6,
             "zone": "GREEN_LIGHT", "confidence": 0.6, "rationale": "k"} for t in payload]})
    if "GROUNDING:" in c:  # no taxonomy match
        tasks = json.loads(c.split("TASKS:\n```json\n")[1].split("\n```")[0])
        return json.dumps({"benchmarks": [
            {"task_id": t["task_id"], "status": "MISSING", "matched_task_ref": None,
             "onet_task_code": None, "taxonomy_source_code": None,
             "source": "model-inferred", "confidence": 0.3} for t in tasks]})
    if "Assess the AI-transformation priority" in c:  # opportunity-matrix narrative
        return json.dumps({"priority": "High", "complexity": "Medium", "rationale": "x"})
    items = json.loads(c.split("INPUT:\n```json\n")[1].split("\n```")[0])
    return json.dumps({"extractions": [
        {"employee_key": it["employee_key"],
         "tasks": [s.strip() for s in it["work_activities"].split(";") if s.strip()]}
        for it in items]})


async def _board_task(api_client, pid, ds, text):
    b = (await api_client.get(f"/api/v1/workflows/{pid}/board", params={"dataset_id": ds})).json()
    allt = b["steps"][0]["tasks"] + b["unmapped"] if b["steps"] else b["unmapped"]
    return next(t for t in allt if t["text"] == text), b


async def test_queue_to_board_handoff_both_paths(api_client, async_session, monkeypatch):
    monkeypatch.setattr(type(claude_service), "has_api_key", property(lambda self: True))
    monkeypatch.setattr(claude_service, "complete", _ai)
    await load_taxonomies(async_session)
    cl = await api_client.post("/api/v1/engagements/clients", json={"name": "GM"})
    e = await api_client.post("/api/v1/engagements", json={"client_id": cl.json()["id"], "name": "AI"})
    eng = e.json()["id"]
    csv = ("Name,Job Title,Grade,Department,Level,Line Manager,Salary,Employee ID,Work Activities\n"
           "A,Lead,H3,Marketing,1,Top,200000,E1,Activate digital channels for events\n"
           "B,Mgr,H3,Marketing,2,A,120000,E2,Develop content strategy\n")
    ds = (await api_client.post(f"/api/v1/engagements/{eng}/datasets",
          files={"file": ("o.csv", csv.encode(), "text/csv")})).json()["id"]
    for ep in ("extract", "benchmark", "ai-opportunity", "infer-potential"):
        await api_client.post(f"/api/v1/task-intel/{ep}", params={"dataset_id": ds})

    proc = (await api_client.post("/api/v1/workflows",
            json={"engagement_id": eng, "name": "Marketing"})).json()
    pid = proc["id"]
    step = (await api_client.post(f"/api/v1/workflows/{pid}/steps", json={"name": "Planning"})).json()
    # Map both tasks to the step.
    tids = [t.id for t in await async_session.scalars(select(Task))]
    await api_client.post(f"/api/v1/workflows/steps/{step['id']}/map-tasks", json={"task_ids": tids})

    # Before review: board tasks are inferred but UNREVIEWED.
    act, _ = await _board_task(api_client, pid, ds, "Activate digital channels for events")
    assert act["human_agency_level"] == "H3" and act["review_state"] == "unreviewed"

    # PATH 1 — manual override in the queue (rate 5 = automate -> H1).
    await api_client.post("/api/v1/validation/manual-score",
                          json={"task_id": act["id"], "rating": 5})
    # PATH 2 — approve-as-suggested: select the other task's ai_score row and approve it as-is.
    q = (await api_client.get("/api/v1/validation/queue", params={"dataset_id": ds})).json()
    dev = next(i for i in q["items"]
               if i["kind"] == "ai_score" and i["task_id"] != act["id"])
    await api_client.post("/api/v1/validation/review",
                          json=[{"kind": "ai_score", "id": dev["id"], "action": "approve"}])

    # The board now reflects BOTH on a fresh load:
    act2, board = await _board_task(api_client, pid, ds, "Activate digital channels for events")
    dev2, _ = await _board_task(api_client, pid, ds, "Develop content strategy")
    # manual override → approved + the rated band (H1/GREEN_LIGHT)
    assert act2["review_state"] == "approved" and act2["human_agency_level"] == "H1"
    assert act2["zone"] == "GREEN_LIGHT"
    # approve-as-suggested → approved, inferred band kept (H3)
    assert dev2["review_state"] == "approved" and dev2["human_agency_level"] == "H3"

    # The opportunity-matrix analysis sees the reviewed bands (H1 + H3).
    matrix = (await api_client.post(f"/api/v1/workflows/{pid}/opportunity-matrix")).json()
    assert matrix["agency_matrix"]["H1"] == 1 and matrix["agency_matrix"]["H3"] == 1
