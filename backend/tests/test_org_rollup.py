"""Org-hierarchy AI roll-up: AI exposure must aggregate UP the reporting lines to department heads
(mirrors the uploaded org chart). Deterministic, no AI."""
from __future__ import annotations

import pytest

from app.models import Client, Dataset, Engagement, Position, Task, TaskAIScore
from app.services import task_intelligence_service as tis


async def _seed(session, *, anonymized=False):
    """Head (E1) ← Manager (E2) ← Analyst (E3); plus a second root Head (E4) with no reports.
    Returns the dataset id."""
    c = Client(name="C")
    session.add(c)
    await session.flush()
    e = Engagement(client_id=c.id, name="E", anonymized=anonymized)
    session.add(e)
    await session.flush()
    ds = Dataset(engagement_id=e.id, version=1)
    session.add(ds)
    await session.flush()

    head = Position(dataset_id=ds.id, employee_key="E1", display_name="Head Person",
                    job_title="Head, Marketing", department="Mktg", level=2, manager_key=None)
    mgr = Position(dataset_id=ds.id, employee_key="E2", display_name="Mid Manager",
                   job_title="Manager", department="Mktg", level=3, manager_key="E1")
    analyst = Position(dataset_id=ds.id, employee_key="E3", display_name="An Analyst",
                       job_title="Analyst", department="Mktg", level=4, manager_key="E2")
    head2 = Position(dataset_id=ds.id, employee_key="E4", display_name="Comms Head",
                     job_title="Head, Comms", department="Comms", level=2, manager_key=None)
    session.add_all([head, mgr, analyst, head2])
    await session.flush()

    # Analyst: H1 approved + H4 unreviewed. Manager: H2 unreviewed. Head: no own tasks. Head2: H5.
    t1 = Task(position_id=analyst.id, task_text="a")
    t2 = Task(position_id=analyst.id, task_text="b")
    t3 = Task(position_id=mgr.id, task_text="c")
    t4 = Task(position_id=head2.id, task_text="d")
    session.add_all([t1, t2, t3, t4])
    await session.flush()
    session.add_all([
        TaskAIScore(task_id=t1.id, has_level=1, review_state="approved", source="consultant-approved"),
        TaskAIScore(task_id=t2.id, has_level=4, review_state="unreviewed", source="model-inferred"),
        TaskAIScore(task_id=t3.id, has_level=2, review_state="unreviewed", source="model-inferred"),
        TaskAIScore(task_id=t4.id, has_level=5, review_state="unreviewed", source="model-inferred"),
    ])
    await session.flush()
    return ds.id


@pytest.mark.asyncio
async def test_org_rollup_aggregates_up_reporting_lines(async_session):
    ds_id = await _seed(async_session)
    out = await tis.org_rollup(async_session, ds_id)
    nodes = {n["employee_key"]: n for n in out["nodes"]}

    # Two roots: the two department heads (no manager within the dataset).
    assert sorted(out["roots"]) == ["E1", "E4"]
    assert nodes["E2"]["manager_key"] == "E1" and nodes["E3"]["manager_key"] == "E2"

    # Self metrics.
    assert nodes["E3"]["self_bands"]["H1"] == 1 and nodes["E3"]["self_bands"]["H4"] == 1
    assert nodes["E3"]["self_tasks"] == 2 and nodes["E3"]["self_reviewed"] == 1
    assert nodes["E1"]["self_tasks"] == 0  # head has no personal tasks

    # Roll-up: the head accumulates the whole subtree (analyst H1+H4, manager H2) = 3 tasks.
    assert nodes["E1"]["rollup_tasks"] == 3
    assert nodes["E1"]["rollup_bands"]["H1"] == 1
    assert nodes["E1"]["rollup_bands"]["H2"] == 1
    assert nodes["E1"]["rollup_bands"]["H4"] == 1
    assert nodes["E1"]["rollup_reviewed"] == 1
    assert nodes["E1"]["direct_reports"] == 1 and nodes["E1"]["total_reports"] == 2

    # Second head is independent (own H5 task, no reports).
    assert nodes["E4"]["rollup_tasks"] == 1 and nodes["E4"]["total_reports"] == 0

    # COHERENCE: a manager's OWN task count is NOT the rolled-up total ("does the head have 3 tasks?").
    assert nodes["E1"]["self_tasks"] == 0 and nodes["E1"]["rollup_tasks"] == 3
    # Each node carries its OWN tasks (D46) with band/zone/review + workflow placement.
    e3_tasks = nodes["E3"]["tasks"]
    assert len(e3_tasks) == 2
    assert {t["human_agency_level"] for t in e3_tasks} == {"H1", "H4"}
    assert all(t["mapped"] == [] for t in e3_tasks)  # nothing mapped to a step yet
    assert nodes["E1"]["tasks"] == []  # head has no own tasks (only rolled-up ones)


@pytest.mark.asyncio
async def test_org_rollup_tasks_carry_workflow_placement(async_session):
    """D46: a role's own tasks show WHERE they are mapped (process → step) — the tie back to Flow."""
    from app.models import Process, ProcessStep, TaskLink
    ds_id = await _seed(async_session)
    # Map the analyst's first task to a process step.
    out0 = await tis.org_rollup(async_session, ds_id)
    analyst = {n["employee_key"]: n for n in out0["nodes"]}["E3"]
    tid = analyst["tasks"][0]["id"]
    eng_id = (await async_session.get(Dataset, ds_id)).engagement_id

    proc = Process(engagement_id=eng_id, name="Content Ops", value_stream="Marketing")
    async_session.add(proc)
    await async_session.flush()
    step = ProcessStep(process_id=proc.id, seq=2, name="Draft")
    async_session.add(step)
    await async_session.flush()
    async_session.add(TaskLink(process_step_id=step.id, task_id=tid))
    await async_session.flush()

    out = await tis.org_rollup(async_session, ds_id)
    tasks = {n["employee_key"]: n for n in out["nodes"]}["E3"]["tasks"]
    mapped = next(t for t in tasks if t["id"] == tid)
    assert mapped["mapped"] == [{"process": "Content Ops", "step": "Draft", "step_seq": 2}]
    # The other task stays unmapped.
    assert any(t["mapped"] == [] for t in tasks if t["id"] != tid)


@pytest.mark.asyncio
async def test_org_rollup_respects_anonymization(async_session):
    ds_id = await _seed(async_session, anonymized=True)
    out = await tis.org_rollup(async_session, ds_id)
    # No real names leak — every node label is a pseudonym (M7).
    for n in out["nodes"]:
        assert n["name"].startswith("EMP-")
        assert n["name"] not in ("Head Person", "Mid Manager", "An Analyst", "Comms Head")


@pytest.mark.asyncio
async def test_org_rollup_empty_dataset(async_session):
    c = Client(name="C")
    async_session.add(c)
    await async_session.flush()
    e = Engagement(client_id=c.id, name="E")
    async_session.add(e)
    await async_session.flush()
    ds = Dataset(engagement_id=e.id, version=1)
    async_session.add(ds)
    await async_session.flush()
    out = await tis.org_rollup(async_session, ds.id)
    assert out["nodes"] == [] and out["roots"] == []
