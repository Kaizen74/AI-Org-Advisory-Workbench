"""Scenarios router — /api/v1/scenarios (Phase 4, Build Spec B2). Non-AI (no API key needed)."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import get_session
from ..services import scenario_service as svc
from ..services.scenario_engine import MOVE_TYPES

router = APIRouter(prefix="/api/v1/scenarios", tags=["scenarios"])


class ScenarioCreate(BaseModel):
    engagement_id: str
    dataset_id: str
    name: str


class MoveCreate(BaseModel):
    move_type: str
    params: Optional[dict] = None
    rationale: Optional[str] = None
    activator_tag: Optional[int] = None


@router.post("", status_code=201)
async def create(body: ScenarioCreate, session: AsyncSession = Depends(get_session)):
    scenario = await svc.create_scenario(
        session, engagement_id=body.engagement_id, dataset_id=body.dataset_id, name=body.name
    )
    if scenario is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return {"id": scenario.id, "name": scenario.name, "status": scenario.status}


@router.get("")
async def list_(engagement_id: Optional[str] = None, session: AsyncSession = Depends(get_session)):
    rows = await svc.list_scenarios(session, engagement_id=engagement_id)
    return [{"id": s.id, "name": s.name, "status": s.status,
             "parent_scenario_id": s.parent_scenario_id} for s in rows]


@router.get("/move-types")
async def move_types():
    return {"move_types": sorted(MOVE_TYPES)}


@router.post("/{scenario_id}/moves", status_code=201)
async def add_move(scenario_id: str, body: MoveCreate, session: AsyncSession = Depends(get_session)):
    if body.move_type not in MOVE_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown move_type: {body.move_type}")
    try:
        move = await svc.add_move(session, scenario_id, move_type=body.move_type, params=body.params,
                                  rationale=body.rationale, activator_tag=body.activator_tag)
    except svc.ScenarioLocked:
        raise HTTPException(status_code=409, detail="Scenario is PRESENTED (locked) — fork to edit")
    if move is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return {"id": move.id, "seq": move.seq, "move_type": move.move_type}


@router.delete("/{scenario_id}/moves/{seq}")
async def remove_move(scenario_id: str, seq: int, session: AsyncSession = Depends(get_session)):
    try:
        ok = await svc.remove_move(session, scenario_id, seq)
    except svc.ScenarioLocked:
        raise HTTPException(status_code=409, detail="Scenario is PRESENTED (locked) — fork to edit")
    if not ok:
        raise HTTPException(status_code=404, detail="Scenario or move not found")
    return {"removed_seq": seq}


@router.get("/{scenario_id}/delta")
async def delta(scenario_id: str, session: AsyncSession = Depends(get_session)):
    result = await svc.compute_delta(session, scenario_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return result


@router.get("/compare")
async def compare(ids: str, session: AsyncSession = Depends(get_session)):
    """Compare up to 3 scenarios: ?ids=a,b,c"""
    id_list = [s for s in ids.split(",") if s]
    return await svc.compare(session, id_list[:3])


@router.post("/{scenario_id}/present")
async def present(scenario_id: str, session: AsyncSession = Depends(get_session)):
    scenario = await svc.present(session, scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return {"id": scenario.id, "status": scenario.status}


@router.post("/{scenario_id}/fork", status_code=201)
async def fork(scenario_id: str, session: AsyncSession = Depends(get_session)):
    child = await svc.fork(session, scenario_id)
    if child is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return {"id": child.id, "name": child.name, "parent_scenario_id": child.parent_scenario_id}
