"""D29 — integrated layered benchmarking: real WORKBank overlay + Claude HAS inference + robotics,
all coexisting on one mixed dataset, with the source-mix reflecting reality (no regressions)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import TaskAIScore, Task
from app.services import taxonomy_loader
from app.services.claude_service import claude_service
from app.services.taxonomy_loader import load_taxonomies

pytestmark = pytest.mark.asyncio

OVERLAY = (Path(taxonomy_loader.__file__).resolve().parents[1]
           / "resources" / "taxonomies" / "workbank_overlay.curated.json")


def _ai(*, model, max_tokens=2048, messages):  # noqa: ARG001
    c = messages[0]["content"]
    if "HUMAN AGENCY SCALE BENCHMARK" in c:  # inference fallback for unmatched/robotics
        payload = json.loads(c.split("TASKS:\n```json\n")[1].split("\n```")[0])
        out = []
        for t in payload:
            low = t["task_text"].lower()
            if "load" in low or "truck" in low:  # physical → stays a robotics lever
                out.append({"task_id": t["task_id"], "has_level": None, "capability_score": None,
                            "zone": "ROBOTICS_GSE_LEVER", "confidence": 0.5, "rationale": "Physical."})
            else:
                out.append({"task_id": t["task_id"], "has_level": 3, "capability_score": 0.55,
                            "zone": "RED_LIGHT", "confidence": 0.6, "rationale": "Knowledge task."})
        return json.dumps({"scores": out})
    if "GROUNDING:" in c:  # mixed benchmark: WORKBank-covered / physical-no-overlay / no-match
        tasks = json.loads(c.split("TASKS:\n```json\n")[1].split("\n```")[0])
        out = []
        for t in tasks:
            low = t["task_text"].lower()
            if "search marketing" in low:
                out.append({"task_id": t["task_id"], "status": "MATCHED", "matched_task_ref": "wb",
                            "onet_task_code": "13-1161.01", "taxonomy_source_code": "WORKBANK",
                            "source": "WORKBank", "confidence": 0.9})
            elif "load" in low or "truck" in low:
                out.append({"task_id": t["task_id"], "status": "MATCHED", "matched_task_ref": "x",
                            "onet_task_code": "53-7062.00", "taxonomy_source_code": "ONET",
                            "source": "ONET", "confidence": 0.6})
            else:
                out.append({"task_id": t["task_id"], "status": "MISSING", "matched_task_ref": None,
                            "onet_task_code": None, "taxonomy_source_code": None,
                            "source": "model-inferred", "confidence": 0.3})
        return json.dumps({"benchmarks": out})
    items = json.loads(c.split("INPUT:\n```json\n")[1].split("\n```")[0])
    return json.dumps({"extractions": [
        {"employee_key": it["employee_key"],
         "tasks": [s.strip() for s in it["work_activities"].split(";") if s.strip()]}
        for it in items]})


async def test_layered_benchmarking_end_to_end(api_client, async_session, monkeypatch):
    if not OVERLAY.exists():
        pytest.skip("committed WORKBank overlay absent")
    monkeypatch.setattr(taxonomy_loader, "WORKBANK_OVERLAY_PATH", OVERLAY)  # overrides autouse isolation
    monkeypatch.setattr(type(claude_service), "has_api_key", property(lambda self: True))
    monkeypatch.setattr(claude_service, "complete", _ai)
    await load_taxonomies(async_session)

    cl = await api_client.post("/api/v1/engagements/clients", json={"name": "Global Marketing"})
    e = await api_client.post("/api/v1/engagements", json={"client_id": cl.json()["id"], "name": "AI"})
    eng = e.json()["id"]
    csv = ("Name,Job Title,Grade,Department,Level,Line Manager,Salary,Employee ID,Work Activities\n"
           "A,SEO Lead,H3,Marketing,1,Top,200000,E1,Optimize search marketing campaigns\n"
           "B,Social Lead,H3,Marketing,2,A,120000,E2,Build brand presence on TikTok\n"
           "C,Logistics,AO,Ops,2,A,70000,E3,Load promotional materials onto trucks\n")
    ds = (await api_client.post(f"/api/v1/engagements/{eng}/datasets",
          files={"file": ("o.csv", csv.encode(), "text/csv")})).json()["id"]
    await api_client.post("/api/v1/task-intel/extract", params={"dataset_id": ds})
    await api_client.post("/api/v1/task-intel/benchmark", params={"dataset_id": ds})

    aiopp = (await api_client.post("/api/v1/task-intel/ai-opportunity", params={"dataset_id": ds})).json()
    assert aiopp["with_overlay"] == 1 and aiopp["robotics_levers"] == 1 and aiopp["unclassified"] == 1

    # WORKBank overlay used for the covered task (real values, not inferred).
    by_text = {(await async_session.get(Task, s.task_id)).task_text: s
               for s in await async_session.scalars(select(TaskAIScore))}
    seo = by_text["Optimize search marketing campaigns"]
    assert seo.source == "WORKBank" and seo.has_level is not None

    # Inference fills the gaps; physical stays a robotics lever.
    infer = (await api_client.post("/api/v1/task-intel/infer-potential", params={"dataset_id": ds})).json()
    assert infer["updated"] == 2  # tiktok (unclassified) + trucks (auto-robotics) re-evaluated

    roll = (await api_client.get("/api/v1/task-intel/rollup", params={"dataset_id": ds})).json()
    assert roll["source_mix"] == {"overlay": 1, "ai_inferred": 1, "robotics": 1, "unclassified": 0}

    # The finalized-workflow deliverable still builds on this dataset (cross-feature sanity).
    proc = (await api_client.post("/api/v1/workflows",
            json={"engagement_id": eng, "name": "Marketing"})).json()
    step = (await api_client.post(f"/api/v1/workflows/{proc['id']}/steps", json={"name": "Plan"})).json()
    await api_client.post(f"/api/v1/workflows/steps/{step['id']}/map-tasks",
                          json={"task_ids": [seo.task_id]})
    dl = await api_client.post("/api/v1/deliverables/generate",
                               params={"engagement_id": eng, "type": "PPTX_WORKFLOW", "dataset_id": ds})
    assert dl.status_code == 200 and dl.json()["bytes"] > 0
