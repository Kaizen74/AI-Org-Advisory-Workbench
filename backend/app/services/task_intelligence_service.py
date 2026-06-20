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
from ..models import (
    Position,
    Task,
    TaskAIOverlay,
    TaskAIScore,
    TaskBenchmark,
    TaxonomyCrosswalk,
    TaxonomyTask,
)
from ._json_utils import parse_ai_json
from .claude_service import claude_service

DEFAULT_BATCH_SIZE = 40
REVIEW_CONFIDENCE_THRESHOLD = 0.70


def _review_state_for(confidence: Optional[float]) -> str:
    """Confidence-triggered routing: <0.70 (or missing) -> unreviewed, else approved (B0)."""
    if confidence is None or confidence < REVIEW_CONFIDENCE_THRESHOLD:
        return "unreviewed"
    return "approved"

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


async def _load_dataset_tasks(session: AsyncSession, dataset_id: str) -> List[Task]:
    """All tasks for a dataset (joined via positions), ordered by id for determinism."""
    rows = await session.scalars(
        select(Task)
        .join(Position, Task.position_id == Position.id)
        .where(Position.dataset_id == dataset_id)
        .order_by(Task.id)
    )
    return list(rows)


# ── Benchmark (task -> SFw/O*NET) ────────────────────────────────────────────
async def _benchmark_grounding(session: AsyncSession) -> List[Dict]:
    """Compact reference grounding: taxonomy tasks + their crosswalked O*NET code (if any)."""
    tasks = list(await session.scalars(select(TaxonomyTask)))
    crosswalks = list(await session.scalars(select(TaxonomyCrosswalk)))
    onet_by_task_id = {c.from_task_id: c.to_task_code for c in crosswalks if c.from_task_id}
    return [
        {
            "task_ref": t.task_ref,
            "task_text": t.task_text,
            "source_code": None,  # filled from source if needed; not required by the model
            "onet_task_code": onet_by_task_id.get(t.id),
        }
        for t in tasks
    ]


def _build_benchmark_prompt(batch: List[Task], grounding: List[Dict]) -> str:
    payload = [{"task_id": t.id, "task_text": t.task_text} for t in batch]
    return (
        "Benchmark each task against the reference taxonomy (SFw primary, O*NET bridge). For each "
        "task return STRICT JSON {\"benchmarks\": [{\"task_id\": \"...\", \"status\": "
        "\"MATCHED|MISSING|EXTRA\", \"taxonomy_source_code\": \"...\", \"matched_task_ref\": "
        "\"...|null\", \"onet_task_code\": \"...|null\", \"source\": \"SFw|ONET|model-inferred\", "
        "\"confidence\": 0.0}]}. Cite the grounding row when matched.\n\nGROUNDING:\n```json\n"
        + json.dumps(grounding, ensure_ascii=False)
        + "\n```\n\nTASKS:\n```json\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n```"
    )


def _benchmark_batch(batch: List[Task], grounding: List[Dict]) -> List[Dict]:
    raw = claude_service.complete(
        model=settings.MODEL_EXTRACT,
        messages=[{"role": "user", "content": _build_benchmark_prompt(batch, grounding)}],
    )
    return parse_ai_json(raw).get("benchmarks", [])


