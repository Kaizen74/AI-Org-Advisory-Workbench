"""P4.5 — scenario-delta baseline snapshot parity (A3 Rule 2).

A fixed move sequence on the PAX fixture must reproduce the committed delta snapshot byte-identically.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.parsers.csv_parser import OrgCSVParser
from app.services.diagnostics_service import flatten_metric_values
from app.services.metrics_service import MetricsCalculator
from app.services.scenario_engine import apply_moves

PAX_CSV = Path(__file__).parent / "fixtures" / "org_structure_PAX.csv"
SNAPSHOT = Path(__file__).parent / "baseline" / "scenario_delta.json"


def test_scenario_delta_matches_snapshot():
    snap = json.loads(SNAPSHOT.read_text())
    positions = OrgCSVParser(str(PAX_CSV)).parse()["positions"]

    base = {r["metric_code"]: r["value"]
            for r in flatten_metric_values(MetricsCalculator(positions).calculate_all_metrics())}
    scn_positions = apply_moves(positions, snap["moves"])
    scn = {r["metric_code"]: r["value"]
           for r in flatten_metric_values(MetricsCalculator(scn_positions).calculate_all_metrics())}
    delta = {k: round(scn[k] - base[k], 4) for k in scn}

    assert base == snap["baseline"]
    assert scn == snap["scenario"]
    assert delta == snap["delta"]
