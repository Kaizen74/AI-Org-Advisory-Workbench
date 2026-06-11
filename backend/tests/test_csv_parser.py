"""P1.4 — CSV parser port tests (test-first, Part A Rule 6).

The breaking fix vs v1 (PRD M1): the org graph is keyed on **Employee ID** (with a surrogate
fallback), never on name. Name collisions therefore keep both positions as distinct nodes (intact
tree) and raise a validation warning listing the duplicates.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

from app.parsers.csv_parser import OrgCSVParser

FIXTURES = Path(__file__).parent / "fixtures"
PAX_CSV = FIXTURES / "org_structure_PAX.csv"
EXPECTED = json.loads((FIXTURES / "expected_pax_metrics.json").read_text())


# ── PAX golden parse ─────────────────────────────────────────────────────────
def test_pax_parses_id_keyed_with_no_warnings():
    result = OrgCSVParser(str(PAX_CSV)).parse()
    assert result["validation_warnings"] == []
    positions = result["positions"]
    assert len(positions) == 64
    # Keyed by Employee ID, not name.
    keys = {p["employee_key"] for p in positions}
    assert "E001" in keys and "E064" in keys
    # Manager linkage is resolved to the manager's employee_key.
    daniel = next(p for p in positions if p["employee_key"] == "E002")
    assert daniel["display_name"] == "Daniel Boy"
    assert daniel["manager_key"] == "E001"  # Vincent Chan
    # Root has no manager_key.
    vincent = next(p for p in positions if p["employee_key"] == "E001")
    assert vincent["manager_key"] is None


def test_pax_metadata_undisputed_values():
    """The two values that BOTH the spec and the provided CSV agree on."""
    meta = OrgCSVParser(str(PAX_CSV)).parse()["metadata"]
    assert meta["total_employees"] == EXPECTED["total_employees"]  # 64 ✓ (spec & data agree)
    assert meta["organizational_layers"] == EXPECTED["organizational_layers"]  # 6 ✓ (agree)


def test_pax_metadata_actual_fixture_values():
    """Documents the ACTUAL output of the faithful port on the CSV Eric provided in the zip.

    NOTE (open question for Eric): these differ from the Build Spec's P1 parity targets
    (total_managers=16 / ratio=25.0 / total_cost=5,770,000). `total_cost` is a raw salary sum, so the
    zip's CSV (sum=6,620,000) is a DIFFERENT file than the one the spec parity was defined against.
    The legacy v1 code itself produces these same numbers on this CSV. NOT yet locked into
    BASELINE.md — pending Eric's resolution of the data-vs-spec conflict (see .checkpoints/LATEST.md).
    """
    meta = OrgCSVParser(str(PAX_CSV)).parse()["metadata"]
    assert meta["manager_count"] == 34
    assert meta["total_salary_cost"] == 6620000
    assert round(meta["manager_count"] / meta["total_employees"] * 100, 1) == 53.1


# ── Breaking-fix behaviour: duplicate names ─────────────────────────────────
DUP_NAME_CSV = (
    "Name,Job Title,Grade,Department,Level,Line Manager,Salary,Employee ID\n"
    "Boss,CEO,SVP,Exec,1,Top of Org,300000,E1\n"
    "Tan Wei Ming,Analyst,AO,Finance,2,Boss,80000,E2\n"
    "Tan Wei Ming,Analyst,AO,Ops,2,Boss,80000,E3\n"
)


def test_duplicate_name_warns_and_keeps_intact_tree():
    result = OrgCSVParser(io.StringIO(DUP_NAME_CSV)).parse()
    # Both same-named people survive as separate ID-keyed nodes (tree intact).
    assert len(result["positions"]) == 3
    keys = sorted(p["employee_key"] for p in result["positions"])
    assert keys == ["E1", "E2", "E3"]
    # A duplicate-name warning is raised listing the collision.
    warnings = " ".join(result["validation_warnings"])
    assert "Tan Wei Ming" in warnings
    assert "duplicate" in warnings.lower()
    # The graph kept both reports under Boss.
    graph = result["graph"]
    assert sorted(graph.successors("E1")) == ["E2", "E3"]


# ── Surrogate-key fallback ──────────────────────────────────────────────────
NO_ID_CSV = (
    "Name,Job Title,Grade,Department,Level,Line Manager,Salary\n"
    "Boss,CEO,SVP,Exec,1,Top of Org,300000\n"
    "Ann,Analyst,AO,Finance,2,Boss,80000\n"
    "Ben,Analyst,AO,Ops,2,Boss,80000\n"
)


def test_surrogate_keys_when_no_employee_id_column():
    result = OrgCSVParser(io.StringIO(NO_ID_CSV)).parse()
    positions = result["positions"]
    assert len(positions) == 3
    # Every position gets a distinct (surrogate) key; linkage still works by name.
    keys = {p["employee_key"] for p in positions}
    assert len(keys) == 3
    ann = next(p for p in positions if p["display_name"] == "Ann")
    boss = next(p for p in positions if p["display_name"] == "Boss")
    assert ann["manager_key"] == boss["employee_key"]


# ── Validation guard ────────────────────────────────────────────────────────
def test_missing_required_columns_returns_error():
    result = OrgCSVParser(io.StringIO("Name,Title\nJohn,Manager")).parse()
    assert result["positions"] == []
    assert any("Missing required columns" in e for e in result["validation_warnings"])