async def benchmark_tasks(
    session: AsyncSession, dataset_id: str, batch_size: int = DEFAULT_BATCH_SIZE
) -> Dict:
    """Benchmark a dataset's extracted tasks against the taxonomy. Idempotent; provenance-tagged."""
    tasks = await _load_dataset_tasks(session, dataset_id)
    if not tasks:
        return {"dataset_id": dataset_id, "tasks": 0, "benchmarks_created": 0,
                "matched": 0, "missing": 0, "caveats": STANDARD_CAVEATS}

    task_ids = [t.id for t in tasks]
    await session.execute(delete(TaskBenchmark).where(TaskBenchmark.task_id.in_(task_ids)))

    grounding = await _benchmark_grounding(session)
    ref_to_id = {t.task_ref: t.id for t in await session.scalars(select(TaxonomyTask))}

    created = matched = missing = 0
    for i in range(0, len(tasks), batch_size):
        batch = tasks[i : i + batch_size]
        valid_ids = {t.id for t in batch}
        for b in _benchmark_batch(batch, grounding):
            tid = b.get("task_id")
            if tid not in valid_ids:
                continue
            status = b.get("status", "MISSING")
            confidence = b.get("confidence")
            session.add(
                TaskBenchmark(
                    task_id=tid,
                    taxonomy_source_code=b.get("taxonomy_source_code"),
                    status=status,
                    matched_taxonomy_task_id=ref_to_id.get(b.get("matched_task_ref")),
                    onet_task_code=b.get("onet_task_code"),
                    source=b.get("source", "model-inferred"),
                    confidence=confidence,
                    review_state=_review_state_for(confidence),
                )
            )
            created += 1
            matched += 1 if status == "MATCHED" else 0
            missing += 1 if status == "MISSING" else 0
    await session.flush()
    return {"dataset_id": dataset_id, "tasks": len(tasks), "benchmarks_created": created,
            "matched": matched, "missing": missing, "caveats": STANDARD_CAVEATS}


# ── Human Agency Scale (WORKBank) — the headline AI-potential band (D17) ─────
# WORKBank HAS, surfaced as H0–H5. Lower H = more AI-amenable (AI does more of the task); higher H =
# more human agency required. H0 is our extension: no software-agent overlay (assess as robotics/GSE).
# Values are ILLUSTRATIVE per the WORKBank guardrail — verify against the source before client use.
HUMAN_AGENCY_SCALE: Dict[str, str] = {
    "H0": "No software-agent overlay — either a physical/handling task (robotics/GSE lever) or not yet matched to a relevant benchmark. Not an AI-agent opportunity as-is.",
    "H1": "AI agent can perform the task with minimal or no human involvement.",
    "H2": "AI performs most of the task; light human review.",
    "H3": "Human–AI equal partnership.",
    "H4": "Human leads the task; AI assists.",
    "H5": "Human performs the task; AI adds little.",
}


def human_agency_band(has_level: Optional[int]) -> str:
    """Map a WORKBank HAS level to its H0–H5 band. None (no overlay) → H0; clamped to H1–H5."""
    if has_level is None:
        return "H0"
    lvl = int(has_level)
    if lvl < 1:
        return "H0"
    return f"H{min(lvl, 5)}"


# ── AI opportunity (HAS/zone/desire/capability/L0-L3 via logical O*NET overlay join) ──
def derive_ai_level(capability: Optional[float], has_level: Optional[int]) -> str:
    """Deterministic L0-L3 from capability + human-agency (heuristic; caveated). Higher capability
    and lower required human agency -> higher transformation level."""
    if capability is None:
        return "L0"
    if capability >= 0.75 and (has_level or 5) <= 2:
        return "L3"
    if capability >= 0.60:
        return "L2"
    if capability >= 0.40:
        return "L1"
    return "L0"


