"""Local-desire pulse instrument (Phase 3, Build Spec M2 "Local desire capture").

Exports the top-N benchmarked tasks as an xlsx the client workforce fills in (automation-desire
1-5), then imports the responses and recomputes `desire_score_local` — which sits BESIDE, and never
overwrites, the WORKBank US score `desire_score_us` (binding guardrail A4).

Local desire is engagement-specific, so it is written to `task_ai_scores.desire_score_local` (not to
the engagement-independent reference overlay).
"""
from __future__ import annotations

import csv
import io
from typing import Dict, List, Optional, Tuple

from openpyxl import Workbook, load_workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Dataset,
    DesirePulseResponse,
    Position,
    Task,
    TaskAIScore,
    TaskBenchmark,
    TaxonomyTask,
)

INSTRUMENT_HEADERS = ["task_ref", "task_text", "desire_rating (1=keep human .. 5=automate)"]

# Sources that represent a curated/real benchmark — excluded from the manual template (already scored).
_BENCHMARK_SOURCES = ("WORKBank", "consultant-approved", "SFw", "ONET")
# External benchmarks whose AI-opportunity is authoritative and must NOT be overwritten by a manual
# upload (only their local desire is updated). consultant-approved is re-applicable, so not protected.
_PROTECTED_SOURCES = ("WORKBank", "SFw", "ONET")


async def _benchmarked_task_refs(session: AsyncSession, dataset_id: str) -> List[Tuple[str, str]]:
    """Distinct (task_ref, task_text) for the dataset's benchmarked tasks, by frequency desc."""
    task_rows = list(
        await session.scalars(
            select(Task).join(Position, Task.position_id == Position.id).where(
                Position.dataset_id == dataset_id
            )
        )
    )
    by_task = {t.id: t for t in task_rows}
    benchmarks = list(
        await session.scalars(
            select(TaskBenchmark).where(TaskBenchmark.task_id.in_(list(by_task)))
        )
    )
    taxo = {t.id: t for t in await session.scalars(select(TaxonomyTask))}

    freq: Dict[str, int] = {}
    text: Dict[str, str] = {}
    for b in benchmarks:
        if not b.matched_taxonomy_task_id:
            continue
        tt = taxo.get(b.matched_taxonomy_task_id)
        if tt is None:
            continue
        freq[tt.task_ref] = freq.get(tt.task_ref, 0) + 1
        text.setdefault(tt.task_ref, tt.task_text)
    ordered = sorted(freq, key=lambda r: (-freq[r], r))
    return [(ref, text[ref]) for ref in ordered]


async def export_instrument(session: AsyncSession, dataset_id: str, top_n: int = 20) -> bytes:
    """Build an xlsx of the top-N benchmarked tasks for the workforce to rate. Returns bytes."""
    rows = (await _benchmarked_task_refs(session, dataset_id))[:top_n]
    wb = Workbook()
    ws = wb.active
    ws.title = "Desire Pulse"
    ws.append(INSTRUMENT_HEADERS)
    for ref, text in rows:
        ws.append([ref, text, ""])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _parse_response_rows(content: bytes, filename: Optional[str]) -> List[Dict]:
    """Parse uploaded responses (xlsx or CSV) into [{task_ref, desire_rating, respondent_hash?}]."""
    name = (filename or "").lower()
    records: List[Dict] = []
    if name.endswith(".xlsx"):
        wb = load_workbook(io.BytesIO(content), read_only=True)
        ws = wb.active
        header = None
        for row in ws.iter_rows(values_only=True):
            if header is None:
                header = [str(c).strip().split(" ")[0] if c else "" for c in row]
                continue
            records.append({header[i]: row[i] for i in range(len(header)) if i < len(row)})
    else:
        text = content.decode("utf-8-sig")
        for rec in csv.DictReader(io.StringIO(text)):
            records.append({(k or "").strip(): v for k, v in rec.items()})
    return records


def _to_rating(value) -> Optional[int]:
    try:
        rating = int(float(value))
    except (TypeError, ValueError):
        return None
    return rating if 1 <= rating <= 5 else None


async def import_responses(
    session: AsyncSession, engagement_id: str, dataset_id: str, content: bytes,
    filename: Optional[str] = None,
) -> Dict:
    """Persist pulse responses and recompute desire_score_local. desire_score_us is never touched."""
    records = _parse_response_rows(content, filename)
    stored = 0
    for rec in records:
        ref = rec.get("task_ref")
        rating = _to_rating(rec.get("desire_rating"))
        if not ref or rating is None:
            continue
        session.add(DesirePulseResponse(
            engagement_id=engagement_id, task_ref=str(ref).strip(),
            respondent_hash=(str(rec.get("respondent_hash")).strip() if rec.get("respondent_hash") else None),
            desire_rating=rating,
        ))
        stored += 1
    await session.flush()

    updated = await recompute_local_desire(session, engagement_id, dataset_id)
    return {"responses_stored": stored, "scores_updated": updated}


