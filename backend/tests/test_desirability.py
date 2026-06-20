"""D30 — local desirability CSV → consultant AI opportunity for tasks with no valid benchmark."""
from __future__ import annotations

import csv
import io
import json

from sqlalchemy import select

from app.models import Task, TaskAIScore
from app.services.claude_service import claude_service
from app.services.taxonomy_loader import load_taxonomies


def _ai(*, model, max_tokens=2048, messages):  # noqa: ARG001
    c = messages[0]["content"]
    if "GROUNDING:" in c:  # nothing matches → all NO_BENCHMARK_MATCH
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


async def _setup(api_client, async_session, monkeypatch):
    monkeypatch.setattr(type(claude_service), "has_api_key", property(lambda self: True))
    monkeypatch.setattr(claude_service, "complete", _ai)
    await load_taxonomies(async_session)
    cl = await api_client.post("/api/v1/engagements/clients", json={"name": "GM"})
    e = await api_client.post("/api/v1/engagements", json={"client_id": cl.json()["id"], "name": "AI"})
    eng = e.json()["id"]
    csv_text = ("Name,Job Title,Grade,Department,Level,Line Manager,Salary,Employee ID,Work Activities\n"
                "A,Lead,H3,Marketing,1,Top,200000,E1,Write copy for digital content\n"
                "B,Mgr,H3,Marketing,2,A,120000,E2,Oversee internal communications\n")
    ds = (await api_client.post(f"/api/v1/engagements/{eng}/datasets",
          files={"file": ("o.csv", csv_text.encode(), "text/csv")})).json()["id"]
    await api_client.post("/api/v1/task-intel/extract", params={"dataset_id": ds})
    await api_client.post("/api/v1/task-intel/benchmark", params={"dataset_id": ds})
    await api_client.post("/api/v1/task-intel/ai-opportunity", params={"dataset_id": ds})
    return eng, ds


async def test_template_lists_unbenchmarked_then_apply_sets_consultant_opportunity(
    api_client, async_session, monkeypatch
):
    eng, ds = await _setup(api_client, async_session, monkeypatch)

    # Template: real headers + one row per unbenchmarked task (keyed by task id).
    tpl = await api_client.get("/api/v1/task-intel/desirability-template.csv", params={"dataset_id": ds})
    assert tpl.status_code == 200
    rows = list(csv.DictReader(io.StringIO(tpl.text)))
    assert {"task_ref", "task_text"}.issubset({k.split(" ")[0] for k in rows[0].keys()})
    assert len(rows) == 2  # both tasks unmatched

    # Fill ratings: 5=automate for the copy task, 1=keep-human for comms.
    task_by_text = {(await async_session.get(Task, s.task_id)).task_text: s.task_id
                    for s in await async_session.scalars(select(TaskAIScore))}
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["task_ref", "task_text", "desire_rating (1=keep human .. 5=automate)"])
    w.writerow([task_by_text["Write copy for digital content"], "Write copy for digital content", 5])
    w.writerow([task_by_text["Oversee internal communications"], "Oversee internal communications", 1])

    res = await api_client.post("/api/v1/task-intel/desirability", params={"dataset_id": ds},
                                files={"file": ("d.csv", out.getvalue().encode(), "text/csv")})
    assert res.status_code == 200 and res.json()["applied"] == 2

    scores = {(await async_session.get(Task, s.task_id)).task_text: s
              for s in await async_session.scalars(select(TaskAIScore))}
    async_session.expire_all()
    scores = {(await async_session.get(Task, s.task_id)).task_text: s
              for s in await async_session.scalars(select(TaskAIScore))}
    copy = scores["Write copy for digital content"]
    comms = scores["Oversee internal communications"]
    assert copy.source == "consultant-approved" and copy.review_state == "approved"
    assert copy.has_level == 1 and copy.zone == "GREEN_LIGHT"      # 5=automate → H1
    assert copy.desire_score_local == 1.0
    assert comms.has_level == 5 and comms.zone == "RED_LIGHT"      # 1=keep human → H5
    assert comms.desire_score_local == 0.0

    # Now client-ready: the queue no longer shows them as unreviewed model-inferred.
    q = (await api_client.get("/api/v1/validation/queue", params={"dataset_id": ds})).json()
    ai = [i for i in q["items"] if i["kind"] == "ai_score"]
    assert all(i["review_state"] == "approved" for i in ai)
