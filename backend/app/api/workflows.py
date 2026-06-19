"""Workflow Mapper router — /api/v1/workflows (Phase 5, Build Spec B2)."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import get_session
from ..services import workflow_service as svc
from ..services.claude_service import claude_service

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])


class ProcessCreate(BaseModel):
    engagement_id: str
    name: str
    value_stream: Optional[str] = None


class StepCreate(BaseModel):
    name: str


class MoveTaskBody(BaseModel):
    task_id: str
    to_step_id: str


class UnmapTaskBody(BaseModel):
    task_id: str


@router.post("", status_code=201)
async def create_process(body: ProcessCreate, session: AsyncSession = Depends(get_session)):
    proc = await svc.create_process(session, engagement_id=body.engagement_id, name=body.name,
                                    value_stream=body.value_stream)
    return {"id": proc.id, "name": proc.name, "value_stream": proc.value_stream}


@router.get("")
async def list_processes(engagement_id: str, session: AsyncSession = Depends(get_session)):
    rows = await svc.list_processes(session, engagement_id)
    return [{"id": p.id, "name": p.name, "value_stream": p.value_stream} for p in rows]


@router.post("/{process_id}/steps", status_code=201)
async def add_step(process_id: str, body: StepCreate, session: AsyncSession = Depends(get_session)):
    step = await svc.add_step(session, process_id, body.name)
    if step is None:
        raise HTTPException(status_code=404, detail="Process not found")
    return {"id": step.id, "seq": step.seq, "name": step.name, "linked_tasks": 0}


@router.get("/{process_id}/steps")
async def list_steps(process_id: str, session: AsyncSession = Depends(get_session)):
    steps = await svc.list_steps(session, process_id)
    if steps is None:
        raise HTTPException(status_code=404, detail="Process not found")
    return {"steps": steps}


@router.post("/steps/{step_id}/map-tasks")
async def map_tasks(step_id: str, task_ids: List[str] = Body(..., embed=True),
                    session: AsyncSession = Depends(get_session)):
    result = await svc.map_tasks(session, step_id, task_ids)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/{process_id}/opportunity-matrix")
async def opportunity_matrix(process_id: str, session: AsyncSession = Depends(get_session)):
    if not claude_service.has_api_key:
        raise HTTPException(status_code=400, detail="Anthropic API key not configured")
    result = await svc.opportunity_matrix(session, process_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Process not found")
    return result


@router.get("/{process_id}/board")
async def board(process_id: str, dataset_id: str, session: AsyncSession = Depends(get_session)):
    """Full board for the Workflow Mapper: steps + their mapped tasks + the dataset's
    still-unmapped tasks (no Anthropic key required — reads persisted data only)."""
    result = await svc.board(session, process_id, dataset_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Process not found")
    return result


@router.post("/{process_id}/move-task")
async def move_task(process_id: str, body: MoveTaskBody,
                    session: AsyncSession = Depends(get_session)):
    """Move a task to a different step within this process (drag-to-remap)."""
    result = await svc.move_task(session, process_id, body.task_id, body.to_step_id)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/{process_id}/unmap-task")
async def unmap_task(process_id: str, body: UnmapTaskBody,
                     session: AsyncSession = Depends(get_session)):
    """Remove a task from this process (returns it to the unmapped tray)."""
    return await svc.unmap_task(session, process_id, body.task_id)
