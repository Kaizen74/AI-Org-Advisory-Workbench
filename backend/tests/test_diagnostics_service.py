"""P1.6 — diagnostics flattening (pure logic, test-first Rule 6)."""
from __future__ import annotations

import json
from pathlib import Path

from app.parsers.csv_parser import OrgCSVParser
from app.services.diagnostics_service import flatten_metric_values
from app.services.metrics_service import MetricsCalculator

PAX_CSV = Path(__file__).parent / "fixtures" / "org_structure_PAX.csv"
EXPECTED = json.loads((Path(__file__).parent / "fixtures" / "expected_pax_metrics.json").read_text())


def _pax_rows():
    positions = OrgCSVParser(str(PAX_CSV)).parse()["positions"]
    metrics = MetricsCalculator(positions).calculate_all_metrics()
    return {r["metric_code"]: r for r in flatten_metric_values(metrics)}


def test_flatten_produces_typed_org_rows():
    rows = _pax_rows()
    # Every row is org-scope with a unit and a float value.
    for r in rows.values():
        assert r["scope"] == "org"
        assert r["scope_key"] is None
        assert isinstance(r["value"], float)
        assert r["unit"]


def test_flatten_headline_values_match_baseline():
    rows = _pax_rows()
    assert rows["total_employees"]["value"] == EXPECTED["total_employees"]
    assert rows["total_managers"]["value"] == EXPECTED["total_managers"]
    assert rows["manager_ratio_pct"]["value"] == EXPECTED["manager_ratio_pct"]
    assert rows["total_cost"]["value"] == EXPECTED["total_cost"]
    assert rows["organizational_layers"]["value"] == EXPECTED["organizational_layers"]
    assert rows["total_cost"]["unit"] == "currency"
