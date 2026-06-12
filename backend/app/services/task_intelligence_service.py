"""Task Intelligence pipeline service (Phase 2, Build Spec M2/B2).

Stages: extract (free-text work activities -> normalised tasks) -> benchmark (vs SFw/O*NET) ->
ai_opportunity (HAS/zone/desire/capability/L0-L3 via the logical O*NET overlay join) -> rollup.

Extraction runs in **batches per department (capped at ~`batch_size` positions)**, in a stable
order, then deterministically merges — removing the single-prompt context ceiling (M2 Upgrade 2).
Every Claude call routes through the `claude_service` singleton and is mocked in tests (A3 Rule 1).
Every AI-derived row carries provenance (`source`, `confidence`, `review_state`) (A4).
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional, Tuple

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import Position, Task
from ._json_utils import parse_ai_json
from .claude_service import claude_service

DEFAULT_BATCH_SIZE = 40

# Caveats that must ride along on every Task Intelligence payload until verified (A4 / M2).
STANDARD_CAVEATS = [
    "WORKBank desire/capability/HAS values are ILLUSTRATIVE — replace with real pulls before client use.",
    "O*NET codes here are occupation-level; verify/refine to task-statement level before client use.",
    "desire_score_us is US worker preference, not local desire — validate locally via the pulse instrument.",
]


# ── Batching (pure, deterministic) ───────────────────────────────────────────
def build_batches(positions: List[Position], batch_size: int = DEFAULT_BATCH_SIZE) -> List[List[Position]]:
    """Group positions by department, then chunk each department to <= batch_size. Deterministic:
    departments sorted by name, positions sorted by employee_key within a department."""
    by_dept: Dict[str, List[Position]] = {}
    for p in positions:
        by_dept.setdefault(p.department or "Unknown", []).append(p)

    batches: List[List[Position]] = []
    for dept in sorted(by_dept):
        members = sorted(by_dept[dept], key=lambda p: p.employee_key)
        for i in range(0, len(members), batch_size):
            batches.append(members[i : i + batch_size])
    return batches


def _build_extract_prompt(batch: List[Position]) -> str:
    """Build a strict-JSON extraction prompt with a machine-readable input block."""
    payload = [
        {"employee_key": p.employee_key, "job_title": p.job_title or "",
         "work_activities": p.work_activities or ""}
        for p in batch
    ]
    return (
        "You are an org-design analyst. For each position, split its free-text work activities into "
        "discrete, normalised tasks (short imperative phrases). Return STRICT JSON of the form "
        '{"extractions": [{"employee_key": "...", "tasks": ["...", "..."]}]}. '
        "Use the exact employee_key values given.\n\nINPUT:\n```json\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n```"
    )


def _extract_batch(batch: List[Position]) -> List[Tuple[str, str]]:
    """Call Claude for one batch and return [(position_id, task_text)] in a stable order."""
    key_to_id = {p.employee_key: p.id for p in batch}
    prompt = _build_extract_prompt(batch)
    raw = claude_service.complete(
        model=settings.MODEL_EXTRACT, messages=[{"role": "user", "content": prompt}]
    )
    data = parse_ai_json(raw)
    out: List[Tuple[str, str]] = []
    for item in data.get("extractions", []):
        pid = key_to_id.get(item.get("employee_key"))
        if pid is None:
            continue
        for task_text in item.get("tasks", []):
            text = str(task_text).strip()
            if text:
                out.append((pid, text))
    return out


async def extract_tasks(
    session: AsyncSession, dataset_id: str, batch_size: int = DEFAULT_BATCH_SIZE
) -> Dict:
    """Extract tasks for all positions in a dataset, batched + deterministically merged.

    Idempotent: clears existing tasks for the dataset's positions first. Returns a summary.
    """
    positions = list(
        await session.scalars(select(Position).where(Position.dataset_id == dataset_id))
    )
    with_activities = [p for p in positions if (p.work_activities or "").strip()]

    # Clear prior tasks for these positions (recompute clean).
    pos_ids = [p.id for p in positions]
    if pos_ids:
        await session.execute(delete(Task).where(Task.position_id.in_(pos_ids)))

    batches = build_batches(with_activities, batch_size)
    tasks_created = 0
    for batch_index, batch in enumerate(batches):
        batch_id = f"batch_{batch_index}"
        for position_id, task_text in _extract_batch(batch):
            session.add(
                Task(
                    position_id=position_id,
                    task_text=task_text,
                    batch_id=batch_id,
                    extraction_source="model-inferred",
                )
            )
            tasks_created += 1
    await session.flush()

    return {
        "dataset_id": dataset_id,
        "positions_total": len(positions),
        "positions_with_activities": len(with_activities),
        "batches": len(batches),
        "batch_size": batch_size,
        "tasks_created": tasks_created,
        "caveats": STANDARD_CAVEATS,
    }


# ── Quick (no API key) — deterministic preview without Claude ────────────────
def quick_stats(positions: List[Position]) -> Dict:
    """A no-AI preview: coverage of work-activities text across the dataset (M2 GET /quick)."""
    total = len(positions)
    with_activities = [p for p in positions if (p.work_activities or "").strip()]
    by_dept: Dict[str, int] = {}
    for p in with_activities:
        by_dept[p.department or "Unknown"] = by_dept.get(p.department or "Unknown", 0) + 1
    coverage = round(len(with_activities) / total * 100, 1) if total else 0.0
    return {
        "positions_total": total,
        "positions_with_activities": len(with_activities),
        "coverage_pct": coverage,
        "departments_with_activities": len(by_dept),
        "estimated_batches": len(build_batches(with_activities)),
    }
