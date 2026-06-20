"""Task Intelligence router — /api/v1/task-intel (Phase 2, Build Spec B2).

Guard pattern: AI endpoints (extract/benchmark/ai-opportunity) return 400 when no Anthropic API key
is configured and 404 when the dataset has no positions/tasks. `GET /quick` is non-AI and works with
no key.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Position
from ..models import get_session
from ..services import audit_service
from ..services import pulse_service
from ..services import task_intelligence_service as tis
from ..services.claude_service import claude_service


async def _audit(session, dataset_id, event_type, result=None):
    pos = await session.scalar(select(Position).where(Position.dataset_id == dataset_id))
    eng_id = None
    if pos is not None:
        from ..models import Dataset
        ds = await session.get(Dataset, dataset_id)
        eng_id = ds.engagement_id if ds else None
    await audit_service.record(session, eng_id, event_type, {"dataset_id": dataset_id})

router = APIRouter(prefix="/api/v1/task-intel", tags=["task-intelligence"])


def _require_api_key() -> None:
    if not claude_service.has_api_key:
        raise HTTPException(status_code=400, detail="Anthropic API key not configured")


async def _positions(session: AsyncSession, dataset_id: str):
    rows = list(await session.scalars(select(Position).where(Position.dataset_id == dataset_id)))
    if not rows:
        raise HTTPException(status_code=404, detail="No positions for dataset (or dataset missing)")
    return rows


@router.post("/extract")
async def extract(dataset_id: str, batch_size: int = tis.DEFAULT_BATCH_SIZE,
                  session: AsyncSession = Depends(get_session)):
    _require_api_key()
    await _positions(session, dataset_id)
    result = await tis.extract_tasks(session, dataset_id, batch_size=batch_size)
    await _audit(session, dataset_id, "ai_extract")
    return result


@router.post("/benchmark")
async def benchmark(dataset_id: str, session: AsyncSession = Depends(get_session)):
    _require_api_key()
    await _positions(session, dataset_id)
    result = await tis.benchmark_tasks(session, dataset_id)
    await _audit(session, dataset_id, "ai_benchmark")
    return result


@router.post("/ai-opportunity")
async def ai_opportunity(dataset_id: str, session: AsyncSession = Depends(get_session)):
    _require_api_key()
    await _positions(session, dataset_id)
    result = await tis.score_ai_opportunity(session, dataset_id)
    await _audit(session, dataset_id, "ai_opportunity")
    return result


@router.post("/infer-potential")
async def infer_potential(dataset_id: str, session: AsyncSession = Depends(get_session)):
    """Robust benchmarking: score tasks with no curated benchmark match by applying the WORKBank
    Human Agency Scale rubric via Claude (model-inferred → unreviewed → export-blocked until approved)."""
    _require_api_key()
    await _positions(session, dataset_id)
    result = await tis.infer_unmatched_potential(session, dataset_id)
    await _audit(session, dataset_id, "infer_potential", result)
    return result


@router.get("/rollup")
async def get_rollup(dataset_id: str, session: AsyncSession = Depends(get_session)):
    return await tis.rollup(session, dataset_id)


@router.get("/quick")
async def quick(dataset_id: str, session: AsyncSession = Depends(get_session)):
    """No-AI preview (work-activities coverage) — no API key required."""
    positions = await _positions(session, dataset_id)
    return tis.quick_stats(positions)


@router.get("/tasks")
async def list_tasks(dataset_id: str, session: AsyncSession = Depends(get_session)):
    """List a dataset's extracted tasks (no API key) — used by the Workflow Mapper."""
    return {"tasks": await tis.list_tasks(session, dataset_id)}


# ── Desire pulse (local desire capture; no API key) ──────────────────────────
_XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/pulse/instrument.xlsx")
async def pulse_instrument(dataset_id: str, top_n: int = 20,
                           session: AsyncSession = Depends(get_session)):
    """Download the top-N tasks as an xlsx for the client workforce to rate (1-5)."""
    await _positions(session, dataset_id)
    data = await pulse_service.export_instrument(session, dataset_id, top_n=top_n)
    return Response(
        content=data, media_type=_XLSX_MEDIA,
        headers={"Content-Disposition": "attachment; filename=desire_pulse_instrument.xlsx"},
    )


@router.post("/pulse/responses")
async def pulse_responses(engagement_id: str, dataset_id: str, file: UploadFile = File(...),
                          session: AsyncSession = Depends(get_session)):
    """Import filled responses (xlsx/CSV) → recompute desire_score_local (US score untouched)."""
    content = await file.read()
    return await pulse_service.import_responses(
        session, engagement_id, dataset_id, content, filename=file.filename
    )


# ── Local desirability → manual AI opportunity for tasks with no valid benchmark (no API key) ──
@router.get("/desirability-template.csv")
async def desirability_template(dataset_id: str, session: AsyncSession = Depends(get_session)):
    """CSV (task_ref=task id, task_text, desire_rating) for tasks lacking a valid benchmark — fill
    desire_rating (1=keep human .. 5=automate) and re-upload to set a consultant AI opportunity."""
    await _positions(session, dataset_id)
    data = await pulse_service.export_desirability_template(session, dataset_id)
    return Response(
        content=data, media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=local_desirability_template.csv"},
    )


@router.post("/desirability")
async def apply_desirability(dataset_id: str, file: UploadFile = File(...),
                             session: AsyncSession = Depends(get_session)):
    """Apply a filled local-desirability CSV → consultant-approved AI opportunity for unbenchmarked
    tasks (keyed by task id; benchmarked tasks only get their local desire updated)."""
    await _positions(session, dataset_id)
    content = await file.read()
    result = await pulse_service.apply_local_desirability(
        session, dataset_id, content, filename=file.filename
    )
    await _audit(session, dataset_id, "local_desirability_applied", result)
    return result
