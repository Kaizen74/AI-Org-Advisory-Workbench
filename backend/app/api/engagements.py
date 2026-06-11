"""Engagement Hub router — /api/v1/engagements (Phase 1, Build Spec B2).

All endpoints are non-AI and work without an Anthropic API key.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import get_session
from ..services import engagement_service as svc
from .schemas import (
    ClientCreate,
    ClientOut,
    DatasetOut,
    EngagementCreate,
    EngagementOut,
)

router = APIRouter(prefix="/api/v1/engagements", tags=["engagements"])


# ── Clients ──────────────────────────────────────────────────────────────────
@router.post("/clients", response_model=ClientOut, status_code=201)
async def create_client(body: ClientCreate, session: AsyncSession = Depends(get_session)):
    return await svc.create_client(
        session, name=body.name, industry=body.industry,
        anonymization_default=body.anonymization_default,
    )


@router.get("/clients", response_model=List[ClientOut])
async def list_clients(session: AsyncSession = Depends(get_session)):
    return await svc.list_clients(session)


# ── Engagements ──────────────────────────────────────────────────────────────
@router.post("", response_model=EngagementOut, status_code=201)
async def create_engagement(body: EngagementCreate, session: AsyncSession = Depends(get_session)):
    engagement = await svc.create_engagement(session, **body.model_dump())
    if engagement is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return engagement


@router.get("", response_model=List[EngagementOut])
async def list_engagements(
    client_id: Optional[str] = None, session: AsyncSession = Depends(get_session)
):
    return await svc.list_engagements(session, client_id=client_id)


@router.get("/{engagement_id}", response_model=EngagementOut)
async def get_engagement(engagement_id: str, session: AsyncSession = Depends(get_session)):
    engagement = await svc.get_engagement(session, engagement_id)
    if engagement is None:
        raise HTTPException(status_code=404, detail="Engagement not found")
    return engagement


# ── Datasets ─────────────────────────────────────────────────────────────────
@router.post("/{engagement_id}/datasets", response_model=DatasetOut, status_code=201)
async def upload_dataset(
    engagement_id: str,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    content = await file.read()
    dataset = await svc.create_dataset_from_csv(
        session, engagement_id=engagement_id, filename=file.filename, content=content
    )
    if dataset is None:
        raise HTTPException(status_code=404, detail="Engagement not found")
    return dataset


@router.get("/{engagement_id}/datasets", response_model=List[DatasetOut])
async def list_datasets(engagement_id: str, session: AsyncSession = Depends(get_session)):
    return await svc.list_datasets(session, engagement_id)


# ── Purge ────────────────────────────────────────────────────────────────────
@router.delete("/{engagement_id}/purge", status_code=200)
async def purge(engagement_id: str, session: AsyncSession = Depends(get_session)):
    ok = await svc.purge_engagement(session, engagement_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Engagement not found")
    return {"purged": engagement_id}
