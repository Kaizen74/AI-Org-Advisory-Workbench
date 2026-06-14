"""Deliverable Factory service (Phase 6, Build Spec M6/B2).

Generates branded pptx/docx/xlsx deliverables from PERSISTED data only (no AI calls, no API key
needed). Two binding rules (A4/M6) are enforced centrally:
  * **Export-block:** unreviewed model-inferred content is excluded from client content (via
    `validation_service.is_client_ready`); the count excluded is disclosed.
  * **Provenance disclosure:** every deliverable carries an auto-generated provenance summary
    (% of content by source tag) + caveats.

Files are written to `backend/output/` (gitignored). The `deliverables` row stores the path +
provenance summary.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Deliverable,
    MetricValue,
    Position,
    Scenario,
    Task,
    TaskAIScore,
)
from . import scenario_service, transition_service
from . import validation_service as vs
from .deliverable_builders import (
    doc_section,
    metric_slide,
    new_document,
    new_presentation,
    provenance_slide,
    save_docx,
    save_pptx,
    section_slide,
    table_slide,
    title_slide,
)
from .deliverable_theme import get_theme
from .task_intelligence_service import STANDARD_CAVEATS

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output"

_EXT = {
    "PPTX_DIAGNOSTIC": "pptx", "PPTX_SCENARIOS": "pptx", "PPTX_AI_ROADMAP": "pptx",
    "DOCX_TOM": "docx", "XLSX_METRICS": "xlsx", "XLSX_TRANSITION": "xlsx",
}

DELIVERABLE_TYPES = list(_EXT)


# ── Provenance summary (transparency as a feature, M6) ───────────────────────
async def provenance_summary(session: AsyncSession, dataset_id: Optional[str]) -> Dict:
    """% of AI content by source tag + how many unreviewed model-inferred rows were export-blocked."""
    summary = {"by_source": {}, "total": 0, "client_ready": 0,
               "excluded_unreviewed_model_inferred": 0, "caveats": list(STANDARD_CAVEATS)}
    if not dataset_id:
        return summary
    task_ids = list(await session.scalars(
        select(Task.id).join(Position, Task.position_id == Position.id).where(
            Position.dataset_id == dataset_id
        )
    ))
    if not task_ids:
        return summary
    scores = list(await session.scalars(
        select(TaskAIScore).where(TaskAIScore.task_id.in_(task_ids))
    ))
    by_source: Dict[str, int] = {}
    excluded = 0
    ready = 0
    for s in scores:
        by_source[s.source or "unknown"] = by_source.get(s.source or "unknown", 0) + 1
        if vs.is_client_ready(s.source, s.review_state):
            ready += 1
        elif s.source == "model-inferred" and s.review_state == "unreviewed":
            excluded += 1
    summary.update({"by_source": by_source, "total": len(scores), "client_ready": ready,
                    "excluded_unreviewed_model_inferred": excluded})
    return summary


async def _dataset_for_scenario(session: AsyncSession, scenario_id: str) -> Optional[str]:
    scenario = await session.get(Scenario, scenario_id)
    return scenario.dataset_id if scenario else None


async def _metric_map(session: AsyncSession, dataset_id: str) -> Dict[str, float]:
    rows = await session.scalars(select(MetricValue).where(MetricValue.dataset_id == dataset_id))
    return {r.metric_code: r.value for r in rows}


# ── Generators (return bytes) ────────────────────────────────────────────────
async def _gen_pptx_diagnostic(session, theme, dataset_id, **_) -> bytes:
    metrics = await _metric_map(session, dataset_id)
    prs = new_presentation()
    title_slide(prs, theme, "Organisation Diagnostic", "Current-state structural read-out")
    stats = [
        ("Employees", f"{int(metrics.get('total_employees', 0))}"),
        ("Managers", f"{int(metrics.get('total_managers', 0))}"),
        ("Manager ratio", f"{metrics.get('manager_ratio_pct', 0)}%"),
        ("Avg span", f"{metrics.get('average_span', 0)}"),
        ("Layers", f"{int(metrics.get('organizational_layers', 0))}"),
        ("Total cost", f"${int(metrics.get('total_cost', 0)):,}"),
    ]
    metric_slide(prs, theme, "Headline metrics", stats)
    provenance_slide(prs, theme, await provenance_summary(session, dataset_id))
    return save_pptx(prs)


async def _gen_pptx_scenarios(session, theme, engagement_id, dataset_id=None, **_) -> bytes:
    scenarios = await scenario_service.list_scenarios(session, engagement_id)
    deltas = []
    for s in scenarios[:3]:
        d = await scenario_service.compute_delta(session, s.id)
        if d:
            deltas.append(d)
    prs = new_presentation()
    title_slide(prs, theme, "Scenario Comparison", "Future-state design options vs baseline")
    if deltas:
        headers = ["Metric"] + [d["name"] for d in deltas]
        codes = [("total_employees", "Employees"), ("total_cost", "Total cost"),
                 ("organizational_layers", "Layers"), ("manager_ratio_pct", "Manager %")]
        rows = [[label] + [f"{d['delta'].get(code, 0):+,}" for d in deltas] for code, label in codes]
        table_slide(prs, theme, "Δ vs baseline", headers, rows)
    else:
        section_slide(prs, theme, "Scenario Comparison", ["No scenarios defined yet."])
    provenance_slide(prs, theme, await provenance_summary(session, dataset_id))
    return save_pptx(prs)


async def _gen_pptx_ai_roadmap(session, theme, dataset_id, **_) -> bytes:
    # Client-ready scores only (export-block): exclude unreviewed model-inferred.
    ready = await vs.client_ready_ai_scores(session, dataset_id)
    levels: Dict[str, int] = {}
    for s in ready:
        lvl = s.ai_opportunity_level or "L0"
        levels[lvl] = levels.get(lvl, 0) + 1
    prs = new_presentation()
    title_slide(prs, theme, "AI Transformation Roadmap", "Task-level AI opportunity (client-ready)")
    rows = [[lvl, str(levels.get(lvl, 0))] for lvl in ["L0", "L1", "L2", "L3"]]
    table_slide(prs, theme, "AI opportunity levels (reviewed content only)", ["Level", "Tasks"], rows)
    provenance_slide(prs, theme, await provenance_summary(session, dataset_id))
    return save_pptx(prs)


async def _gen_docx_tom(session, theme, dataset_id, **_) -> bytes:
    metrics = await _metric_map(session, dataset_id)
    prov = await provenance_summary(session, dataset_id)
    doc = new_document(theme, "Target Operating Model", "Narrative report")
    doc_section(doc, "Current state", [
        f"The organisation comprises {int(metrics.get('total_employees', 0))} positions across "
        f"{int(metrics.get('organizational_layers', 0))} layers, with a manager ratio of "
        f"{metrics.get('manager_ratio_pct', 0)}% and an average span of "
        f"{metrics.get('average_span', 0)}. Total annual people cost is approximately "
        f"${int(metrics.get('total_cost', 0)):,}.",
    ])
    doc_section(doc, "Provenance & disclosure", [
        f"Client-ready AI items: {prov['client_ready']} of {prov['total']}.",
        f"Excluded (unreviewed model-inferred): {prov['excluded_unreviewed_model_inferred']}.",
    ])
    doc_section(doc, "Caveats", list(prov["caveats"]))
    return save_docx(doc)


async def _gen_xlsx_metrics(session, theme, dataset_id, **_) -> bytes:
    rows = await session.scalars(select(MetricValue).where(MetricValue.dataset_id == dataset_id))
    wb = Workbook()
    ws = wb.active
    ws.title = "Metrics"
    ws.append(["metric_code", "scope", "scope_key", "value", "unit"])
    for r in rows:
        ws.append([r.metric_code, r.scope, r.scope_key, r.value, r.unit])
    import io
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def _gen_xlsx_transition(session, theme, scenario_id, **_) -> bytes:
    # Deterministic register (impact classes only; pathway suggestions are AI/live-only).
    scenario, positions, moves = await transition_service._scenario_context(session, scenario_id)
    if scenario is None:
        return transition_service.register_to_xlsx([])
    from .diagnostics_service import positions_to_dicts
    pos = positions_to_dicts(positions)
    classes = transition_service.classify_impacts(pos, moves)
    by_key = {p["employee_key"]: p for p in pos}
    register = [{
        "employee_key": k, "display_name": by_key.get(k, {}).get("display_name", k),
        "job_title": by_key.get(k, {}).get("job_title", ""), "impact_class": cls,
        "skill_gaps": [], "suggested_pathway": "(run Transition Planner for AI pathways)",
        "source": "structural", "review_state": "n/a",
    } for k, cls in sorted(classes.items())]
    return transition_service.register_to_xlsx(register)


_GENERATORS = {
    "PPTX_DIAGNOSTIC": _gen_pptx_diagnostic,
    "PPTX_SCENARIOS": _gen_pptx_scenarios,
    "PPTX_AI_ROADMAP": _gen_pptx_ai_roadmap,
    "DOCX_TOM": _gen_docx_tom,
    "XLSX_METRICS": _gen_xlsx_metrics,
    "XLSX_TRANSITION": _gen_xlsx_transition,
}


async def generate(
    session: AsyncSession, *, engagement_id: str, type: str, template: str = "minimal",
    dataset_id: Optional[str] = None, scenario_id: Optional[str] = None,
) -> Optional[Dict]:
    """Generate a deliverable, persist the file + a Deliverable row, return metadata."""
    gen = _GENERATORS.get(type)
    if gen is None:
        return None
    theme = get_theme(template)

    # Scenario-based deliverables resolve their dataset for the provenance summary.
    if scenario_id and not dataset_id:
        dataset_id = await _dataset_for_scenario(session, scenario_id)

    data = await gen(session, theme, dataset_id=dataset_id, engagement_id=engagement_id,
                     scenario_id=scenario_id)

    out_dir = OUTPUT_DIR / engagement_id
    os.makedirs(out_dir, exist_ok=True)
    from uuid import uuid4
    filename = f"{type}_{uuid4().hex[:8]}.{_EXT[type]}"
    path = out_dir / filename
    path.write_bytes(data)

    prov = await provenance_summary(session, dataset_id)
    row = Deliverable(engagement_id=engagement_id, type=type, template=theme.name,
                      file_path=str(path), provenance_summary=prov)
    session.add(row)
    await session.flush()
    return {"id": row.id, "type": type, "template": theme.name, "file_path": str(path),
            "bytes": len(data), "provenance_summary": prov}


async def list_deliverables(session: AsyncSession, engagement_id: str) -> List[Dict]:
    rows = await session.scalars(
        select(Deliverable).where(Deliverable.engagement_id == engagement_id).order_by(
            Deliverable.generated_at
        )
    )
    return [{"id": r.id, "type": r.type, "template": r.template, "file_path": r.file_path,
             "provenance_summary": r.provenance_summary, "generated_at": str(r.generated_at)}
            for r in rows]