async def score_ai_opportunity(session: AsyncSession, dataset_id: str) -> Dict:
    """Attach HAS/zone/desire/capability + L0-L3 to each benchmarked task via the overlay.

    The overlay is reached LOGICALLY by `onet_task_code` (D1 — no FK). Tasks with no overlay (e.g.
    physical ramp handling) get NO software-agent overlay: they are tagged `model-inferred` and
    surfaced as a robotics/GSE lever (A4). Every score is `unreviewed` (WORKBank values are
    illustrative) until consultant approval (P3). Idempotent.
    """
    tasks = await _load_dataset_tasks(session, dataset_id)
    if not tasks:
        return {"dataset_id": dataset_id, "scored": 0, "with_overlay": 0,
                "robotics_levers": 0, "level_breakdown": {}, "caveats": STANDARD_CAVEATS}

    task_ids = [t.id for t in tasks]
    await session.execute(delete(TaskAIScore).where(TaskAIScore.task_id.in_(task_ids)))

    benchmarks = {
        b.task_id: b
        for b in await session.scalars(
            select(TaskBenchmark).where(TaskBenchmark.task_id.in_(task_ids))
        )
    }
    overlays = {o.onet_task_code: o for o in await session.scalars(select(TaskAIOverlay))}

    with_overlay = robotics = unclassified = 0
    level_breakdown: Dict[str, int] = {}
    for task in tasks:
        bench = benchmarks.get(task.id)
        onet = bench.onet_task_code if bench else None
        overlay = overlays.get(onet) if onet else None

        if overlay is not None:
            with_overlay += 1
            level = derive_ai_level(overlay.capability_score, overlay.has_level)
            score = TaskAIScore(
                task_id=task.id,
                has_level=overlay.has_level,
                zone=overlay.zone,
                desire_score_us=overlay.desire_score_us,
                desire_score_local=overlay.desire_score_local,
                capability_score=overlay.capability_score,
                ai_opportunity_level=level,
                rationale=(
                    f"Joined to O*NET {onet} overlay (WORKBank, illustrative). "
                    f"capability={overlay.capability_score}, HAS={overlay.has_level}."
                ),
                source="WORKBank",
                confidence=bench.confidence if bench else None,
                review_state="unreviewed",
            )
        elif onet is not None:
            # Benchmark-matched to an O*NET code that has NO software-agent overlay → likely a
            # physical/handling task: surface as a robotics/GSE lever (A4).
            robotics += 1
            level = "L0"
            score = TaskAIScore(
                task_id=task.id,
                has_level=None,
                zone="ROBOTICS_GSE_LEVER",
                ai_opportunity_level=level,
                rationale=(
                    f"Matched O*NET {onet} but no software-agent overlay (likely physical/handling "
                    "task). Surface as a robotics/GSE automation lever, not a software-agent opportunity."
                ),
                source="model-inferred",
                confidence=0.3,
                review_state="unreviewed",
            )
        else:
            # No benchmark match at all (e.g. the loaded taxonomy covers a different sector than this
            # client). This is NOT a robotics lever — it is simply unclassified until a relevant
            # benchmark is loaded/curated. Mislabeling knowledge work as robotics is misleading.
            unclassified += 1
            level = "L0"
            score = TaskAIScore(
                task_id=task.id,
                has_level=None,
                zone="NO_BENCHMARK_MATCH",
                ai_opportunity_level=level,
                rationale=(
                    "No matching benchmark in the loaded taxonomy (it may cover a different sector). "
                    "Load or curate a relevant benchmark to score this task — not a robotics/GSE lever."
                ),
                source="model-inferred",
                confidence=0.0,
                review_state="unreviewed",
            )
        level_breakdown[level] = level_breakdown.get(level, 0) + 1
        session.add(score)
    await session.flush()

    return {
        "dataset_id": dataset_id,
        "scored": len(tasks),
        "with_overlay": with_overlay,
        "robotics_levers": robotics,
        "unclassified": unclassified,
        "level_breakdown": level_breakdown,
        "caveats": STANDARD_CAVEATS,
    }


# ── Rollup (aggregate AI scores up the org graph) ────────────────────────────
# ── Robust AI benchmarking for unmatched tasks (Claude grounded in the WORKBank HAS rubric) ──
# When the curated seed/overlay has no match (e.g. a different sector than the illustrative seed), we
# do NOT leave the task unscored. We use Claude — the app's sanctioned inference engine — grounded in
# the WORKBank Human Agency Scale rubric (and its knowledge of O*NET/ESCO/SFw) to infer the task's
# AI potential. The curated overlay always takes precedence; these inferred scores are tagged
# `model-inferred` + `unreviewed`, so they are export-blocked until a consultant approves them (M6).
_HAS_INFERENCE_MARKER = "HUMAN AGENCY SCALE BENCHMARK"


