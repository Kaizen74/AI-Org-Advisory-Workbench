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
from ..models import Position, Process, ProcessStep, Task, TaskAIScore, TaskLink
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


# ── Visual board (drag-to-remap) — additive, no migration; reuses existing tables ──
def _board_task_payload(task: Task, pos: Optional[Position], score: Optional[TaskAIScore],
                        step_id: Optional[str]) -> Dict:
    """Flatten a task + its source position + its AI score into one board row.

    Every field is REAL persisted data:
      - role / department        <- Position.job_title / Position.department (never the real name)
      - human_agency_level (H0-H5) <- WORKBank HAS band (headline AI-potential, D17/D19)
      - ai_level (L0..L3)         <- TaskAIScore.ai_opportunity_level (secondary detail)
      - zone / scores / etc.      <- TaskAIScore.*
    Missing AI scores degrade gracefully (H0 / 'L0' / 'unreviewed').
    """
    desire = None
    if score is not None:
        # Prefer the locally-captured desire pulse when present; never overwrite the US score.
        desire = score.desire_score_local if score.desire_score_local is not None else score.desire_score_us
    has_level = score.has_level if score else None
    return {
        "id": task.id,
        "text": task.task_text,
        "role": (pos.job_title if pos else None) or "Unassigned",
        "department": pos.department if pos else None,
        "employee_key": pos.employee_key if pos else None,
        "human_agency_level": human_agency_band(has_level),  # H0-H5 headline
        "has_level": has_level,
        "ai_level": (score.ai_opportunity_level if score else None) or "L0",
        "zone": score.zone if score else None,
        "capability_score": score.capability_score if score else None,
        "desire_score": desire,
        "confidence": score.confidence if score else None,
        "review_state": (score.review_state if score else "unreviewed") or "unreviewed",
        "rationale": score.rationale if score else None,
        "step_id": step_id,
    }


async def board(session: AsyncSession, process_id: str, dataset_id: str) -> Optional[Dict]:
    """The full Workflow-Mapper board for one process over one dataset's tasks.

    Returns the process, its ordered steps each with their mapped tasks, and the dataset's
    still-unmapped tasks (extracted from the CSV upload via Task Intelligence) so the UI can
    drag them onto steps. Returns None if the process does not exist.
    """
    proc = await session.get(Process, process_id)
    if proc is None:
        return None

    steps = list(await session.scalars(
        select(ProcessStep).where(ProcessStep.process_id == process_id).order_by(ProcessStep.seq)
    ))
    step_ids = [s.id for s in steps]

    links = list(await session.scalars(
        select(TaskLink).where(TaskLink.process_step_id.in_(step_ids))
    )) if step_ids else []
    step_by_task: Dict[str, str] = {tl.task_id: tl.process_step_id for tl in links}

    tasks = list(await session.scalars(
        select(Task).join(Position, Task.position_id == Position.id)
        .where(Position.dataset_id == dataset_id).order_by(Task.id)
    ))
    positions = {
        p.id: p
        for p in await session.scalars(select(Position).where(Position.dataset_id == dataset_id))
    }
    task_ids = [t.id for t in tasks]
    scores = {
        s.task_id: s
        for s in await session.scalars(select(TaskAIScore).where(TaskAIScore.task_id.in_(task_ids)))
    } if task_ids else {}

    payloads = [
        _board_task_payload(t, positions.get(t.position_id), scores.get(t.id), step_by_task.get(t.id))
        for t in tasks
    ]
    mapped = [p for p in payloads if p["step_id"]]
    unmapped = [p for p in payloads if not p["step_id"]]
    steps_payload = [
        {"id": s.id, "name": s.name, "seq": s.seq,
         "tasks": [p for p in mapped if p["step_id"] == s.id]}
        for s in steps
    ]
    return {
        "process_id": proc.id,
        "name": proc.name,
        "value_stream": proc.value_stream,
        "steps": steps_payload,
        "unmapped": unmapped,
        "task_count": len(payloads),
        "mapped_count": len(mapped),
        "human_agency_scale": HUMAN_AGENCY_SCALE,
        "caveats": STANDARD_CAVEATS,
    }


async def _process_step_ids(session: AsyncSession, process_id: str) -> List[str]:
    return [
        s.id
        for s in await session.scalars(
            select(ProcessStep).where(ProcessStep.process_id == process_id)
        )
    ]


async def move_task(session: AsyncSession, process_id: str, task_id: str,
                    to_step_id: str) -> Dict:
    """Move a task to a step WITHIN this process (removes its prior link(s) in the same
    process, then links it to the target step). Idempotent."""
    if await session.get(Task, task_id) is None:
        return {"error": "task not found"}
    target = await session.get(ProcessStep, to_step_id)
    if target is None or target.process_id != process_id:
        return {"error": "step not found in process"}

    step_ids = await _process_step_ids(session, process_id)
    existing = list(await session.scalars(
        select(TaskLink).where(TaskLink.task_id == task_id,
                               TaskLink.process_step_id.in_(step_ids))
    )) if step_ids else []
    already = any(tl.process_step_id == to_step_id for tl in existing)
    for tl in existing:
        if tl.process_step_id != to_step_id:
            await session.delete(tl)
    if not already:
        session.add(TaskLink(process_step_id=to_step_id, task_id=task_id))
    await session.flush()
    return {"task_id": task_id, "step_id": to_step_id}


async def unmap_task(session: AsyncSession, process_id: str, task_id: str) -> Dict:
    """Remove a task from every step of this process (back to the 'unmapped' tray)."""
    step_ids = await _process_step_ids(session, process_id)
    existing = list(await session.scalars(
        select(TaskLink).where(TaskLink.task_id == task_id,
                               TaskLink.process_step_id.in_(step_ids))
    )) if step_ids else []
    for tl in existing:
        await session.delete(tl)
    await session.flush()
    return {"task_id": task_id, "unmapped": len(existing)}
