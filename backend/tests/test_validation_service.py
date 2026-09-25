"""P3.1–P3.3 — validation queue, bulk review + crosswalk learning, client-ready exclusion."""
from __future__ import annotations

import json

from sqlalchemy import func, select

from app.models import Client, Dataset, Engagement, Position, Task, TaskBenchmark, TaxonomyCrosswalk
from app.services import task_intelligence_service as tis
from app.services import validation_service as vs
from app.services.claude_service import claude_service
from app.services.taxonomy_loader import load_taxonomies


def _keyword_benchmarker(*, model, max_tokens=2048, messages):  # noqa: ARG001
    tasks = json.loads(messages[0]["content"].split("TASKS:\n```json\n")[1].split("\n```")[0])
    out = []
    for t in tasks:
        text = t["task_text"].lower()
        if "waybill" in text or "document" in text:
            out.append({"task_id": t["task_id"], "status": "MATCHED",
                        "matched_task_ref": "SFW_AT_CGO_01", "onet_task_code": "43-5011.00",
                        "taxonomy_source_code": "SFW_AIR_TRANSPORT", "source": "SFw", "confidence": 0.85})
        elif "baggage" in text or "load" in text:
            out.append({"task_id": t["task_id"], "status": "MATCHED",
                        "matched_task_ref": "SFW_AT_RHO_01", "onet_task_code": "53-7062.00",
                        "taxonomy_source_code": "SFW_AIR_TRANSPORT", "source": "SFw", "confidence": 0.60})
        else:
            out.append({"task_id": t["task_id"], "status": "MISSING", "matched_task_ref": None,
                        "onet_task_code": None, "taxonomy_source_code": None,
                        "source": "model-inferred", "confidence": 0.30})
    return json.dumps({"benchmarks": out})


async def _seed_pipeline(async_session):
    await load_taxonomies(async_session)
    client = Client(name="PAX", anonymization_default=False)
    eng = Engagement(client=client, name="TOM", anonymized=False)
    ds = Dataset(engagement=eng, version=1, row_count=1)
    async_session.add_all([client, eng, ds])
    await async_session.flush()
    pos = Position(dataset_id=ds.id, employee_key="E1", department="Cargo")
    async_session.add(pos)
    await async_session.flush()
    for txt in ["Process air waybills and documents", "Load and unload baggage", "Attend meetings"]:
        async_session.add(Task(position_id=pos.id, task_text=txt))
    await async_session.flush()
    await tis.benchmark_tasks(async_session, ds.id)
    await tis.score_ai_opportunity(async_session, ds.id)
    return ds.id


async def test_queue_includes_seed_040_crosswalk(async_session, monkeypatch):
    monkeypatch.setattr(claude_service, "complete", _keyword_benchmarker)
    await _seed_pipeline(async_session)

    queue = await vs.get_queue(async_session, max_confidence=0.70)
    crosswalk_items = [i for i in queue if i["kind"] == "crosswalk"]
    assert any(abs((i["confidence"] or 0) - 0.40) < 1e-9 for i in crosswalk_items)
    assert all(i["review_state"] == "unreviewed" for i in crosswalk_items)


async def test_review_approves_and_learns_curated_crosswalk(async_session, monkeypatch):
    monkeypatch.setattr(claude_service, "complete", _keyword_benchmarker)
    dataset_id = await _seed_pipeline(async_session)

    # Approve the cargo benchmark (has matched task + onet code) -> learns a crosswalk.
    cargo = await async_session.scalar(
        select(TaskBenchmark).where(TaskBenchmark.onet_task_code == "43-5011.00")
    )
    before = await async_session.scalar(
        select(func.count()).select_from(TaxonomyCrosswalk).where(
            TaxonomyCrosswalk.method == "CURATED_BY_CONSULTANT"
        )
    )
    result = await vs.review_items(
        async_session, [{"kind": "benchmark", "id": cargo.id, "action": "approve"}]
    )
    assert result["updated"] == 1
    assert result["crosswalks_created"] == 1

    after = await async_session.scalar(
        select(func.count()).select_from(TaxonomyCrosswalk).where(
            TaxonomyCrosswalk.method == "CURATED_BY_CONSULTANT"
        )
    )
    assert after == before + 1
    refreshed = await async_session.get(TaskBenchmark, cargo.id)
    assert refreshed.review_state == "approved" and refreshed.reviewed_at is not None

    # Idempotent: re-approving does not create a duplicate learned crosswalk.
    await vs.review_items(async_session, [{"kind": "benchmark", "id": cargo.id, "action": "approve"}])
    assert await async_session.scalar(
        select(func.count()).select_from(TaxonomyCrosswalk).where(
            TaxonomyCrosswalk.method == "CURATED_BY_CONSULTANT"
        )
    ) == after


async def test_client_ready_excludes_unreviewed_model_inferred(async_session, monkeypatch):
    monkeypatch.setattr(claude_service, "complete", _keyword_benchmarker)
    dataset_id = await _seed_pipeline(async_session)

    ready = await vs.client_ready_ai_scores(async_session, dataset_id)
    # The baggage task is model-inferred + unreviewed (robotics lever) -> excluded.
    assert all(not (s.source == "model-inferred" and s.review_state == "unreviewed") for s in ready)
    # WORKBank-sourced score (cargo) is retained.
    assert any(s.source == "WORKBank" for s in ready)

    # Unit check on the rule.
    assert vs.is_client_ready("model-inferred", "unreviewed") is False
    assert vs.is_client_ready("WORKBank", "unreviewed") is True
    assert vs.is_client_ready("SFw", "approved") is True
    assert vs.is_client_ready("SFw", "rejected") is False
