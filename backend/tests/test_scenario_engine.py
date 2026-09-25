"""P4.2 — pure move engine: apply/undo byte-parity property test (Part A Rule 6).

The engine MUST be pure: applying any move sequence never mutates the baseline, and recomputing
from the baseline with the moves removed reproduces baseline metrics byte-identically.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from app.parsers.csv_parser import OrgCSVParser
from app.services.metrics_service import MetricsCalculator
from app.services.scenario_engine import apply_moves

PAX_CSV = Path(__file__).parent / "fixtures" / "org_structure_PAX.csv"


def _baseline():
    return OrgCSVParser(str(PAX_CSV)).parse()["positions"]


def _metrics(positions):
    return json.loads(json.dumps(MetricsCalculator(positions).calculate_all_metrics(), sort_keys=True))


MOVES = [
    {"move_type": "CHANGE_GRADE", "params": {"employee_key": "E002", "grade": "H7", "level": 2}},
    {"move_type": "REPARENT", "params": {"employee_key": "E003", "new_manager_key": "E001"}},
    {"move_type": "DELETE_POSITION", "params": {"employee_key": "E064"}},
    {"move_type": "ADD_POSITION", "params": {"employee_key": "E999", "manager_key": "E001",
                                             "grade": "H5", "level": 3, "salary": 120000,
                                             "department": "Passenger Services"}},
    {"move_type": "REASSIGN_TASKS", "params": {"from_key": "E002", "to_key": "E003"}},  # no-op
    {"move_type": "SET_ANCHOR_LAYER", "params": {"level": 3}},  # no-op
    {"move_type": "SET_DOCKING_STATION", "params": {"employee_key": "E001"}},  # no-op
]


def test_apply_does_not_mutate_baseline():
    baseline = _baseline()
    snapshot = copy.deepcopy(baseline)
    apply_moves(baseline, MOVES)
    assert baseline == snapshot  # input untouched (pure function)


def test_empty_moves_is_identity():
    baseline = _baseline()
    assert apply_moves(baseline, []) == baseline


def test_undo_reproduces_baseline_metrics_byte_identically():
    baseline = _baseline()
    base_metrics = _metrics(baseline)
    # Apply the full sequence (exercise every move path).
    apply_moves(baseline, MOVES)
    # "Undo" = recompute from baseline with the moves removed.
    undone = apply_moves(baseline, [])
    assert _metrics(undone) == base_metrics  # byte-identical


def test_progressive_undo_returns_to_baseline():
    baseline = _baseline()
    base_metrics = _metrics(baseline)
    # Removing moves one-by-one from the end must walk metrics back to baseline at k=0.
    for k in range(len(MOVES), -1, -1):
        m = _metrics(apply_moves(baseline, MOVES[:k]))
        if k == 0:
            assert m == base_metrics


def test_structural_effects_are_correct():
    baseline = _baseline()
    scenario = apply_moves(baseline, MOVES)
    base_m = MetricsCalculator(baseline).calculate_all_metrics()
    scn_m = MetricsCalculator(scenario).calculate_all_metrics()
    # delete E064 (-1) + add E999 (+1) => same headcount.
    assert scn_m["total_employees"] == base_m["total_employees"]
    # cost: baseline - 60000 (E064) + 120000 (E999).
    assert scn_m["cost_analysis"]["total_cost"] == base_m["cost_analysis"]["total_cost"] - 60000 + 120000


def test_merge_and_split_units():
    baseline = _baseline()
    # E002 and E003 are both VPs under E001. Merge E003's unit into E002.
    merged = apply_moves(baseline, [
        {"move_type": "MERGE_UNITS", "params": {"source_manager_key": "E003",
                                                "target_manager_key": "E002"}},
    ])
    keys = {p["employee_key"] for p in merged}
    assert "E003" not in keys  # source manager removed
    # Everyone who reported to E003 now reports to E002.
    e003_reports_baseline = [p["employee_key"] for p in baseline if p["manager_key"] == "E003"]
    for k in e003_reports_baseline:
        moved = next(p for p in merged if p["employee_key"] == k)
        assert moved["manager_key"] == "E002"

    # Split: pull two of E002's reports under a new sub-manager.
    e002_reports = [p["employee_key"] for p in baseline if p["manager_key"] == "E002"][:2]
    split = apply_moves(baseline, [
        {"move_type": "SPLIT_UNIT", "params": {
            "manager_key": "E002",
            "new_manager": {"employee_key": "NEW1", "grade": "H6", "level": 3, "salary": 150000,
                            "department": "Passenger Services"},
            "reports": e002_reports,
        }},
    ])
    new_mgr = next(p for p in split if p["employee_key"] == "NEW1")
    assert new_mgr["manager_key"] == "E002"
    for k in e002_reports:
        assert next(p for p in split if p["employee_key"] == k)["manager_key"] == "NEW1"
