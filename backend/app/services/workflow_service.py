"""Workflow Mapper service (Phase 5, Build Spec M4/B2).

Defines processes / value streams, links tasks (from M2) to process steps ('follow the work'), and
produces a four-level (L0-L3) AI-opportunity matrix per process. The L0-L3 counts are computed
deterministically from the linked tasks' persisted `task_ai_scores`; a Claude call (mocked in tests)
adds a priority/complexity narrative. Every payload carries the standard WORKBank/O*NET caveats.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import Process, ProcessStep, Task, TaskAIScore, TaskLink
from ._json_utils import parse_ai_json
from .claude_service import claude_service
from .task_intelligence_service import HUMAN_AGENCY_SCALE, STANDARD_CAVEATS, human_agency_band

LEVELS = ["L0", "L1", "L2", "L3"]
AGENCY_BANDS = ["H0", "H1", "H2", "H3", "H4", "H5"]  # WORKBank Human Agency Scale (D17/D19 headline)


# ── CRUD ─────────────────────────────────────────────────────────────────────
async def create_process(session: AsyncSession, *, engagement_id: str, name: str,
                         value_stream: Optional[str] = None) -> Process:
    proc = Process(engagement_id=engagement_id, name=name, value_stream=value_stream)
    session.add(proc)
    await session.flush()
    return proc


async def list_processes(session: AsyncSession, engagement_id: str) -> List[Process]:
    return list(await session.scalars(
        select(Process).where(Process.engagement_id == engagement_id).order_by(Process.created_at)
    ))


async def add_step(session: AsyncSession, process_id: str, name: str) -> Optional[ProcessStep]:
    if await session.get(Process, process_id) is None:
        return None
    from sqlalchemy import func
    next_seq = (await session.scalar(
        select(func.max(ProcessStep.seq)).where(ProcessStep.process_id == process_id)
    ) or 0) + 1
    step = ProcessStep(process_id=process_id, seq=next_seq, name=name)
    session.add(step)
    await session.flush()
    return step


async def list_steps(session: AsyncSession, process_id: str) -> Optional[List[Dict]]:
    """Steps for a process, each with its linked task ids + count (None if the process is missing)."""
    if await session.get(Process, process_id) is None:
        return None
    steps = list(await session.scalars(
        select(ProcessStep).where(ProcessStep.process_id == process_id).order_by(ProcessStep.seq)
    ))
    links_by_step: Dict[str, List[str]] = {}
    if steps:
        rows = await session.execute(
            select(TaskLink.process_step_id, TaskLink.task_id)
            .where(TaskLink.process_step_id.in_([s.id for s in steps]))
        )
        for sid, tid in rows.all():
            links_by_step.setdefault(sid, []).append(tid)
    return [
        {"id": s.id, "seq": s.seq, "name": s.name,
         "linked_tasks": len(links_by_step.get(s.id, [])),
         "linked_task_ids": links_by_step.get(s.id, [])}
        for s in steps
    ]


async def map_tasks(session: AsyncSession, step_id: str, task_ids: List[str]) -> Dict:
    """Link tasks to a process step (idempotent — existing links are skipped)."""
    if await session.get(ProcessStep, step_id) is None:
        return {"linked": 0, "error": "step not found"}
    existing = {
        tl.task_id
        for tl in await session.scalars(
            select(TaskLink).where(TaskLink.process_step_id == step_id)
        )
    }
    linked = 0
    for tid in task_ids:
        if tid in existing:
            continue
        if await session.get(Task, tid) is None:
            continue
        session.add(TaskLink(process_step_id=step_id, task_id=tid))
        linked += 1
    await session.flush()
    return {"step_id": step_id, "linked": linked}


# ── Opportunity matrix (deterministic counts + mocked-AI narrative) ──────────
async def _process_level_counts(session: AsyncSession, process_id: str):
    steps = list(await session.scalars(
        select(ProcessStep).where(ProcessStep.process_id == process_id).order_by(ProcessStep.seq)
    ))
    step_ids = [s.id for s in steps]
    links = list(await session.scalars(
        select(TaskLink).where(TaskLink.process_step_id.in_(step_ids))
    )) if step_ids else []
    task_ids = [tl.task_id for tl in links]
    scores = {
        s.task_id: s
        for s in await session.scalars(select(TaskAIScore).where(TaskAIScore.task_id.in_(task_ids)))
    } if task_ids else {}
    tasks = {
        t.id: t for t in await session.scalars(select(Task).where(Task.id.in_(task_ids)))
    } if task_ids else {}

    step_payload = []
    overall = {lvl: 0 for lvl in LEVELS}
    evidencing: Dict[str, List[str]] = {lvl: [] for lvl in LEVELS}
    # Headline AI-potential banding (H0–H5) computed from each linked task's HAS level (D19).
    agency_overall = {b: 0 for b in AGENCY_BANDS}
    agency_evidencing: Dict[str, List[str]] = {b: [] for b in AGENCY_BANDS}
    for step in steps:
        counts = {lvl: 0 for lvl in LEVELS}
        agency_counts = {b: 0 for b in AGENCY_BANDS}
        for tl in links:
            if tl.process_step_id != step.id:
                continue
            score = scores.get(tl.task_id)
            lvl = (score.ai_opportunity_level if score else "L0") or "L0"
            band = human_agency_band(score.has_level if score else None)
            counts[lvl] = counts.get(lvl, 0) + 1
            overall[lvl] = overall.get(lvl, 0) + 1
            agency_counts[band] = agency_counts.get(band, 0) + 1
            agency_overall[band] = agency_overall.get(band, 0) + 1
            task = tasks.get(tl.task_id)
            if task and len(evidencing[lvl]) < 5:
                evidencing[lvl].append(task.task_text)
            if task and len(agency_evidencing[band]) < 5:
                agency_evidencing[band].append(task.task_text)
        step_payload.append({"step_id": step.id, "name": step.name, "seq": step.seq,
                             "level_counts": counts, "agency_counts": agency_counts})
    return steps, step_payload, overall, evidencing, agency_overall, agency_evidencing


def _ai_priority(process_name: str, overall: Dict[str, int],
                 agency_overall: Optional[Dict[str, int]] = None) -> Dict:
    """Mocked-in-tests Claude call for a priority/complexity narrative."""
    prompt = (
        f"Assess the AI-transformation priority for process '{process_name}' given its Human Agency "
        f"Scale distribution {agency_overall or {}} (H0=no software-agent overlay; lower H = more "
        f"AI-amenable) and L0-L3 task distribution {overall}. Return STRICT JSON "
        '{"priority": "High|Medium|Low", "complexity": "High|Medium|Low", "rationale": "..."}.'
    )
    raw = claude_service.complete(
        model=settings.MODEL_SYNTH, messages=[{"role": "user", "content": prompt}]
    )
    data = parse_ai_json(raw)
    return {
        "priority": data.get("priority", "Medium"),
        "complexity": data.get("complexity", "Medium"),
        "rationale": data.get("rationale", ""),
        "source": "model-inferred",
        "review_state": "unreviewed",
    }


async def opportunity_matrix(session: AsyncSession, process_id: str) -> Optional[Dict]:
    proc = await session.get(Process, process_id)
    if proc is None:
        return None
    steps, step_payload, overall, evidencing, agency_overall, agency_evidencing = \
        await _process_level_counts(session, process_id)
    assessment = _ai_priority(proc.name, overall, agency_overall)
    return {
        "process_id": process_id,
        "name": proc.name,
        "value_stream": proc.value_stream,
        "matrix": overall,
        "agency_matrix": agency_overall,
        "steps": step_payload,
        "evidencing_tasks": evidencing,
        "agency_evidencing": agency_evidencing,
        "human_agency_scale": HUMAN_AGENCY_SCALE,
        "assessment": assessment,
        "caveats": STANDARD_CAVEATS,
    }
