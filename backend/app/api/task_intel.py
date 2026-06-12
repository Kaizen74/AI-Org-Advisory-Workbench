"""Task Intelligence router — /api/v1/task-intel (Phase 2, Build Spec B2).

Guard pattern: AI endpoints (extract/benchmark/ai-opportunity) return 400 when no Anthropic API key
is configured and 404 when the dataset has no positions/tasks. `GET /quick` is non-AI and works with
no key.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Position
from ..models import get_session
from ..services import task_intelligence_service as tis
from ..services.claude_service import claude_service

router = APIRouter(prefix="/api/v1/task-intel", tags=["task-intelligence"])


def _require_api_key() -> None:
    if not claude_service.has_api_key:
        raise HTTPException(status_code=400, detail="Anthropic API key not configured")


async def _positions(session: AsyncSession, dataset_id: str):
    rows = list(await session.scalars(select(Position).where(Position.dataset_id == dataset_id)))
    if not rows:
        raise HTTPException(status_code=404, detail="No positions for dataset (or dataset missing)")
    return rows


@router.post("/extract")
async def extract(dataset_id: str, batch_size: int = tis.DEFAULT_BATCH_SIZE,
                  session: AsyncSession = Depends(get_session)):
    _require_api_key()
    await _positions(session, dataset_id)
    return await tis.extract_tasks(session, dataset_id, batch_size=batch_size)


@router.post("/benchmark")
async def benchmark(dataset_id: str, session: AsyncSession = Depends(get_session)):
    _require_api_key()
    await _positions(session, dataset_id)
    return await tis.benchmark_tasks(session, dataset_id)


@router.post("/ai-opportunity")
async def ai_opportunity(dataset_id: str, session: AsyncSession = Depends(get_session)):
    _require_api_key()
    await _positions(session, dataset_id)
    return await tis.score_ai_opportunity(session, dataset_id)


@router.get("/rollup")
async def get_rollup(dataset_id: str, session: AsyncSession = Depends(get_session)):
    return await tis.rollup(session, dataset_id)


@router.get("/quick")
async def quick(dataset_id: str, session: AsyncSession = Depends(get_session)):
    """No-AI preview (work-activities coverage) — no API key required."""
    positions = await _positions(session, dataset_id)
    return tis.quick_stats(positions)
