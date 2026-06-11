"""Diagnostics router — /api/v1/diagnostics (Phase 1, Build Spec B2).

`POST /compute` computes metrics for a dataset's positions and persists typed metric_values rows;
`GET /summary` reads them back. Guard pattern: 404 when the dataset has no positions. Non-AI: no
API key required.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import MetricValue
from ..models import get_session
from ..services import diagnostics_service as diag
from ..services import engagement_service as eng
from .schemas import DiagnosticsSummary, MetricValueOut

router = APIRouter(prefix="/api/v1/diagnostics", tags=["diagnostics"])


async def _load_rows(session: AsyncSession, dataset_id: str):
    result = await session.execute(
        select(MetricValue).where(MetricValue.dataset_id == dataset_id)
    )
    return list(result.scalars().all())


@router.post("/compute", response_model=DiagnosticsSummary)
async def compute(dataset_id: str, session: AsyncSession = Depends(get_session)):
    positions = await eng.get_dataset_positions(session, dataset_id)
    if not positions:
        raise HTTPException(status_code=404, detail="No positions for dataset (or dataset missing)")
    await diag.compute_and_persist(session, dataset_id, positions)
    rows = await _load_rows(session, dataset_id)
    return _summary(dataset_id, rows)


@router.get("/summary", response_model=DiagnosticsSummary)
async def summary(dataset_id: str, session: AsyncSession = Depends(get_session)):
    rows = await _load_rows(session, dataset_id)
    return _summary(dataset_id, rows)


def _summary(dataset_id: str, rows) -> DiagnosticsSummary:
    return DiagnosticsSummary(
        dataset_id=dataset_id,
        computed=len(rows) > 0,
        metrics={r.metric_code: r.value for r in rows},
        rows=[MetricValueOut.model_validate(r, from_attributes=True) for r in rows],
    )