def _build_inference_prompt(payload: List[Dict]) -> str:
    return (
        "You are benchmarking work TASKS for AI-automation potential using the WORKBank "
        "Human Agency Scale (HAS) and your knowledge of O*NET / ESCO / SkillsFuture task taxonomies.\n"
        f"{_HAS_INFERENCE_MARKER}\n"
        "For EACH task assign:\n"
        "- has_level: integer 1-5 — H1 = AI can perform with minimal/no human; H2 = AI does most, "
        "light human review; H3 = equal human-AI partnership; H4 = human leads, AI assists; "
        "H5 = human-led, AI adds little. Use null ONLY for a physical/handling task with no "
        "software-agent overlay.\n"
        "- capability_score: 0.0-1.0 (current AI capability to perform the task).\n"
        "- zone: GREEN_LIGHT (strong agentic fit), RED_LIGHT (keep human-led), or "
        "ROBOTICS_GSE_LEVER (physical → robotics, not a software agent).\n"
        "- confidence: 0.0-1.0.\n- rationale: one short sentence.\n"
        "Return STRICT JSON: {\"scores\":[{\"task_id\":\"..\",\"has_level\":2,"
        "\"capability_score\":0.7,\"zone\":\"GREEN_LIGHT\",\"confidence\":0.6,\"rationale\":\"..\"}]}."
        "\n\nTASKS:\n```json\n" + json.dumps(payload) + "\n```"
    )


_INFERRED_TAG = "[WORKBank HAS inference]"


async def infer_unmatched_potential(session: AsyncSession, dataset_id: str) -> Dict:
    """Robustly score the tasks the curated benchmark could not resolve — both `NO_BENCHMARK_MATCH`
    (no match at all) and the auto-assigned `ROBOTICS_GSE_LEVER` rows (matched an O*NET code with no
    overlay, heuristically 'physical') — by asking Claude to apply the WORKBank HAS rubric. Claude
    keeps genuinely physical tasks as a robotics/GSE lever (has_level null) and re-bands misclassified
    knowledge work (H1-H5). Updates rows in place; tags the rationale so re-runs are idempotent. Does
    nothing if there are no candidates. (Curated/WORKBank-overlay rows, source='WORKBank', are never
    touched — the curated layer always wins.)"""
    tasks = await _load_dataset_tasks(session, dataset_id)
    by_task = {t.id: t for t in tasks}
    if not tasks:
        return {"dataset_id": dataset_id, "candidates": 0, "updated": 0, "caveats": STANDARD_CAVEATS}

    rows = await session.scalars(
        select(TaskAIScore).where(
            TaskAIScore.task_id.in_(list(by_task)),
            TaskAIScore.source == "model-inferred",
            TaskAIScore.review_state == "unreviewed",
            TaskAIScore.zone.in_(["NO_BENCHMARK_MATCH", "ROBOTICS_GSE_LEVER"]),
        )
    )
    # Skip rows already rubric-inferred (idempotency) — keeps confirmed robotics levers stable.
    scores = {s.task_id: s for s in rows if not (s.rationale and _INFERRED_TAG in s.rationale)}
    if not scores:
        return {"dataset_id": dataset_id, "candidates": 0, "updated": 0, "caveats": STANDARD_CAVEATS}

    payload = [{"task_id": tid, "task_text": by_task[tid].task_text} for tid in scores]
    raw = claude_service.complete(
        model=settings.MODEL_SYNTH, messages=[{"role": "user", "content": _build_inference_prompt(payload)}]
    )
    results = parse_ai_json(raw).get("scores", [])

    updated = 0
    for item in results:
        s = scores.get(item.get("task_id"))
        if s is None:
            continue
        has_level = item.get("has_level")
        cap = item.get("capability_score")
        zone = item.get("zone") or "RED_LIGHT"
        if zone not in ("GREEN_LIGHT", "RED_LIGHT", "ROBOTICS_GSE_LEVER"):
            zone = "RED_LIGHT"
        if zone == "ROBOTICS_GSE_LEVER":
            has_level = None  # physical lever → off the software-agent scale
        s.has_level = has_level
        s.capability_score = cap
        s.zone = zone
        s.ai_opportunity_level = derive_ai_level(cap, has_level)
        s.confidence = item.get("confidence")
        s.rationale = (
            (item.get("rationale") or "AI-inferred via the WORKBank Human Agency Scale rubric.")
            + f" {_INFERRED_TAG} — no curated benchmark match; verify before client use."
        )
        s.source = "model-inferred"
        s.review_state = "unreviewed"  # export-blocked until consultant approval (M6)
        updated += 1
    await session.flush()
    return {"dataset_id": dataset_id, "candidates": len(scores), "updated": updated,
            "caveats": STANDARD_CAVEATS}


