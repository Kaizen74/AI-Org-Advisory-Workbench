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

from ..models import Client, Dataset, Engagement, MetricValue, Position
from ..parsers.csv_parser import OrgCSVParser


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

    for p in positions:
        session.add(
            Position(
                dataset_id=dataset.id,
                employee_key=p["employee_key"],
                display_name=p["display_name"],
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
async def purge_engagement(session: AsyncSession, engagement_id: str) -> bool:
    """Delete an engagement and everything under it. Returns False if not found.

    Explicit ordered deletes (child -> parent) so purge is reliable on async SQLite/Postgres without
    depending on DB-level ON DELETE cascade or ORM lazy-load during cascade.
    """
    engagement = await session.get(Engagement, engagement_id)
    if engagement is None:
        return False

    dataset_ids = select(Dataset.id).where(Dataset.engagement_id == engagement_id)
    await session.execute(delete(MetricValue).where(MetricValue.dataset_id.in_(dataset_ids)))
    await session.execute(delete(Position).where(Position.dataset_id.in_(dataset_ids)))
    await session.execute(delete(Dataset).where(Dataset.engagement_id == engagement_id))
    await session.execute(delete(Engagement).where(Engagement.id == engagement_id))
    await session.flush()
    return True
