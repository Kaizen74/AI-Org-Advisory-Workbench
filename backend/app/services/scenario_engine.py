"""Pure scenario move engine (Phase 4, Build Spec M3/B2).

`apply_moves(baseline_positions, moves)` is a **pure function**: it deep-copies the baseline,
applies the ordered moves, and returns a NEW positions list — it never mutates its input. Because
"undo" is implemented as recompute-from-baseline-with-fewer-moves, applying then removing any move
sequence reproduces baseline metrics byte-identically (the P4 property test).

Positions are plain dicts keyed by `employee_key`, with `manager_key` references (the same shape the
parser and metrics engine use). Moves that don't change structure (REASSIGN_TASKS, SET_ANCHOR_LAYER,
SET_DOCKING_STATION) are intentional no-ops on positions — they affect task rollups / annotations,
not headcount/span/cost.
"""
from __future__ import annotations

import copy
from typing import Callable, Dict, List

Position = Dict
Move = Dict

MOVE_TYPES = {
    "MERGE_UNITS", "SPLIT_UNIT", "REPARENT", "DELETE_POSITION", "ADD_POSITION",
    "CHANGE_GRADE", "REASSIGN_TASKS", "SET_ANCHOR_LAYER", "SET_DOCKING_STATION",
}


def apply_moves(baseline_positions: List[Position], moves: List[Move]) -> List[Position]:
    """Return a new positions list after applying `moves` in order. Never mutates the input."""
    positions = copy.deepcopy(baseline_positions)
    for move in moves:
        handler = _HANDLERS.get(move.get("move_type"))
        if handler is None:
            continue  # unknown/no-op move types leave positions unchanged
        positions = handler(positions, move.get("params") or {})
    return positions


def _index(positions: List[Position]) -> Dict[str, Position]:
    return {p["employee_key"]: p for p in positions}


# ── Move handlers (each returns the updated list) ────────────────────────────
def _change_grade(positions, params):
    idx = _index(positions)
    p = idx.get(params.get("employee_key"))
    if p is not None:
        if "grade" in params:
            p["grade"] = params["grade"]
        if params.get("level") is not None:
            p["level"] = params["level"]
    return positions


def _reparent(positions, params):
    idx = _index(positions)
    p = idx.get(params.get("employee_key"))
    if p is not None:
        p["manager_key"] = params.get("new_manager_key")
    return positions


def _delete_position(positions, params):
    key = params.get("employee_key")
    idx = _index(positions)
    target = idx.get(key)
    if target is None:
        return positions
    new_manager = target.get("manager_key")
    # Reattach the deleted node's direct reports to its manager (keep the tree connected).
    for p in positions:
        if p.get("manager_key") == key:
            p["manager_key"] = new_manager
    return [p for p in positions if p["employee_key"] != key]


def _add_position(positions, params):
    if not params.get("employee_key"):
        return positions
    positions.append({
        "employee_key": params["employee_key"],
        "display_name": params.get("display_name", params["employee_key"]),
        "job_title": params.get("job_title", ""),
        "grade": params.get("grade", ""),
        "department": params.get("department", "Unknown"),
        "level": params.get("level", 0),
        "manager_key": params.get("manager_key"),
        "manager_name": params.get("manager_name", ""),
        "salary": float(params.get("salary", 0) or 0),
        "work_activities": params.get("work_activities", ""),
    })
    return positions


def _merge_units(positions, params):
    source = params.get("source_manager_key")
    target = params.get("target_manager_key")
    if source is None or target is None:
        return positions
    # Move source's direct reports under target, then remove the source manager.
    for p in positions:
        if p.get("manager_key") == source:
            p["manager_key"] = target
    return [p for p in positions if p["employee_key"] != source]


def _split_unit(positions, params):
    manager_key = params.get("manager_key")
    new_manager = params.get("new_manager") or {}
    reports = set(params.get("reports") or [])
    idx = _index(positions)
    if manager_key not in idx or not new_manager.get("employee_key"):
        return positions
    # New sub-manager reports to the original manager.
    positions = _add_position(positions, {**new_manager, "manager_key": manager_key})
    # Move the listed reports under the new sub-manager.
    new_key = new_manager["employee_key"]
    for p in positions:
        if p["employee_key"] in reports:
            p["manager_key"] = new_key
    return positions


def _noop(positions, _params):
    return positions


_HANDLERS: Dict[str, Callable[[List[Position], Dict], List[Position]]] = {
    "CHANGE_GRADE": _change_grade,
    "REPARENT": _reparent,
    "DELETE_POSITION": _delete_position,
    "ADD_POSITION": _add_position,
    "MERGE_UNITS": _merge_units,
    "SPLIT_UNIT": _split_unit,
    "REASSIGN_TASKS": _noop,
    "SET_ANCHOR_LAYER": _noop,
    "SET_DOCKING_STATION": _noop,
}
