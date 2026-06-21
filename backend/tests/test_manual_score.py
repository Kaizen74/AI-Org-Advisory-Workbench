"""D31 — inline Validation-Queue manual override of AI opportunity for no-benchmark tasks,
and the override shows in the Workflow Mapper board."""
from __future__ import annotations

import json

from sqlalchemy import select

from app.models import Task, TaskAIScore
from app.services.claude_service import claude_service
from app.services.taxonomy_loader import load_taxonomies


def _ai(*, model, max_tokens=2048, messages):  # noqa: ARG001
    c = messages[0]["content"]
    if "GROUNDING:" in c:  # nothing matches -> NO_BENCHMARK_MATCH
        tasks = json.loads(c.split("TASKS:\n```json\n")[1].split("\n```")[0])
        return json.dumps({"benchmarks": [
            {"task_id": t["task_id"], "status": "MISSING", "matched_task_ref": None,
             "onet_task_code": None, "taxonomy_source_code": None,
             "source": "model-inferred", "confidence": 0.3} for t in tasks]})
    items = json.loads(c.split("INPUT:\n```json\n")[1].split("\n```")[0])
    return json.dumps({"extractions": [
        {"employee_key": it["employee_key"],
         "tasks": [s.strip() for s in it["work_activities"].split(";") if s.strip()]}
        for it in items]})


async def test_manual_score_sets_consultant_opportunity_and_shows_on_board(
    api_client, async_session, monkeypatch
):
    monkeypatch.setattr(type(claude_service), "has_api_key", property(lambda self: True))
    monkeypatch.setattr(claude_service, "complete", _ai)
    await load_taxonomies(async_session)
    cl = await api_client.post("/api/v1/engagements/clients", json={"name": "GM"})
    e = await api_client.post("/api/v1/engagements", json={"client_id": cl.json()["id"], "name": "AI"})
    eng = e.json()["id"]
    csv = ("Name,Job Title,Grade,Department,Level,Line Manager,Salary,Employee ID,Work Activities\n"
           "A,Lead,H3,Marketing,1,Top,200000,E1,Write copy for digital content\n")
    ds = (await api_client.post(f"/api/v1/engagements/{eng}/datasets",
          files={"file": ("o.csv", csv.encode(), "text/csv")})).json()["id"]
    await api_client.post("/api/v1/task-intel/extract", params={"dataset_id": ds})
    await api_client.post("/api/v1/task-intel/benchmark", params={"dataset_id": ds})
    await api_client.post("/api/v1/task-intel/ai-opportunity", params={"dataset_id": ds})

    # The queue shows the no-benchmark ai_score row AND a benchmark EXTRA row for the same task —
    # both now carry a task_id so the manual override is reachable from either.
    q = (await api_client.get("/api/v1/validation/queue", params={"dataset_id": ds})).json()
    ai = next(i for i in q["items"] if i["kind"] == "ai_score")
    bench = next(i for i in q["items"] if i["kind"] == "benchmark")
    assert "NO_BENCHMARK_MATCH" in ai["label"] and ai["review_state"] == "unreviewed"
    assert ai["task_id"] and bench["task_id"]

    # Inline override (keyed by task_id): rate 5 (=automate) -> H1/GREEN_LIGHT, consultant-approved.
    r = await api_client.post("/api/v1/validation/manual-score",
                              json={"task_id": ai["task_id"], "rating": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["human_agency_level"] == "H1" and body["zone"] == "GREEN_LIGHT"
    assert body["review_state"] == "approved" and body["source"] == "consultant-approved"

    score = await async_session.get(TaskAIScore, ai["id"])
    async_session.expire_all()
    score = await async_session.get(TaskAIScore, ai["id"])
    assert score.has_level == 1 and score.review_state == "approved"

    # The override shows in the Workflow Mapper board (board reads TaskAIScore).
    proc = (await api_client.post("/api/v1/workflows",
            json={"engagement_id": eng, "name": "P"})).json()
    board = (await api_client.get(f"/api/v1/workflows/{proc['id']}/board",
                                  params={"dataset_id": ds})).json()
    t = next(x for x in board["unmapped"] if x["id"] == ai["task_id"])
    assert t["human_agency_level"] == "H1" and t["zone"] == "GREEN_LIGHT" and t["review_state"] == "approved"

    # The same override is reachable from the benchmark (EXTRA) row of that task (same task_id).
    r2 = await api_client.post("/api/v1/validation/manual-score",
                               json={"task_id": bench["task_id"], "rating": 1})
    assert r2.status_code == 200 and r2.json()["human_agency_level"] == "H5"

    # Guards.
    assert (await api_client.post("/api/v1/validation/manual-score",
                                  json={"task_id": "nope", "rating": 3})).status_code == 404
    assert (await api_client.post("/api/v1/validation/manual-score",
                                  json={"task_id": ai["task_id"], "rating": 9})).status_code == 400
