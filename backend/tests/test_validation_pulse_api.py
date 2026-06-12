"""P3.4 + P3.5 — validation API + desire-pulse export/import (dual desire scores)."""
from __future__ import annotations

import io
import json

from sqlalchemy import select

from app.models import TaskAIScore
from app.services.claude_service import claude_service
from app.services.taxonomy_loader import load_taxonomies

CSV = (
    "Name,Job Title,Grade,Department,Level,Line Manager,Salary,Employee ID,Work Activities\n"
    "Boss,CEO,SVP,Exec,1,Top of Org,300000,E1,Lead the organisation\n"
    "Cargo Joe,Cargo Officer,AO,Cargo,2,Boss,80000,E2,Process air waybills and customs documents\n"
)


def _bench(*, model, max_tokens=2048, messages):  # noqa: ARG001
    if "GROUNDING:" in messages[0]["content"]:
        tasks = json.loads(messages[0]["content"].split("TASKS:\n```json\n")[1].split("\n```")[0])
        out = [{"task_id": t["task_id"], "status": "MATCHED", "matched_task_ref": "SFW_AT_CGO_01",
                "onet_task_code": "43-5011.00", "taxonomy_source_code": "SFW_AIR_TRANSPORT",
                "source": "SFw", "confidence": 0.85} for t in tasks]
        return json.dumps({"benchmarks": out})
    items = json.loads(messages[0]["content"].split("INPUT:\n```json\n")[1].split("\n```")[0])
    return json.dumps({"extractions": [
        {"employee_key": it["employee_key"],
         "tasks": [s.strip() for s in it["work_activities"].split(";") if s.strip()]}
        for it in items
    ]})


async def _run_pipeline(api_client, async_session, monkeypatch):
    monkeypatch.setattr(type(claude_service), "has_api_key", property(lambda self: True))
    monkeypatch.setattr(claude_service, "complete", _bench)
    await load_taxonomies(async_session)
    c = await api_client.post("/api/v1/engagements/clients", json={"name": "PAX"})
    e = await api_client.post("/api/v1/engagements",
                              json={"client_id": c.json()["id"], "name": "TOM"})
    eng_id = e.json()["id"]
    files = {"file": ("org.csv", CSV.encode(), "text/csv")}
    ds = await api_client.post(f"/api/v1/engagements/{eng_id}/datasets", files=files)
    ds_id = ds.json()["id"]
    await api_client.post("/api/v1/task-intel/extract", params={"dataset_id": ds_id})
    await api_client.post("/api/v1/task-intel/benchmark", params={"dataset_id": ds_id})
    await api_client.post("/api/v1/task-intel/ai-opportunity", params={"dataset_id": ds_id})
    return eng_id, ds_id


async def test_validation_queue_and_review_api(api_client, async_session, monkeypatch):
    _, ds_id = await _run_pipeline(api_client, async_session, monkeypatch)

    q = await api_client.get("/api/v1/validation/queue", params={"max_confidence": 0.70})
    assert q.status_code == 200
    crosswalks = [i for i in q.json()["items"] if i["kind"] == "crosswalk"]
    assert any(abs((i["confidence"] or 0) - 0.40) < 1e-9 for i in crosswalks)  # seed 0.40 row

    # Approve a matched benchmark -> learns a CURATED_BY_CONSULTANT crosswalk. (High-confidence
    # benchmarks load as 'approved', so include_reviewed=true to surface them for the demo.)
    bench_items = [i for i in (await api_client.get("/api/v1/validation/queue",
                   params={"dataset_id": ds_id, "include_reviewed": True})).json()["items"]
                   if i["kind"] == "benchmark" and "43-5011.00" in i["label"]]
    assert bench_items
    review = await api_client.post("/api/v1/validation/review",
                                   json=[{"kind": "benchmark", "id": bench_items[0]["id"],
                                          "action": "approve"}])
    assert review.json()["updated"] == 1
    assert review.json()["crosswalks_created"] == 1

    stats = await api_client.get("/api/v1/validation/stats")
    assert "benchmark" in stats.json()


async def test_pulse_export_import_sets_local_not_us(api_client, async_session, monkeypatch):
    eng_id, ds_id = await _run_pipeline(api_client, async_session, monkeypatch)

    # Export the instrument (xlsx) — must be a non-empty workbook.
    inst = await api_client.get("/api/v1/task-intel/pulse/instrument.xlsx",
                                params={"dataset_id": ds_id})
    assert inst.status_code == 200
    assert inst.content[:2] == b"PK"  # xlsx is a zip

    # Capture US score before import.
    before = await async_session.scalar(select(TaskAIScore))
    us_before = before.desire_score_us

    # Import responses (CSV) rating SFW_AT_CGO_01 high (5,4) -> local desire ~0.875.
    resp_csv = "task_ref,desire_rating\nSFW_AT_CGO_01,5\nSFW_AT_CGO_01,4\n"
    files = {"file": ("responses.csv", resp_csv.encode(), "text/csv")}
    imp = await api_client.post("/api/v1/task-intel/pulse/responses",
                                params={"engagement_id": eng_id, "dataset_id": ds_id}, files=files)
    assert imp.status_code == 200
    assert imp.json()["responses_stored"] == 2
    assert imp.json()["scores_updated"] >= 1

    async_session.expire_all()
    cargo = await async_session.scalar(
        select(TaskAIScore).where(TaskAIScore.desire_score_local.isnot(None))
    )
    assert cargo is not None
    assert abs(cargo.desire_score_local - 0.875) < 1e-6  # (mean 4.5 -1)/4
    assert cargo.desire_score_us == us_before  # US score never overwritten (A4)
