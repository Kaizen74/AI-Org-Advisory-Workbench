"""Workflow Mapper service (Phase 5, Build Spec M4/B2).

Defines processes / value streams, links tasks (from M2) to process steps ('follow the work'), and
produces a four-level (L0-L3) AI-opportunity matrix per process. The L0-L3 counts are computed
deterministically from the linked tasks' persisted `task_ai_scores`; a Claude call (mocked in tests)
adds a priority/complexity narrative. Every payload carries the standard WORKBank/O*NET caveats.
"""
from __future__ import annotations

import csv
import io
from typing import Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Position, Process, ProcessStep, Task, TaskAIScore, TaskLink
from . import settings_service
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
        model=settings_service.model_synth(), messages=[{"role": "user", "content": prompt}]
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
        "source": score.source if score else None,
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


async def delete_process(session: AsyncSession, process_id: str) -> bool:
    """Delete a process, its steps, and all task links under it. Returns False if missing."""
    if await session.get(Process, process_id) is None:
        return False
    step_ids = await _process_step_ids(session, process_id)
    if step_ids:
        await session.execute(delete(TaskLink).where(TaskLink.process_step_id.in_(step_ids)))
    await session.execute(delete(ProcessStep).where(ProcessStep.process_id == process_id))
    await session.execute(delete(Process).where(Process.id == process_id))
    await session.flush()
    return True


async def delete_step(session: AsyncSession, step_id: str) -> bool:
    """Delete a single step + its task links (linked tasks return to the unmapped tray). False if missing."""
    if await session.get(ProcessStep, step_id) is None:
        return False
    await session.execute(delete(TaskLink).where(TaskLink.process_step_id == step_id))
    await session.execute(delete(ProcessStep).where(ProcessStep.id == step_id))
    await session.flush()
    return True


async def reset_board(session: AsyncSession, process_id: str) -> Optional[Dict]:
    """Unmap every task from this process — clear the board back to the unmapped tray. Returns the
    number of links removed, or None if the process does not exist."""
    if await session.get(Process, process_id) is None:
        return None
    step_ids = await _process_step_ids(session, process_id)
    links = list(await session.scalars(
        select(TaskLink).where(TaskLink.process_step_id.in_(step_ids))
    )) if step_ids else []
    for tl in links:
        await session.delete(tl)
    await session.flush()
    return {"process_id": process_id, "unmapped": len(links)}


# ── Export the finalized workflow (CSV: every mapped task → step → process) ──────────────────
async def export_workflow_csv(session: AsyncSession, engagement_id: str, dataset_id: str) -> bytes:
    """CSV of the finalized workflow for an engagement: one row per task mapped to a step, across all
    processes. Real persisted fields only (role = job title, never a name)."""
    headers = ["process", "value_stream", "step_seq", "step_name", "task_text", "role",
               "department", "human_agency_level", "has_level", "zone", "ai_opportunity_level",
               "review_state", "source"]
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(headers)
    for proc in await list_processes(session, engagement_id):
        b = await board(session, proc.id, dataset_id)
        if b is None:
            continue
        for step in b["steps"]:
            for t in step["tasks"]:
                w.writerow([
                    proc.name, proc.value_stream or "", step["seq"], step["name"], t["text"],
                    t["role"], t.get("department") or "", t["human_agency_level"],
                    "" if t.get("has_level") is None else t["has_level"], t.get("zone") or "",
                    t.get("ai_level") or "", t.get("review_state") or "", t.get("source") or "",
                ])
    return out.getvalue().encode("utf-8")


# ── Landscape & Roll-up exports (D48) — deck/CSV mirrors of the other two views ──────────────────
def _workbank_quadrant(cap: Optional[float], desire: Optional[float]) -> str:
    """The WORKBank zone a plotted dot falls in (0.5 axis split — the UI's quadrant grid, D47).
    Desire not captured → '' (the UI draws those hollow at neutral height, unclassified)."""
    if cap is None or desire is None:
        return ""
    if cap >= 0.5:
        return "Green Light — automate" if desire >= 0.5 else "Red Light — caution"
    return "R&D Opportunity" if desire >= 0.5 else "Low Priority"


