"""D26 — WORKBank → overlay converter (offline, synthetic CSVs) + overlay bypasses Claude inference."""
from __future__ import annotations

import json

from sqlalchemy import select

from app.models import TaskAIOverlay, TaskAIScore, Task
from app.services import taxonomy_loader
from app.services.claude_service import claude_service
from app.services.taxonomy_loader import load_taxonomies
from app.services.workbank_ingest import build_overlay_from_dir


def _write_workbank(tmp_path):
    (tmp_path / "task_statement_with_metadata.csv").write_text(
        "task_id,task_statement,onet_soc_code,occupation_title\n"
        "t1,Develop marketing strategy,11-2021.00,Marketing Managers\n"
        "t2,Manage social media campaigns,11-2021.00,Marketing Managers\n"
        "t3,Operate packaging machinery,51-9111.00,Packaging Operators\n",
        encoding="utf-8")
    (tmp_path / "expert_rated_technological_capability.csv").write_text(
        "task_id,technological_capability,human_agency_level\n"
        "t1,4,2\nt2,5,2\nt3,2,4\n", encoding="utf-8")
    (tmp_path / "domain_worker_desires.csv").write_text(
        "task_id,automation_desire\nt1,3\nt2,4\nt3,1\n", encoding="utf-8")


def test_converter_aggregates_to_soc_with_normalised_scores(tmp_path):
    _write_workbank(tmp_path)
    overlay = build_overlay_from_dir(tmp_path)
    by_soc = {o["onet_task_code"]: o for o in overlay}
    assert set(by_soc) == {"11-2021.00", "51-9111.00"}
    mk = by_soc["11-2021.00"]
    assert mk["source"] == "WORKBank" and mk["occupation"] == "Marketing Managers"
    assert mk["has_level"] == 2                       # mean(2,2)
    assert mk["capability_score"] == 0.9              # mean(4/5, 5/5)
    assert mk["zone"] == "GREEN_LIGHT"                # high capability + low HAS
    assert by_soc["51-9111.00"]["zone"] == "RED_LIGHT"  # low capability, high HAS


async def test_workbank_overlay_bypasses_inference(api_client, async_session, monkeypatch, tmp_path):
    """A task whose O*NET code is covered by the WORKBank overlay is scored from the overlay
    (source=WORKBank, real has_level) — NO Claude inference / NO_BENCHMARK_MATCH."""
    _write_workbank(tmp_path)
    overlay = build_overlay_from_dir(tmp_path)
    wb = tmp_path / "workbank_overlay.curated.json"
    wb.write_text(json.dumps({"task_ai_overlay": overlay}), encoding="utf-8")
    monkeypatch.setattr(taxonomy_loader, "WORKBANK_OVERLAY_PATH", wb)

    def _ai(*, model, max_tokens=2048, messages):  # noqa: ARG001
        c = messages[0]["content"]
        if "HUMAN AGENCY SCALE BENCHMARK" in c:  # inference must NOT be needed here
            raise AssertionError("inference called although the WORKBank overlay covers the task")
        if "GROUNDING:" in c:
            tasks = json.loads(c.split("TASKS:\n```json\n")[1].split("\n```")[0])
            return json.dumps({"benchmarks": [
                {"task_id": t["task_id"], "status": "MATCHED", "matched_task_ref": "wb",
                 "onet_task_code": "11-2021.00", "taxonomy_source_code": "WORKBANK",
                 "source": "WORKBank", "confidence": 0.9} for t in tasks]})
        items = json.loads(c.split("INPUT:\n```json\n")[1].split("\n```")[0])
        return json.dumps({"extractions": [
            {"employee_key": it["employee_key"],
             "tasks": [s.strip() for s in it["work_activities"].split(";") if s.strip()]}
            for it in items]})

    monkeypatch.setattr(type(claude_service), "has_api_key", property(lambda self: True))
    monkeypatch.setattr(claude_service, "complete", _ai)
    await load_taxonomies(async_session)
    assert await async_session.scalar(
        select(TaskAIOverlay).where(TaskAIOverlay.onet_task_code == "11-2021.00")) is not None

    c = await api_client.post("/api/v1/engagements/clients", json={"name": "GM"})
    e = await api_client.post("/api/v1/engagements", json={"client_id": c.json()["id"], "name": "AI"})
    eng = e.json()["id"]
    csv = ("Name,Job Title,Grade,Department,Level,Line Manager,Salary,Employee ID,Work Activities\n"
           "Ann,Marketing Manager,H5,Marketing,1,Top,300000,E1,Develop marketing strategy\n")
    ds = (await api_client.post(f"/api/v1/engagements/{eng}/datasets",
          files={"file": ("o.csv", csv.encode(), "text/csv")})).json()["id"]
    await api_client.post("/api/v1/task-intel/extract", params={"dataset_id": ds})
    await api_client.post("/api/v1/task-intel/benchmark", params={"dataset_id": ds})
    aiopp = (await api_client.post("/api/v1/task-intel/ai-opportunity", params={"dataset_id": ds})).json()
    assert aiopp["with_overlay"] == 1 and aiopp["unclassified"] == 0  # overlay used, nothing unmatched

    # infer-potential is a no-op (no candidates) — overlay already resolved everything.
    infer = (await api_client.post("/api/v1/task-intel/infer-potential", params={"dataset_id": ds})).json()
    assert infer["candidates"] == 0

    score = await async_session.scalar(select(TaskAIScore))
    assert score.source == "WORKBank" and score.has_level == 2

    roll = (await api_client.get("/api/v1/task-intel/rollup", params={"dataset_id": ds})).json()
    assert roll["source_mix"]["overlay"] == 1 and roll["source_mix"]["ai_inferred"] == 0