async def _dataset_tasks_with_scores(session: AsyncSession, dataset_id: str):
    tasks = list(await session.scalars(
        select(Task).join(Position, Task.position_id == Position.id)
        .where(Position.dataset_id == dataset_id).order_by(Task.id)
    ))
    scores = {
        s.task_id: s
        for s in await session.scalars(
            select(TaskAIScore).where(TaskAIScore.task_id.in_([t.id for t in tasks]))
        )
    }
    return tasks, scores


async def export_desirability_template(session: AsyncSession, dataset_id: str,
                                       only_unscored: bool = True) -> bytes:
    """CSV (task_ref=task id, task_text, desire_rating) for tasks LACKING a valid benchmark, so a
    consultant can manually set the AI opportunity. `task_ref` is the extracted task's id — download
    this template rather than hand-keying, so it aligns with the dataset automatically (tasks are
    extracted from the org CSV's Work Activities, not the raw structure rows)."""
    tasks, scores = await _dataset_tasks_with_scores(session, dataset_id)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(INSTRUMENT_HEADERS)
    for t in tasks:
        s = scores.get(t.id)
        if only_unscored and s is not None and s.source in _BENCHMARK_SOURCES:
            continue  # already has a real/curated benchmark — no manual scoring needed
        w.writerow([t.id, t.task_text, ""])
    return out.getvalue().encode("utf-8")


async def apply_local_desirability(session: AsyncSession, dataset_id: str, content: bytes,
                                   filename: Optional[str] = None) -> Dict:
    """Apply a filled local-desirability CSV (keyed by task id). For tasks WITHOUT a real benchmark,
    set a consultant-approved AI-opportunity derived from the rating (1=keep human → H5/L0,
    5=automate → H1/L3) so it becomes client-ready; for benchmarked tasks, only the local desire is
    updated (the authoritative benchmark is never overwritten). desire_score_us is never touched."""
    from .task_intelligence_service import apply_manual_opportunity

    records = _parse_response_rows(content, filename)
    tasks, scores = await _dataset_tasks_with_scores(session, dataset_id)
    task_ids = {t.id for t in tasks}
    applied = desire_only = skipped = 0
    for rec in records:
        # Normalise headers to their first word so "desire_rating (1=keep human .. 5=automate)" works
        # from CSV too (the xlsx parser already splits; CSV keeps the full header).
        norm = {(k or "").strip().split(" ")[0]: v for k, v in rec.items()}
        ref = (str(norm.get("task_ref")).strip() if norm.get("task_ref") is not None else "")
        rating = _to_rating(norm.get("desire_rating"))
        if not ref or rating is None or ref not in task_ids:
            skipped += 1
            continue
        score = scores.get(ref)
        if score is None:  # task was never AI-scored — create a consultant row
            score = TaskAIScore(task_id=ref, source="consultant-approved", review_state="approved")
            session.add(score)
            scores[ref] = score
        if score.source in _PROTECTED_SOURCES:
            score.desire_score_local = round((rating - 1) / 4, 4)  # only local desire (keep benchmark)
            desire_only += 1
            continue
        apply_manual_opportunity(score, rating)  # consultant-approved, client-ready
        applied += 1
    await session.flush()
    return {"applied": applied, "desire_only": desire_only, "skipped": skipped}


async def recompute_local_desire(session: AsyncSession, engagement_id: str, dataset_id: str) -> int:
    """Average pulse ratings per task_ref → desire_score_local on the matching task_ai_scores.

    Mapping 1..5 → 0..1 via (mean-1)/4. Updates only `desire_score_local` (US score untouched).
    """
    responses = list(
        await session.scalars(
            select(DesirePulseResponse).where(DesirePulseResponse.engagement_id == engagement_id)
        )
    )
    if not responses:
        return 0
    sums: Dict[str, List[int]] = {}
    for r in responses:
        if r.task_ref and r.desire_rating is not None:
            sums.setdefault(r.task_ref, []).append(r.desire_rating)
    local_by_ref = {ref: (sum(v) / len(v) - 1) / 4 for ref, v in sums.items()}

    # task_ref -> taxonomy_task.id -> benchmarks -> task ids -> ai_scores
    taxo = {t.task_ref: t.id for t in await session.scalars(select(TaxonomyTask))}
    task_ids = list(
        await session.scalars(
            select(Task.id).join(Position, Task.position_id == Position.id).where(
                Position.dataset_id == dataset_id
            )
        )
    )
    benchmarks = list(
        await session.scalars(select(TaskBenchmark).where(TaskBenchmark.task_id.in_(task_ids)))
    )
    scores = {
        s.task_id: s
        for s in await session.scalars(select(TaskAIScore).where(TaskAIScore.task_id.in_(task_ids)))
    }

    updated = 0
    for b in benchmarks:
        if not b.matched_taxonomy_task_id:
            continue
        ref = next((r for r, tid in taxo.items() if tid == b.matched_taxonomy_task_id), None)
        if ref is None or ref not in local_by_ref:
            continue
        score = scores.get(b.task_id)
        if score is not None:
            score.desire_score_local = round(local_by_ref[ref], 4)  # US score left intact
            updated += 1
    await session.flush()
    return updated
