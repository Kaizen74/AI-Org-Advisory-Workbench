"""Phase 0 guard for baseline fixture #1 — the PAX CSV + expected metrics.

The full PAX metric-parity test arrives in Phase 1 with the ported metrics engine. In Phase 0 we
only assert the fixture is present and well-formed, and that the recorded expected values match the
v1/Build-Spec numbers — so the parity target can never drift before P1 implements it.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
PAX_CSV = FIXTURES / "org_structure_PAX.csv"
EXPECTED = FIXTURES / "expected_pax_metrics.json"


def test_pax_csv_present_and_shaped():
    """The PAX CSV exists, is ID-keyed, and has exactly 64 employee rows."""
    assert PAX_CSV.exists(), "PAX fixture missing — ported from legacy in P0 (baseline #1)"
    with PAX_CSV.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 64
    # ID-keyed graph requirement (PRD M1 / Build Spec P1): an Employee ID column must exist.
    assert "Employee ID" in rows[0]
    assert rows[0]["Employee ID"] == "E001"
    assert rows[-1]["Employee ID"] == "E064"


def test_expected_pax_metrics_locked_values():
    """The recorded baseline numbers equal the LOCKED values for the provided PAX CSV (A3 Rule 2;
    DECISIONS.md D9 — provided CSV is the source of truth)."""
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    assert expected["total_employees"] == 64
    assert expected["total_managers"] == 34
    assert expected["manager_ratio_pct"] == 53.1
    assert expected["total_cost"] == 6620000
    assert expected["organizational_layers"] == 6
