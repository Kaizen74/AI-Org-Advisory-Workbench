"""Transition Planner router — /api/v1/transition (Phase 5, Build Spec B2)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import get_session
from ..services import transition_service as svc
from ..services.claude_service import claude_service

router = APIRouter(prefix="/api/v1/transition", tags=["transition"])
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.post("/compute")
async def compute(scenario_id: str, session: AsyncSession = Depends(get_session)):
    """Impact classes + reskilling pathway suggestions for a scenario (AI → needs a key)."""
    if not claude_service.has_api_key:
        raise HTTPException(status_code=400, detail="Anthropic API key not configured")
    result = await svc.compute(session, scenario_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return result


@router.get("/register")
async def register(scenario_id: str, session: AsyncSession = Depends(get_session)):
    if not claude_service.has_api_key:
        raise HTTPException(status_code=400, detail="Anthropic API key not configured")
    result = await svc.compute(session, scenario_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return {"scenario_id": scenario_id, "register": result["register"], "summary": result["summary"]}


@router.get("/register.xlsx")
async def register_xlsx(scenario_id: str, session: AsyncSession = Depends(get_session)):
    if not claude_service.has_api_key:
        raise HTTPException(status_code=400, detail="Anthropic API key not configured")
    result = await svc.compute(session, scenario_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    data = svc.register_to_xlsx(result["register"])
    return Response(content=data, media_type=_XLSX,
                    headers={"Content-Disposition": "attachment; filename=transition_register.xlsx"})
