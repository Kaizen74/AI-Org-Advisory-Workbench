"""P1.5 — metrics engine PAX parity + baseline-snapshot parity (A3 Rule 2).

The metrics engine port must reproduce the LOCKED PAX numbers (DECISIONS.md D9) and stay byte-stable
against the snapshot under `backend/tests/baseline/`.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.parsers.csv_parser import OrgCSVParser
from app.services.metrics_service import MetricsCalculator

FIXTURES = Path(__file__).parent / "fixtures"
BASELINE = Path(__file__).parent / "baseline"
PAX_CSV = FIXTURES / "org_structure_PAX.csv"
EXPECTED = json.loads((FIXTURES / "expected_pax_metrics.json").read_text())


def _pax_metrics() -> dict:
    positions = OrgCSVParser(str(PAX_CSV)).parse()["positions"]
    return MetricsCalculator(positions).calculate_all_metrics()


def test_pax_metric_parity():
    """Headline metrics equal the locked baseline values."""
    m = _pax_metrics()
    assert m["total_employees"] == EXPECTED["total_employees"]  # 64
    assert m["manager_stats"]["total_managers"] == EXPECTED["total_managers"]  # 34
    assert m["manager_stats"]["manager_ratio_pct"] == EXPECTED["manager_ratio_pct"]  # 53.1
    assert m["cost_analysis"]["total_cost"] == EXPECTED["total_cost"]  # 6,620,000
    assert m["layer_analysis"]["total_layers"] == EXPECTED["organizational_layers"]  # 6


def test_pax_metrics_snapshot_byte_stable():
    """The full deterministic metrics payload matches the committed snapshot exactly."""
    snapshot = json.loads((BASELINE / "pax_metrics.json").read_text())
    current = json.loads(json.dumps(_pax_metrics(), sort_keys=True))  # normalize for comparison
    assert current == snapshot


def test_empty_positions_safe():
    """No positions -> zeroed metrics, no exception (guard)."""
    m = MetricsCalculator([]).calculate_all_metrics()
    assert m["total_employees"] == 0
    assert m["manager_stats"]["total_managers"] == 0
