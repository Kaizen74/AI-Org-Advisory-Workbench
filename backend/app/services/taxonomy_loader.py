"""Idempotent taxonomy seed loader (Phase 2, Build Spec B0/B2/M2).

Loads `taxonomy_seed.starter.json` into the reference layer. Upserts by natural keys so repeated
runs do not duplicate rows: `code` (sources), `task_ref` (tasks), `onet_task_code` (overlay), and
(`from_task_ref`, `to_task_code`) (crosswalk).

Binding mappings (Build Spec B0/A4):
  * seed `desire_score` → `desire_score_us` (US preference). `desire_score_local` starts NULL and is
    populated only by the M2 pulse instrument — never overwritten here.
  * `has_level` and `capability_score` are loaded independently (never collapsed).
  * Any crosswalk with `confidence < 0.70` defaults to `review_state = "unreviewed"` (it enters the
    M3 validation queue) — INCLUDING curated seed rows (the starter ships one at 0.40). Higher-
    confidence curated rows load as `"approved"` reference data.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import TaskAIOverlay, TaxonomyCrosswalk, TaxonomySource, TaxonomyTask

DEFAULT_SEED_PATH = (
    Path(__file__).resolve().parents[1] / "resources" / "taxonomies" / "taxonomy_seed.starter.json"
)
# Optional curated WORKBank overlay (authoritative AI-potential layer). Build it from the WORKBank
# dataset with scripts/build_workbank_overlay.py and commit a curated subset here. When present it
# upserts real has_level/capability/desire keyed by O*NET code, so benchmarking relies far less on
# Claude inference. Absent => seed-only (unchanged behaviour).
WORKBANK_OVERLAY_PATH = (
    Path(__file__).resolve().parents[1] / "resources" / "taxonomies" / "workbank_overlay.curated.json"
)

REVIEW_CONFIDENCE_THRESHOLD = 0.70


async def _upsert_overlay(session: AsyncSession, o: dict, default_source: Optional[str] = None) -> None:
    """Upsert one AI overlay row by its natural key (onet_task_code). Accepts the seed's `desire_score`
    or an explicit `desire_score_us`. `has_level` and `capability_score` stay independent (A4)."""
    row = await _get(session, TaskAIOverlay, onet_task_code=o["onet_task_code"])
    if row is None:
        row = TaskAIOverlay(onet_task_code=o["onet_task_code"])
        session.add(row)
    row.onet_task_text = o.get("onet_task_text")
    row.occupation = o.get("occupation")
    row.has_level = o.get("has_level")  # independent of capability (A4)
    row.desire_score_us = o.get("desire_score_us", o.get("desire_score"))  # US preference only
    # desire_score_local intentionally untouched (NULL until the pulse instrument runs)
    row.capability_score = o.get("capability_score")
    row.zone = o.get("zone")
    row.source = o.get("source", default_source)
    await session.flush()


async def _get(session: AsyncSession, model, **filters):
    stmt = select(model)
    for key, value in filters.items():
        stmt = stmt.where(getattr(model, key) == value)
    return await session.scalar(stmt)


async def load_taxonomies(session: AsyncSession, path: Optional[Path] = None) -> Dict[str, int]:
    """Upsert the seed into the reference layer. Returns counts of rows processed. Idempotent."""
    data = json.loads(Path(path or DEFAULT_SEED_PATH).read_text(encoding="utf-8"))

    counts = {"sources": 0, "tasks": 0, "overlays": 0, "crosswalks": 0}

    # ── Sources (natural key: code) ─────────────────────────────────────────
    code_to_source_id: Dict[str, str] = {}
    for s in data.get("taxonomy_sources", []):
        row = await _get(session, TaxonomySource, code=s["code"])
        if row is None:
            row = TaxonomySource(code=s["code"])
            session.add(row)
        row.name = s.get("name", row.name or s["code"])
        row.region = s.get("region")
        row.version = s.get("version")
        row.is_default = bool(s.get("is_default", False))
        row.license_note = s.get("license_note")
        await session.flush()
        code_to_source_id[s["code"]] = row.id
        counts["sources"] += 1

    # ── Tasks (natural key: task_ref) ───────────────────────────────────────
    ref_to_task_id: Dict[str, str] = {}
    for t in data.get("taxonomy_tasks", []):
        row = await _get(session, TaxonomyTask, task_ref=t["task_ref"])
        if row is None:
            row = TaxonomyTask(task_ref=t["task_ref"], task_text=t["task_text"])
            session.add(row)
        row.source_id = code_to_source_id.get(t["source_code"])
        row.role_label = t.get("role_label")
        row.track = t.get("track")
        row.function = t.get("function")
        row.task_text = t["task_text"]
        row.task_code = t.get("task_code")
        row.skills = t.get("skills")
        await session.flush()
        ref_to_task_id[t["task_ref"]] = row.id
        counts["tasks"] += 1

    # ── Overlay (natural key: onet_task_code) — desire_score → desire_score_us ──
    for o in data.get("task_ai_overlay", []):
        await _upsert_overlay(session, o)
        counts["overlays"] += 1

    # ── Curated WORKBank overlay (optional, additive) — the authoritative AI-potential layer ──
    if WORKBANK_OVERLAY_PATH.exists():
        wb = json.loads(WORKBANK_OVERLAY_PATH.read_text(encoding="utf-8"))
        wb_rows = wb.get("task_ai_overlay", wb) if isinstance(wb, dict) else wb
        for o in wb_rows:
            await _upsert_overlay(session, o, default_source="WORKBank")
            counts["overlays"] += 1

    # ── Crosswalk (natural key: from_task_ref + to_task_code) ───────────────
    for c in data.get("taxonomy_crosswalk", []):
        from_task_id = ref_to_task_id.get(c.get("from_task_ref"))
        from_source_id = None
        if from_task_id is not None:
            ft = await session.get(TaxonomyTask, from_task_id)
            from_source_id = ft.source_id if ft else None

        row = await _get(
            session,
            TaxonomyCrosswalk,
            from_task_id=from_task_id,
            to_task_code=c["to_task_code"],
        )
        if row is None:
            row = TaxonomyCrosswalk(
                from_task_id=from_task_id, to_task_code=c["to_task_code"]
            )
            session.add(row)
        row.from_source_id = from_source_id
        row.to_source_code = c["to_source_code"]
        row.confidence = c.get("confidence")
        row.method = c.get("method", "CURATED")
        row.review_state = _review_state_for(row.confidence)
        row.note = c.get("note")
        await session.flush()
        counts["crosswalks"] += 1

    return counts


def _review_state_for(confidence: Optional[float]) -> str:
    """Confidence-triggered routing: <0.70 (or missing) -> unreviewed; else approved (B0)."""
    if confidence is None or confidence < REVIEW_CONFIDENCE_THRESHOLD:
        return "unreviewed"
    return "approved"
