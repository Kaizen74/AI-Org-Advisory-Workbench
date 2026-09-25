"""Audit trail service (Phase 7 / M7).

Append-only log of meaningful actions (uploads, AI calls, validations, exports, PDPA purges) so an
engagement's activity is reviewable before a second-client engagement.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditEvent


async def record(session: AsyncSession, engagement_id: Optional[str], event_type: str,
                 detail: Optional[Dict] = None) -> None:
    """Append an audit event. Never raises into the caller's flow on logging failure."""
    try:
        session.add(AuditEvent(engagement_id=engagement_id, event_type=event_type, detail=detail))
        await session.flush()
    except Exception:  # noqa: BLE001 - auditing must not break the primary action
        pass


async def list_events(session: AsyncSession, engagement_id: str) -> List[Dict]:
    rows = await session.scalars(
        select(AuditEvent).where(AuditEvent.engagement_id == engagement_id).order_by(AuditEvent.at)
    )
    return [{"id": r.id, "event_type": r.event_type, "detail": r.detail, "at": str(r.at)}
            for r in rows]
