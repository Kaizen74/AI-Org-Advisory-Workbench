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


@router.get("/stats")
async def stats(dataset_id: Optional[str] = None, session: AsyncSession = Depends(get_session)):
    return await vs.get_stats(session, dataset_id=dataset_id)
