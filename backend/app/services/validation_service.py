"""Validation service (Phase 3, Build Spec M2 Upgrade 1 / M3).

The human-in-the-loop trust loop. Surfaces model-inferred / low-confidence mappings from three
sources — `task_benchmarks`, `task_ai_scores`, and reference `taxonomy_crosswalk` (the seed's 0.40
row included) — into one review queue. Bulk approve/edit/reject updates `review_state`; approving a
benchmark writes a `CURATED_BY_CONSULTANT` crosswalk so the system learns per engagement.

`client_ready_ai_scores` enforces the deliverable rule (A4/M6): unreviewed model-inferred content is
excluded from client-ready payloads.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Position,
    Task,
    TaskAIScore,
    TaskBenchmark,
    TaxonomyCrosswalk,
    TaxonomyTask,
)
from .task_intelligence_service import apply_manual_opportunity, human_agency_band

_ACTION_TO_STATE = {"approve": "approved", "edit": "edited", "reject": "rejected"}


def _below(confidence: Optional[float], max_confidence: Optional[float]) -> bool:
    if max_confidence is None:
        return True
    return confidence is None or confidence < max_confidence


async def _dataset_task_ids(session: AsyncSession, dataset_id: str) -> List[str]:
    rows = await session.scalars(
        select(Task.id)
        .join(Position, Task.position_id == Position.id)
        .where(Position.dataset_id == dataset_id)
    )
    return list(rows)


async def get_queue(
    session: AsyncSession,
    dataset_id: Optional[str] = None,
    max_confidence: Optional[float] = None,
    include_reviewed: bool = False,
) -> List[Dict]:
    """Unified review items. Default shows only `unreviewed`; `max_confidence` filters by confidence."""
    items: List[Dict] = []
    task_ids = await _dataset_task_ids(session, dataset_id) if dataset_id else None

    # Benchmarks — only MATCHED ones are actionable review items (approving one curates a crosswalk).
    # EXTRA/MISSING ("no benchmark match") aren't approvable and would otherwise double every
    # no-benchmark task with a noisy, non-resolvable row — the task's ai_score row already carries the
    # reviewable AI opportunity (+ the manual-rating override). So they are not listed here.
    bstmt = select(TaskBenchmark)
    if task_ids is not None:
        bstmt = bstmt.where(TaskBenchmark.task_id.in_(task_ids))
    benchmarks = [
        b for b in await session.scalars(bstmt)
        if b.status == "MATCHED"
        and (include_reviewed or b.review_state == "unreviewed") and _below(b.confidence, max_confidence)
    ]

    # AI scores
    sstmt = select(TaskAIScore)
    if task_ids is not None:
        sstmt = sstmt.where(TaskAIScore.task_id.in_(task_ids))
    ai_scores = [
        s for s in await session.scalars(sstmt)
        if (include_reviewed or s.review_state == "unreviewed") and _below(s.confidence, max_confidence)
    ]

    # One lookup of task text so each row is identifiable in the UI (distinct tasks otherwise render
    # as identical labels — e.g. many "EXTRA → …" / "L0 · zone …" rows look like duplicates).
    needed_ids = {b.task_id for b in benchmarks} | {s.task_id for s in ai_scores}
    text_by_task: Dict[str, str] = {}
    if needed_ids:
        for t in await session.scalars(select(Task).where(Task.id.in_(needed_ids))):
            text_by_task[t.id] = t.task_text

    for b in benchmarks:
        # Show the ACTUAL benchmarked source (SFw primary / O*NET bridge), not a hardcoded one.
        # When nothing matched, say so plainly instead of an opaque "EXTRA → — —".
        if b.onet_task_code:
            target = b.taxonomy_source_code or "O*NET"
            label = f"{b.status} → {target} {b.onet_task_code}"
        else:
            label = f"{b.status} → no benchmark match (load a relevant taxonomy)"
        items.append({
            "kind": "benchmark", "id": b.id, "task_id": b.task_id,
            "task_text": text_by_task.get(b.task_id),
            "label": label,
            "source": b.source, "confidence": b.confidence, "review_state": b.review_state,
        })

    for s in ai_scores:
        band = human_agency_band(s.has_level)  # headline AI-potential band (D17)
        items.append({
            "kind": "ai_score", "id": s.id, "task_id": s.task_id,
            "task_text": text_by_task.get(s.task_id), "has_level": s.has_level,
            "label": f"{band} · {s.ai_opportunity_level} · zone {s.zone or '—'}",
            "source": s.source, "confidence": s.confidence, "review_state": s.review_state,
        })

    # Reference crosswalks (global; the seed's 0.40 row lands here) — Build Spec B0.
    for c in await session.scalars(select(TaxonomyCrosswalk)):
        if (include_reviewed or c.review_state == "unreviewed") and _below(c.confidence, max_confidence):
            items.append({
                "kind": "crosswalk", "id": c.id, "task_id": None, "task_text": None,
                "label": f"crosswalk → {c.to_source_code} {c.to_task_code}",
                "source": c.method, "confidence": c.confidence, "review_state": c.review_state,
            })

    return items


async def _learn_crosswalk_from_benchmark(session: AsyncSession, benchmark: TaskBenchmark) -> bool:
    """On approval, persist a CURATED_BY_CONSULTANT crosswalk capturing the approved mapping."""
    if not benchmark.matched_taxonomy_task_id or not benchmark.onet_task_code:
        return False
    existing = await session.scalar(
        select(TaxonomyCrosswalk).where(
            TaxonomyCrosswalk.from_task_id == benchmark.matched_taxonomy_task_id,
            TaxonomyCrosswalk.to_task_code == benchmark.onet_task_code,
            TaxonomyCrosswalk.method == "CURATED_BY_CONSULTANT",
        )
    )
    if existing is not None:
        return False
    matched = await session.get(TaxonomyTask, benchmark.matched_taxonomy_task_id)
    session.add(TaxonomyCrosswalk(
        from_source_id=matched.source_id if matched else None,
        from_task_id=benchmark.matched_taxonomy_task_id,
        to_source_code="ONET",
        to_task_code=benchmark.onet_task_code,
        confidence=1.0,
        method="CURATED_BY_CONSULTANT",
        review_state="approved",
        note="Learned from a consultant-approved task benchmark.",
    ))
    return True


_MODEL_BY_KIND = {
    "benchmark": TaskBenchmark,
    "ai_score": TaskAIScore,
    "crosswalk": TaxonomyCrosswalk,
}


async def review_items(session: AsyncSession, reviews: List[Dict]) -> Dict:
    """Apply bulk review actions. Each review: {kind, id, action ∈ approve|edit|reject, edits?}."""
    updated = 0
    crosswalks_created = 0
    for r in reviews:
        model = _MODEL_BY_KIND.get(r.get("kind"))
        action = r.get("action")
        if model is None or action not in _ACTION_TO_STATE:
            continue
        row = await session.get(model, r.get("id"))
        if row is None:
            continue
        row.review_state = _ACTION_TO_STATE[action]
        if hasattr(row, "reviewed_at"):
            row.reviewed_at = datetime.utcnow()
        # Apply edits to whitelisted fields.
        for field, value in (r.get("edits") or {}).items():
            if hasattr(row, field) and field not in {"id", "review_state", "reviewed_at"}:
                setattr(row, field, value)
        # Crosswalk learning on approving/editing a benchmark.
        if r["kind"] == "benchmark" and action in {"approve", "edit"}:
            if await _learn_crosswalk_from_benchmark(session, row):
                crosswalks_created += 1
        updated += 1
    await session.flush()
    return {"updated": updated, "crosswalks_created": crosswalks_created}


async def set_manual_opportunity(session: AsyncSession, task_id: str, rating: int) -> Optional[Dict]:
    """Inline Validation-Queue override: set a consultant-approved AI opportunity for a TASK from a
    1-5 rating. Keyed by task_id so it works from either the ai_score or the 'no benchmark match'
    (EXTRA) benchmark row. Creates the score row if the task was never AI-scored. None if no task.
    Also resolves the task's benchmark review item(s) so the WHOLE task leaves the queue consistently."""
    if await session.get(Task, task_id) is None:
        return None
    score = await session.scalar(select(TaskAIScore).where(TaskAIScore.task_id == task_id))
    if score is None:
        score = TaskAIScore(task_id=task_id, source="consultant-approved", review_state="approved")
        session.add(score)
    apply_manual_opportunity(score, rating)
    # The task also has a benchmark review row (e.g. EXTRA → no match). The consultant has now resolved
    # the task's AI opportunity by hand, so mark that benchmark reviewed too — otherwise the same task
    # lingers in the queue via its benchmark row. (EXTRA/MISSING have no match → no crosswalk learned.)
    for b in await session.scalars(select(TaskBenchmark).where(TaskBenchmark.task_id == task_id)):
        if b.review_state == "unreviewed":
            b.review_state = "edited"
            if hasattr(b, "reviewed_at"):
                b.reviewed_at = datetime.utcnow()
    await session.flush()
    return {
        "task_id": task_id,
        "human_agency_level": human_agency_band(score.has_level),
        "ai_opportunity_level": score.ai_opportunity_level,
        "zone": score.zone,
        "review_state": score.review_state,
        "source": score.source,
    }


async def get_stats(session: AsyncSession, dataset_id: Optional[str] = None) -> Dict:
    """Counts per kind per review_state."""
    items = await get_queue(session, dataset_id=dataset_id, include_reviewed=True)
    stats: Dict[str, Dict[str, int]] = {}
    for it in items:
        kind = stats.setdefault(it["kind"], {})
        kind[it["review_state"]] = kind.get(it["review_state"], 0) + 1
    return stats


def is_client_ready(source: Optional[str], review_state: Optional[str]) -> bool:
    """Deliverable rule (A4/M6): exclude rejected, and exclude unreviewed model-inferred content."""
    if review_state == "rejected":
        return False
    if source == "model-inferred" and review_state == "unreviewed":
        return False
    return True


async def client_ready_ai_scores(session: AsyncSession, dataset_id: str) -> List[TaskAIScore]:
    """AI scores eligible for a client deliverable (unreviewed model-inferred excluded)."""
    task_ids = await _dataset_task_ids(session, dataset_id)
    if not task_ids:
        return []
    scores = await session.scalars(select(TaskAIScore).where(TaskAIScore.task_id.in_(task_ids)))
    return [s for s in scores if is_client_ready(s.source, s.review_state)]
