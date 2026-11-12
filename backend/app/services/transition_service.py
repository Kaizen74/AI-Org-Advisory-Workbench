"""Workforce Transition Planner service (Phase 5, Build Spec M5/B2).

For a scenario, classifies each role's **impact class** deterministically from the scenario's design
moves (unchanged / augmented / transformed / displaced / new). For impacted roles it asks Claude
(mocked in tests) for SkillsFuture-aligned reskilling pathway suggestions — these are
`model-inferred` + `unreviewed` (they pass through the M2 validation discipline; excluded from
client-ready exports per A4/M6). Exports a transition register (xlsx).
"""
from __future__ import annotations

import io
from typing import Dict, List, Optional

from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import DesignMove, Engagement, Position, Scenario
from . import settings_service
from ._json_utils import parse_ai_json
from .anonymization import display_label
from .claude_service import claude_service
from .diagnostics_service import positions_to_dicts

# Severity order (higher wins when a role is touched by several moves).
_RANK = {"unchanged": 0, "augmented": 1, "transformed": 2, "displaced": 3, "new": 4}
REGISTER_HEADERS = ["employee_key", "display_name", "job_title", "impact_class",
                    "skill_gaps", "suggested_pathway", "source", "review_state",
                    "compass_role_ref", "compass_route"]  # appended (D50); blank with no packet


def _upgrade(classes: Dict[str, str], key: str, new_class: str) -> None:
    if key is None:
        return
    if _RANK[new_class] >= _RANK.get(classes.get(key, "unchanged"), 0):
        classes[key] = new_class


def classify_impacts(baseline_positions: List[Dict], moves: List[Dict]) -> Dict[str, str]:
    """Deterministic per-role impact class from a scenario's moves."""
    classes: Dict[str, str] = {p["employee_key"]: "unchanged" for p in baseline_positions}
    reports_by_mgr: Dict[str, List[str]] = {}
    for p in baseline_positions:
        if p.get("manager_key"):
            reports_by_mgr.setdefault(p["manager_key"], []).append(p["employee_key"])

    for move in moves:
        mt = move.get("move_type")
        params = move.get("params") or {}
        if mt == "ADD_POSITION" and params.get("employee_key"):
            classes[params["employee_key"]] = "new"
        elif mt == "DELETE_POSITION":
            _upgrade(classes, params.get("employee_key"), "displaced")
        elif mt == "CHANGE_GRADE":
            _upgrade(classes, params.get("employee_key"), "augmented")
        elif mt == "REPARENT":
            _upgrade(classes, params.get("employee_key"), "augmented")
        elif mt == "REASSIGN_TASKS":
            _upgrade(classes, params.get("from_key"), "transformed")
            _upgrade(classes, params.get("to_key"), "transformed")
        elif mt == "MERGE_UNITS":
            _upgrade(classes, params.get("source_manager_key"), "displaced")
            _upgrade(classes, params.get("target_manager_key"), "augmented")
            for r in reports_by_mgr.get(params.get("source_manager_key"), []):
                _upgrade(classes, r, "transformed")
        elif mt == "SPLIT_UNIT":
            nm = (params.get("new_manager") or {}).get("employee_key")
            if nm:
                classes[nm] = "new"
            _upgrade(classes, params.get("manager_key"), "augmented")
            for r in params.get("reports", []):
                _upgrade(classes, r, "transformed")
    return classes


def _suggest_pathways(impacted: List[Dict]) -> List[Dict]:
    """Mocked-in-tests Claude call: SkillsFuture pathway suggestions for impacted roles."""
    if not impacted:
        return []
    import json
    prompt = (
        "Suggest SkillsFuture-aligned reskilling pathways for these impacted roles. Return STRICT "
        'JSON {"pathways": [{"employee_key": "...", "skill_gaps": ["..."], '
        '"suggested_pathway": "..."}]}.\n\nROLES:\n```json\n'
        + json.dumps(impacted, ensure_ascii=False) + "\n```"
    )
    raw = claude_service.complete(
        model=settings_service.model_synth(), messages=[{"role": "user", "content": prompt}]
    )
    return parse_ai_json(raw).get("pathways", [])


async def _scenario_context(session: AsyncSession, scenario_id: str):
    scenario = await session.get(Scenario, scenario_id)
    if scenario is None:
        return None, None, None, False
    positions = list(await session.scalars(
        select(Position).where(Position.dataset_id == scenario.dataset_id)
    ))
    moves = [
        {"move_type": m.move_type, "params": m.params or {}}
        for m in await session.scalars(
            select(DesignMove).where(DesignMove.scenario_id == scenario_id).order_by(DesignMove.seq)
        )
    ]
    engagement = await session.get(Engagement, scenario.engagement_id)
    anonymized = bool(engagement.anonymized) if engagement else False
    return scenario, positions, moves, anonymized


async def compute(session: AsyncSession, scenario_id: str) -> Optional[Dict]:
    scenario, positions, moves, anonymized = await _scenario_context(session, scenario_id)
    if scenario is None:
        return None
    pos_dicts = positions_to_dicts(positions)
    from . import compass_service
    role_idx = await compass_service.role_index(session, scenario.engagement_id)
    classes = classify_impacts(pos_dicts, moves)
    by_key = {p["employee_key"]: p for p in pos_dicts}

    # AI pathway suggestions for impacted (non-unchanged) roles.
    impacted = [
        {"employee_key": k, "job_title": by_key.get(k, {}).get("job_title", ""),
         "impact_class": cls}
        for k, cls in classes.items() if cls != "unchanged"
    ]
    pathways = {p["employee_key"]: p for p in _suggest_pathways(impacted)}

    register = []
    for key, cls in sorted(classes.items()):
        p = by_key.get(key, {})
        pw = pathways.get(key, {})
        register.append({
            "employee_key": key,
            "display_name": display_label(  # pseudonym when anonymized (M7)
                anonymized=anonymized, display_name=p.get("display_name"),
                pseudonym=p.get("pseudonym"), employee_key=key,
            ),
            "job_title": p.get("job_title", ""),
            "impact_class": cls,
            "skill_gaps": pw.get("skill_gaps", []),
            "suggested_pathway": pw.get("suggested_pathway", ""),
            "source": "model-inferred" if cls != "unchanged" else "structural",
            "review_state": "unreviewed" if cls != "unchanged" else "n/a",
            **{k: v for k, v in compass_service.role_fields(role_idx, p.get("job_title"), None).items()
               if k in ("compass_ref", "compass_route")},
        })

    summary: Dict[str, int] = {}
    for cls in classes.values():
        summary[cls] = summary.get(cls, 0) + 1

    return {"scenario_id": scenario_id, "name": scenario.name, "summary": summary,
            "register": register,
            "caveats": ["Pathway suggestions are model-inferred and unreviewed — validate before "
                        "client use; excluded from client-ready exports by default (A4/M6)."]}


def register_to_xlsx(register: List[Dict]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Transition Register"
    ws.append(REGISTER_HEADERS)
    for row in register:
        ws.append([
            row["employee_key"], row["display_name"], row["job_title"], row["impact_class"],
            "; ".join(row.get("skill_gaps") or []), row.get("suggested_pathway", ""),
            row["source"], row["review_state"],
            row.get("compass_ref") or "", row.get("compass_route") or "",
        ])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
