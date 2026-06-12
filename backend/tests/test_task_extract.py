"""P2.4 — batched extraction: 500-position synthetic fixture proving batching + deterministic merge.

The Claude call is mocked with a realistic *echo extractor* that reads the prompt's machine-readable
JSON block and splits each position's work_activities on ';' — so the test exercises the real
batching/merge code path offline and deterministically (A3 Rule 1).
"""
from __future__ import annotations

import json

from sqlalchemy import select

from app.models import Client, Dataset, Engagement, Position, Task
from app.services import task_intelligence_service as tis
from app.services.claude_service import claude_service


def _echo_extractor(*, model, max_tokens=2048, messages):  # noqa: ARG001 - signature parity
    block = messages[0]["content"].split("```json")[1].split("```")[0]
    items = json.loads(block)
    extractions = [
        {
            "employee_key": it["employee_key"],
            "tasks": [t.strip() for t in it["work_activities"].split(";") if t.strip()],
        }
        for it in items
    ]
    return json.dumps({"extractions": extractions})


async def _seed_500(async_session) -> str:
    client = Client(name="Synthetic", anonymization_default=False)
    eng = Engagement(client=client, name="Scale test", anonymized=False)
    ds = Dataset(engagement=eng, version=1, filename="synthetic500.csv", row_count=500)
    async_session.add_all([client, eng, ds])
    await async_session.flush()
    for i in range(500):
        key = f"E{i:03d}"
        async_session.add(
            Position(
                dataset_id=ds.id,
                employee_key=key,
                display_name=f"Person {i}",
                department=f"Dept{i % 13}",
                level=(i % 6) + 1,
                work_activities=f"Do A for {key}; Do B for {key}",
            )
        )
    await async_session.flush()
    return ds.id


async def test_extract_batches_and_merges_500(async_session, monkeypatch):
    monkeypatch.setattr(claude_service, "complete", _echo_extractor)
    dataset_id = await _seed_500(async_session)

    result = await tis.extract_tasks(async_session, dataset_id, batch_size=40)

    # 13 departments, each <= 40 positions -> 13 batches; 2 tasks per position -> 1000 tasks.
    assert result["positions_with_activities"] == 500
    assert result["batches"] == 13
    assert result["tasks_created"] == 1000
    assert any("occupation-level" in c for c in result["caveats"])

    persisted = await async_session.scalar(
        select(Task).where(Task.task_text == "Do A for E000")
    )
    assert persisted is not None
    assert persisted.extraction_source == "model-inferred"
    assert persisted.batch_id.startswith("batch_")


async def test_extract_is_deterministic_and_idempotent(async_session, monkeypatch):
    monkeypatch.setattr(claude_service, "complete", _echo_extractor)
    dataset_id = await _seed_500(async_session)

    async def texts_in_order():
        rows = list(
            await async_session.scalars(
                select(Task).order_by(Task.batch_id, Task.task_text)
            )
        )
        return [t.task_text for t in rows]

    await tis.extract_tasks(async_session, dataset_id, batch_size=40)
    first = await texts_in_order()
    await tis.extract_tasks(async_session, dataset_id, batch_size=40)  # rerun
    second = await texts_in_order()

    assert first == second  # deterministic
    # Idempotent: rerun does not accumulate duplicates.
    total = await async_session.scalar(select(Task).where(Task.task_text == "Do A for E000"))
    assert total is not None
    count = len(list(await async_session.scalars(
        select(Task).where(Task.task_text == "Do A for E000")
    )))
    assert count == 1


async def test_smaller_batch_size_makes_more_batches(async_session, monkeypatch):
    monkeypatch.setattr(claude_service, "complete", _echo_extractor)
    dataset_id = await _seed_500(async_session)
    result = await tis.extract_tasks(async_session, dataset_id, batch_size=10)
    # Each dept (~38-39) chunked by 10 -> 4 batches per dept * 13 = 52.
    assert result["batches"] == 52
    assert result["tasks_created"] == 1000
