"""Audit router — /api/v1/audit (Phase 7 / M7). Non-AI; read-only trail."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import get_session
from ..services import audit_service

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("")
async def list_events(engagement_id: str, session: AsyncSession = Depends(get_session)):
    return {"events": await audit_service.list_events(session, engagement_id)}
