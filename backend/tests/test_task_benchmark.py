"""P2.5 + P2.6 — benchmark + ai-opportunity (mocked AI), incl. provenance-presence (A4)."""
from __future__ import annotations

import json

from sqlalchemy import select

from app.models import Client, Dataset, Engagement, Position, Task, TaskAIScore, TaskBenchmark
from app.services import task_intelligence_service as tis
from app.services.claude_service import claude_service
from app.services.taxonomy_loader import load_taxonomies


def _keyword_benchmarker(*, model, max_tokens=2048, messages):  # noqa: ARG001
    """Realistic mock: read the TASKS json block and map by keyword to O*NET codes."""
    content = messages[0]["content"]
    tasks_block = content.split("TASKS:\n```json\n")[1].split("\n```")[0]
    tasks = json.loads(tasks_block)
    out = []
    for t in tasks:
        text = t["task_text"].lower()
        if any(k in text for k in ("waybill", "document", "cargo")):
            out.append({"task_id": t["task_id"], "status": "MATCHED",
                        "taxonomy_source_code": "SFW_AIR_TRANSPORT",
                        "matched_task_ref": "SFW_AT_CGO_01", "onet_task_code": "43-5011.00",
                        "source": "SFw", "confidence": 0.85})
        elif any(k in text for k in ("check-in", "boarding")):
            out.append({"task_id": t["task_id"], "status": "MATCHED",
                        "taxonomy_source_code": "SFW_AIR_TRANSPORT",
                        "matched_task_ref": "SFW_AT_PSO_01", "onet_task_code": "43-4181.00",
                        "source": "SFw", "confidence": 0.88})
        elif any(k in text for k in ("load", "baggage", "unload")):
            out.append({"task_id": t["task_id"], "status": "MATCHED",
                        "taxonomy_source_code": "SFW_AIR_TRANSPORT",
                        "matched_task_ref": "SFW_AT_RHO_01", "onet_task_code": "53-7062.00",
                        "source": "SFw", "confidence": 0.60})
        else:
            out.append({"task_id": t["task_id"], "status": "MISSING",
                        "taxonomy_source_code": None, "matched_task_ref": None,
                        "onet_task_code": None, "source": "model-inferred", "confidence": 0.30})
    return json.dumps({"benchmarks": out})


TASK_TEXTS = [
    "Process air waybills and customs documents",  # -> 43-5011.00 (overlay exists)
    "Perform passenger check-in and boarding",      # -> 43-4181.00 (overlay exists)
    "Load and unload baggage onto aircraft",        # -> 53-7062.00 (NO overlay -> robotics)
    "Attend weekly team meetings",                  # -> MISSING
]


async def _seed(async_session):
    await load_taxonomies(async_session)  # overlays for 43-5011.00, 43-4181.00 (not 53-7062.00)
    client = Client(name="PAX", anonymization_default=False)
    eng = Engagement(client=client, name="TOM", anonymized=False)
    ds = Dataset(engagement=eng, version=1, row_count=1)
    async_session.add_all([client, eng, ds])
    await async_session.flush()
    pos = Position(dataset_id=ds.id, employee_key="E1", display_name="A", department="Cargo")
    async_session.add(pos)
    await async_session.flush()
    for txt in TASK_TEXTS:
        async_session.add(Task(position_id=pos.id, task_text=txt, extraction_source="model-inferred"))
    await async_session.flush()
    return ds.id


async def test_benchmark_statuses_and_review_routing(async_session, monkeypatch):
    monkeypatch.setattr(claude_service, "complete", _keyword_benchmarker)
    dataset_id = await _seed(async_session)

    result = await tis.benchmark_tasks(async_session, dataset_id)
    assert result["benchmarks_created"] == 4
    assert result["matched"] == 3
    assert result["missing"] == 1

    rows = {
        (await async_session.get(Task, b.task_id)).task_text: b
        for b in await async_session.scalars(select(TaskBenchmark))
    }
    # 0.60 and 0.30 (<0.70) route to unreviewed; 0.85/0.88 route to approved.
    assert rows["Load and unload baggage onto aircraft"].review_state == "unreviewed"
    assert rows["Process air waybills and customs documents"].review_state == "approved"
    assert rows["Attend weekly team meetings"].status == "MISSING"


async def test_ai_opportunity_overlay_join_and_robotics_lever(async_session, monkeypatch):
    monkeypatch.setattr(claude_service, "complete", _keyword_benchmarker)
    dataset_id = await _seed(async_session)
    await tis.benchmark_tasks(async_session, dataset_id)

    result = await tis.score_ai_opportunity(async_session, dataset_id)
    assert result["scored"] == 4
    assert result["with_overlay"] == 2  # 43-5011.00 + 43-4181.00
    assert result["robotics_levers"] >= 1  # the physical baggage task (no overlay)

    scores = {
        (await async_session.get(Task, s.task_id)).task_text: s
        for s in await async_session.scalars(select(TaskAIScore))
    }
    cargo = scores["Process air waybills and customs documents"]
    assert cargo.source == "WORKBank"
    assert cargo.desire_score_us == 0.70 and cargo.desire_score_local is None
    assert cargo.ai_opportunity_level == "L3"  # capability 0.78, HAS 2

    baggage = scores["Load and unload baggage onto aircraft"]
    assert baggage.source == "model-inferred"
    assert baggage.zone == "ROBOTICS_GSE_LEVER"


async def test_provenance_present_on_every_ai_row(async_session, monkeypatch):
    """Canonical pipeline output: every AI-derived row carries source/confidence/review_state (A4)."""
    monkeypatch.setattr(claude_service, "complete", _keyword_benchmarker)
    dataset_id = await _seed(async_session)
    await tis.benchmark_tasks(async_session, dataset_id)
    await tis.score_ai_opportunity(async_session, dataset_id)

    for model in (TaskBenchmark, TaskAIScore):
        for row in await async_session.scalars(select(model)):
            assert row.source, f"{model.__name__} missing source"
            assert row.review_state in {"unreviewed", "approved", "edited", "rejected"}
            assert hasattr(row, "confidence")