def _blank_bucket() -> Dict:
    return {"tasks": 0, "levels": {}, "zones": {}, "has": {}, "agency": {},
            "with_overlay": 0, "robotics_levers": 0}


def _accumulate(bucket: Dict, score: TaskAIScore) -> None:
    bucket["tasks"] += 1
    lvl = score.ai_opportunity_level or "L0"
    bucket["levels"][lvl] = bucket["levels"].get(lvl, 0) + 1
    if score.zone:
        bucket["zones"][score.zone] = bucket["zones"].get(score.zone, 0) + 1
    if score.has_level is not None:
        key = str(score.has_level)
        bucket["has"][key] = bucket["has"].get(key, 0) + 1
    # Headline AI-potential band (H0–H5), counting H0 for no-overlay tasks (D17).
    band = human_agency_band(score.has_level)
    bucket["agency"][band] = bucket["agency"].get(band, 0) + 1
    if score.source == "WORKBank":
        bucket["with_overlay"] += 1
    if score.zone == "ROBOTICS_GSE_LEVER":
        bucket["robotics_levers"] += 1


async def rollup(session: AsyncSession, dataset_id: str) -> Dict:
    """Aggregate AI-opportunity scores by department and by layer, plus an overall bucket."""
    tasks = await _load_dataset_tasks(session, dataset_id)
    task_ids = [t.id for t in tasks]
    positions = {
        p.id: p
        for p in await session.scalars(select(Position).where(Position.dataset_id == dataset_id))
    }
    scores = {
        s.task_id: s
        for s in await session.scalars(
            select(TaskAIScore).where(TaskAIScore.task_id.in_(task_ids))
        )
    }

    overall = _blank_bucket()
    by_department: Dict[str, Dict] = {}
    by_layer: Dict[str, Dict] = {}
    for task in tasks:
        score = scores.get(task.id)
        if score is None:
            continue
        pos = positions.get(task.position_id)
        dept = (pos.department if pos else None) or "Unknown"
        layer = str(pos.level if pos and pos.level is not None else 0)
        _accumulate(overall, score)
        _accumulate(by_department.setdefault(dept, _blank_bucket()), score)
        _accumulate(by_layer.setdefault(layer, _blank_bucket()), score)

    return {
        "dataset_id": dataset_id,
        "overall": overall,
        "by_department": by_department,
        "by_layer": by_layer,
        "human_agency_scale": HUMAN_AGENCY_SCALE,
        "caveats": STANDARD_CAVEATS,
    }


async def list_tasks(session: AsyncSession, dataset_id: str) -> List[Dict]:
    """List a dataset's extracted tasks (id + text + position) for mapping/UI. No AI."""
    tasks = await _load_dataset_tasks(session, dataset_id)
    positions = {
        p.id: p
        for p in await session.scalars(select(Position).where(Position.dataset_id == dataset_id))
    }
    return [
        {
            "id": t.id,
            "task_text": t.task_text,
            "employee_key": positions[t.position_id].employee_key if t.position_id in positions else None,
        }
        for t in tasks
    ]


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
