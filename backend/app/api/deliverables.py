"""Deliverables router — /api/v1/deliverables (Phase 6, Build Spec B2).

Non-AI (no API key): deliverables are generated from persisted data. Export-block + provenance
disclosure are enforced inside the service.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Deliverable, get_session
from ..services import deliverable_service as svc

router = APIRouter(prefix="/api/v1/deliverables", tags=["deliverables"])


@router.get("/types")
async def types():
    return {"types": svc.DELIVERABLE_TYPES}


@router.post("/generate")
async def generate(
    engagement_id: str,
    type: str,
    template: str = "minimal",
    dataset_id: Optional[str] = None,
    scenario_id: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    if type not in svc.DELIVERABLE_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown deliverable type: {type}")
    result = await svc.generate(session, engagement_id=engagement_id, type=type, template=template,
                                dataset_id=dataset_id, scenario_id=scenario_id)
    if result is None:
        raise HTTPException(status_code=400, detail="Could not generate deliverable")
    return result


@router.get("/list")
async def list_(engagement_id: str, session: AsyncSession = Depends(get_session)):
    return {"deliverables": await svc.list_deliverables(session, engagement_id)}


@router.get("/{deliverable_id}/download")
async def download(deliverable_id: str, session: AsyncSession = Depends(get_session)):
    row = await session.get(Deliverable, deliverable_id)
    if row is None or not row.file_path or not Path(row.file_path).exists():
        raise HTTPException(status_code=404, detail="Deliverable file not found")
    return FileResponse(row.file_path, filename=Path(row.file_path).name)
