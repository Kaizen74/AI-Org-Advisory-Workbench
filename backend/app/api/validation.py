"""Validation router — /api/v1/validation (Phase 3, Build Spec B2).

Non-AI (no API key needed): the queue, bulk review, and stats operate on already-persisted rows.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import get_session
from ..services import validation_service as vs

router = APIRouter(prefix="/api/v1/validation", tags=["validation"])


class ReviewAction(BaseModel):
    kind: str  # benchmark | ai_score | crosswalk
    id: str
    action: str  # approve | edit | reject
    edits: Optional[dict] = None


@router.get("/queue")
async def queue(
    dataset_id: Optional[str] = None,
    max_confidence: Optional[float] = None,
    include_reviewed: bool = False,
    session: AsyncSession = Depends(get_session),
):
    items = await vs.get_queue(
        session, dataset_id=dataset_id, max_confidence=max_confidence,
        include_reviewed=include_reviewed,
    )
    return {"count": len(items), "items": items}


@router.post("/review")
async def review(
    reviews: List[ReviewAction] = Body(...), session: AsyncSession = Depends(get_session)
):
    return await vs.review_items(session, [r.model_dump() for r in reviews])


class ManualScore(BaseModel):
    task_id: str  # the task to score (works from ai_score OR benchmark/EXTRA rows)
    rating: int  # 1=keep human .. 5=automate


@router.post("/manual-score")
async def manual_score(body: ManualScore, session: AsyncSession = Depends(get_session)):
    """Inline human override of AI opportunity for a 'no benchmark match' task (1-5 rating)."""
    from fastapi import HTTPException
    if not 1 <= body.rating <= 5:
        raise HTTPException(status_code=400, detail="rating must be 1..5")
    result = await vs.set_manual_opportunity(session, body.task_id, body.rating)
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


@router.get("/stats")
async def stats(dataset_id: Optional[str] = None, session: AsyncSession = Depends(get_session)):
    return await vs.get_stats(session, dataset_id=dataset_id)