async def landscape_rows(session: AsyncSession, dataset_id: str,
                         reviewed_only: bool = False) -> Dict:
    """Every dataset task flattened with the same `_board_task_payload` fields the Landscape view
    plots (capability = X, desire = Y, H-band = colour), split into plotted `points`
    (capability-scored) and an `unscored` count. `reviewed_only` mirrors the UI's
    'Reviewed only' analysis filter (D42)."""
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
    rows = [_board_task_payload(t, positions.get(t.position_id), scores.get(t.id), None)
            for t in tasks]
    if reviewed_only:
        rows = [r for r in rows if r["review_state"] == "approved"]
    points = [r for r in rows if r["capability_score"] is not None]
    for r in points:
        r["workbank_quadrant"] = _workbank_quadrant(r["capability_score"], r["desire_score"])
    return {"points": points, "unscored": len(rows) - len(points), "total": len(rows)}


async def export_landscape_csv(session: AsyncSession, dataset_id: str,
                               reviewed_only: bool = False) -> bytes:
    """CSV of the AI-opportunity landscape: one row per plotted dot (capability-scored task),
    carrying exactly the fields the on-screen plot encodes (axes, H-band colour, quadrant).
    Role = job title, never a name."""
    data = await landscape_rows(session, dataset_id, reviewed_only=reviewed_only)
    headers = ["task_text", "role", "department", "human_agency_level", "capability_score",
               "desire_score", "workbank_quadrant", "zone", "review_state", "source"]
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(headers)
    for r in data["points"]:
        w.writerow([
            r["text"], r["role"], r.get("department") or "", r["human_agency_level"],
            r["capability_score"],
            "" if r["desire_score"] is None else r["desire_score"],
            r["workbank_quadrant"], r.get("zone") or "", r["review_state"], r.get("source") or "",
        ])
    return out.getvalue().encode("utf-8")


def flatten_rollup(rollup: Dict) -> List[Dict]:
    """Depth-first flatten of the org-hierarchy roll-up into display rows — the same order and
    numbers the Roll-up view renders: siblings sorted by rolled-up index (desc), each row with
    own vs team counts, reviewed %, rolled-up index and H-band mix. Role = job title, never a name."""
    from .deliverable_builders import has_index

    nodes = {n["employee_key"]: n for n in rollup["nodes"]}
    children: Dict[str, List[Dict]] = {}
    for n in rollup["nodes"]:
        if n["manager_key"]:
            children.setdefault(n["manager_key"], []).append(n)

    def sort_key(n: Dict):
        # Mirrors the UI's sortByOpportunity: index desc, team size desc, then stable by title.
        return (-has_index(n["rollup_bands"]), -n["rollup_tasks"], n["job_title"])

    rows: List[Dict] = []

    def walk(n: Dict, depth: int) -> None:
        team = n["rollup_tasks"]
        rows.append({
            "employee_key": n["employee_key"],
            "title": n["job_title"],
            "department": n.get("department") or "",
            "depth": depth,
            "level": n.get("level", 0),
            "own": n["self_tasks"],
            "team": team,
            "reviewed_pct": round(n["rollup_reviewed"] / team * 100) if team else 0,
            "index": has_index(n["rollup_bands"]),
            "bands": n["rollup_bands"],
            "direct_reports": n["direct_reports"],
            "total_reports": n["total_reports"],
        })
        for c in sorted(children.get(n["employee_key"], []), key=sort_key):
            walk(c, depth + 1)

    for root in sorted((nodes[k] for k in rollup["roots"] if k in nodes), key=sort_key):
        walk(root, 0)
    return rows


async def export_rollup_csv(session: AsyncSession, dataset_id: str) -> bytes:
    """CSV of the org-hierarchy roll-up: one row per role in the on-screen (depth-first) order,
    with own/team task counts, rolled-up index, reviewed % and the H0–H5 mix."""
    from .task_intelligence_service import org_rollup

    rows = flatten_rollup(await org_rollup(session, dataset_id))
    headers = ["depth", "role", "department", "org_level", "own_tasks", "team_tasks",
               "direct_reports", "total_reports", "rollup_index", "reviewed_pct",
               "H0", "H1", "H2", "H3", "H4", "H5"]
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(headers)
    for r in rows:
        w.writerow([
            r["depth"], r["title"], r["department"], r["level"], r["own"], r["team"],
            r["direct_reports"], r["total_reports"], r["index"], r["reviewed_pct"],
            *(r["bands"].get(b, 0) for b in ("H0", "H1", "H2", "H3", "H4", "H5")),
        ])
    return out.getvalue().encode("utf-8")
