"""Capability Compass hand-off router — /api/v1/compass (D50).

Non-AI (no API key). Import is two steps — `preview` writes nothing; `apply` writes only what the
consultant confirmed. Every route degrades cleanly for an engagement with no Compass packet.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import get_session
from ..services import audit_service, compass_return_service, compass_service

router = APIRouter(prefix="/api/v1/compass", tags=["compass"])


class PreviewBody(BaseModel):
    packet: Any = None
    engagement_id: Optional[str] = None
    dataset_id: Optional[str] = None


class ApplyBody(PreviewBody):
    matches: Optional[Dict[str, Optional[str]]] = None  # role ref -> job title (null = unmatched)
    overwrite_name: bool = False
    confirm_key_change: bool = False


class RoleMatchBody(BaseModel):
    job_title: Optional[str] = None


@router.post("/preview")
async def preview(body: PreviewBody, session: AsyncSession = Depends(get_session)):
    """What the import would create or change. Nothing is written."""
    return await compass_service.preview(session, body.packet, engagement_id=body.engagement_id,
                                         dataset_id=body.dataset_id)


@router.post("/apply")
async def apply(body: ApplyBody, session: AsyncSession = Depends(get_session)):
    try:
        result = await compass_service.apply(
            session, body.packet, engagement_id=body.engagement_id, dataset_id=body.dataset_id,
            matches=body.matches, overwrite_name=body.overwrite_name,
            confirm_key_change=body.confirm_key_change)
    except compass_service.ImportRefused as exc:
        return JSONResponse(status_code=422, content={"detail": " ".join(exc.errors),
                                                      "errors": exc.errors})
    await audit_service.record(session, result["engagement_id"], "compass_imported",
                               {"key": result["key"], "roles": result["roles"]})
    return result


@router.get("/{engagement_id}")
async def state(engagement_id: str, dataset_id: Optional[str] = None,
                session: AsyncSession = Depends(get_session)):
    result = await compass_service.state(session, engagement_id, dataset_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Engagement not found")
    return result


@router.put("/{engagement_id}/roles/{ref}")
async def set_role_match(engagement_id: str, ref: str, body: RoleMatchBody,
                         session: AsyncSession = Depends(get_session)):
    result = await compass_service.set_role_match(session, engagement_id, ref, body.job_title)
    if result is None:
        raise HTTPException(status_code=404, detail="Compass role not found")
    return result


async def _return(session, engagement_id, dataset_id):
    result = await compass_return_service.build(session, engagement_id, dataset_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Engagement not found")
    return result


@router.get("/{engagement_id}/return.json")
async def return_json(engagement_id: str, dataset_id: Optional[str] = None,
                      session: AsyncSession = Depends(get_session)):
    """The `compass-return` v1.0 file (findings in the shared shape)."""
    result = await _return(session, engagement_id, dataset_id)
    key = (result["packet"]["engagement_key"] or "workbench").lower()
    return Response(content=compass_return_service.to_json_bytes(result),
                    media_type="application/json",
                    headers={"Content-Disposition": f"attachment; filename={key}_compass_return.json"})


@router.get("/{engagement_id}/return.txt")
async def return_txt(engagement_id: str, dataset_id: Optional[str] = None,
                     session: AsyncSession = Depends(get_session)):
    """The same findings as readable text."""
    result = await _return(session, engagement_id, dataset_id)
    key = (result["packet"]["engagement_key"] or "workbench").lower()
    return Response(content=compass_return_service.to_text(result).encode("utf-8"),
                    media_type="text/plain; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename={key}_compass_return.txt"})
