"""Engagement Hub service (Phase 1, Build Spec M0/B2).

Async CRUD for clients/engagements and dataset ingestion (CSV upload -> parse -> persist positions
+ validation warnings). Purge cascades via FK so an engagement's data deletes cleanly (PRD §5).
Non-AI: works with no Anthropic API key.
"""
from __future__ import annotations

import io
from typing import List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    AuditEvent,
    Client,
    Dataset,
    Deliverable,
    DesignMove,
    DesirePulseResponse,
    Engagement,
    MetricValue,
    Position,
    Process,
    ProcessStep,
    Scenario,
    ScenarioMetric,
    Task,
    TaskAIScore,
    TaskBenchmark,
    TaskLink,
)
from ..parsers.csv_parser import OrgCSVParser
from .anonymization import pseudonym_for


# ── Clients ──────────────────────────────────────────────────────────────────
async def create_client(session: AsyncSession, *, name: str, industry: Optional[str],
                        anonymization_default: bool) -> Client:
    client = Client(name=name, industry=industry, anonymization_default=anonymization_default)
    session.add(client)
    await session.flush()
    return client


async def list_clients(session: AsyncSession) -> List[Client]:
    result = await session.execute(select(Client).order_by(Client.name))
    return list(result.scalars().all())


# ── Engagements ──────────────────────────────────────────────────────────────
async def create_engagement(session: AsyncSession, **fields) -> Optional[Engagement]:
    # Guard: the client must exist.
    client = await session.get(Client, fields["client_id"])
    if client is None:
        return None
    engagement = Engagement(**fields)
    session.add(engagement)
    await session.flush()
    return engagement


async def list_engagements(session: AsyncSession, client_id: Optional[str] = None) -> List[Engagement]:
    stmt = select(Engagement)
    if client_id:
        stmt = stmt.where(Engagement.client_id == client_id)
    result = await session.execute(stmt.order_by(Engagement.created_at))
    return list(result.scalars().all())


async def get_engagement(session: AsyncSession, engagement_id: str) -> Optional[Engagement]:
    return await session.get(Engagement, engagement_id)


# ── Datasets (CSV ingest) ────────────────────────────────────────────────────
async def create_dataset_from_csv(
    session: AsyncSession, *, engagement_id: str, filename: Optional[str], content: bytes
) -> Optional[Dataset]:
    """Parse an uploaded org CSV and persist a new dataset version + its positions + warnings."""
    engagement = await session.get(Engagement, engagement_id)
    if engagement is None:
        return None

    parsed = OrgCSVParser(io.BytesIO(content)).parse()
    positions = parsed["positions"]
    warnings = parsed["validation_warnings"]

    # Next version under this engagement.
    current_max = await session.scalar(
        select(func.max(Dataset.version)).where(Dataset.engagement_id == engagement_id)
    )
    version = (current_max or 0) + 1

    dataset = Dataset(
        engagement_id=engagement_id,
        version=version,
        filename=filename,
        row_count=len(positions),
        validation_warnings=warnings,
    )
    session.add(dataset)
    await session.flush()

    anonymized = bool(engagement.anonymized)
    for p in positions:
        session.add(
            Position(
                dataset_id=dataset.id,
                employee_key=p["employee_key"],
                display_name=p["display_name"],
                # Stable salted pseudonym generated at ingest when the engagement is anonymized (M7).
                pseudonym=(pseudonym_for(engagement_id, p["employee_key"]) if anonymized else None),
                job_title=p.get("job_title"),
                grade=p.get("grade"),
                level=p.get("level"),
                manager_key=p.get("manager_key"),
                department=p.get("department"),
                salary=p.get("salary"),
                work_activities=p.get("work_activities"),
            )
        )
    await session.flush()
    return dataset


async def list_datasets(session: AsyncSession, engagement_id: str) -> List[Dataset]:
    result = await session.execute(
        select(Dataset).where(Dataset.engagement_id == engagement_id).order_by(Dataset.version)
    )
    return list(result.scalars().all())


async def get_dataset_positions(session: AsyncSession, dataset_id: str) -> List[Position]:
    result = await session.execute(select(Position).where(Position.dataset_id == dataset_id))
    return list(result.scalars().all())


# ── Purge ────────────────────────────────────────────────────────────────────
async def purge_real_names(session: AsyncSession, engagement_id: str) -> Optional[int]:
    """PDPA: null out real names (display_name) across the engagement, keeping pseudonymized
    analytics intact. Returns the number of positions scrubbed, or None if engagement not found."""
    engagement = await session.get(Engagement, engagement_id)
    if engagement is None:
        return None
    dataset_ids = select(Dataset.id).where(Dataset.engagement_id == engagement_id)
    positions = list(await session.scalars(
        select(Position).where(Position.dataset_id.in_(dataset_ids))
    ))
    count = 0
    for p in positions:
        if p.display_name is not None:
            # Ensure a pseudonym exists so the position stays referenceable after scrub.
            if not p.pseudonym:
                p.pseudonym = pseudonym_for(engagement_id, p.employee_key)
            p.display_name = None
            count += 1
    await session.flush()
    return count


async def _delete_dataset_chain(session: AsyncSession, dataset_id_filter) -> None:
    """Delete the full task/score/benchmark/link + metric/position chain for one or more datasets.

    `dataset_id_filter` is a SQL expression usable in `.in_()` / `==` (a scalar id or a subquery).
    Explicit ordered deletes (child -> parent) so it is reliable on async SQLite/Postgres without
    depending on DB-level cascade.
    """
    task_ids = (
        select(Task.id).join(Position, Task.position_id == Position.id)
        .where(Position.dataset_id.in_(dataset_id_filter))
    )
    await session.execute(delete(TaskLink).where(TaskLink.task_id.in_(task_ids)))
    await session.execute(delete(TaskAIScore).where(TaskAIScore.task_id.in_(task_ids)))
    await session.execute(delete(TaskBenchmark).where(TaskBenchmark.task_id.in_(task_ids)))
    await session.execute(delete(Task).where(Task.id.in_(task_ids)))
    await session.execute(delete(MetricValue).where(MetricValue.dataset_id.in_(dataset_id_filter)))
    await session.execute(delete(Position).where(Position.dataset_id.in_(dataset_id_filter)))


async def _purge_engagement_data(session: AsyncSession, engagement_id: str) -> None:
    """Delete everything under an engagement EXCEPT the engagement row itself."""
    dataset_ids = select(Dataset.id).where(Dataset.engagement_id == engagement_id)
    await _delete_dataset_chain(session, dataset_ids)
    # Workflow processes/steps (and any residual links by step).
    process_ids = select(Process.id).where(Process.engagement_id == engagement_id)
    step_ids = select(ProcessStep.id).where(ProcessStep.process_id.in_(process_ids))
    await session.execute(delete(TaskLink).where(TaskLink.process_step_id.in_(step_ids)))
    await session.execute(delete(ProcessStep).where(ProcessStep.process_id.in_(process_ids)))
    await session.execute(delete(Process).where(Process.engagement_id == engagement_id))
    # Scenarios (parked feature, but data may exist).
    scenario_ids = select(Scenario.id).where(Scenario.engagement_id == engagement_id)
    await session.execute(delete(ScenarioMetric).where(ScenarioMetric.scenario_id.in_(scenario_ids)))
    await session.execute(delete(DesignMove).where(DesignMove.scenario_id.in_(scenario_ids)))
    await session.execute(delete(Scenario).where(Scenario.engagement_id == engagement_id))
    # Other engagement-scoped rows.
    await session.execute(
        delete(DesirePulseResponse).where(DesirePulseResponse.engagement_id == engagement_id)
    )
    await session.execute(delete(Deliverable).where(Deliverable.engagement_id == engagement_id))
    await session.execute(delete(AuditEvent).where(AuditEvent.engagement_id == engagement_id))
    await session.execute(delete(Dataset).where(Dataset.engagement_id == engagement_id))


async def purge_engagement(session: AsyncSession, engagement_id: str) -> bool:
    """Delete an engagement and everything under it. Returns False if not found."""
    engagement = await session.get(Engagement, engagement_id)
    if engagement is None:
        return False
    await _purge_engagement_data(session, engagement_id)
    await session.execute(delete(Engagement).where(Engagement.id == engagement_id))
    await session.flush()
    return True


async def delete_dataset(session: AsyncSession, dataset_id: str) -> bool:
    """Delete a single dataset (CSV upload) and all data derived from it. Returns False if missing."""
    ds = await session.get(Dataset, dataset_id)
    if ds is None:
        return False
    await _delete_dataset_chain(session, select(Dataset.id).where(Dataset.id == dataset_id))
    await session.execute(delete(Dataset).where(Dataset.id == dataset_id))
    await session.flush()
    return True


async def delete_client(session: AsyncSession, client_id: str) -> bool:
    """Delete a client and every engagement (and all data) under it. Returns False if missing."""
    client = await session.get(Client, client_id)
    if client is None:
        return False
    engagement_ids = list(
        await session.scalars(select(Engagement.id).where(Engagement.client_id == client_id))
    )
    for eng_id in engagement_ids:
        await _purge_engagement_data(session, eng_id)
    await session.execute(delete(Engagement).where(Engagement.client_id == client_id))
    await session.execute(delete(Client).where(Client.id == client_id))
    await session.flush()
    return True
