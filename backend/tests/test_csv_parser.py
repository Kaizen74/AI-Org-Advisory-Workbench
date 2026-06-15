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


def test_pax_metadata_matches_locked_baseline():
    """Parser metadata reproduces the LOCKED PAX baseline (DECISIONS.md D9 — provided CSV is truth)."""
    meta = OrgCSVParser(str(PAX_CSV)).parse()["metadata"]
    assert meta["total_employees"] == EXPECTED["total_employees"]  # 64
    assert meta["manager_count"] == EXPECTED["total_managers"]  # 34
    assert meta["total_salary_cost"] == EXPECTED["total_cost"]  # 6,620,000
    assert meta["organizational_layers"] == EXPECTED["organizational_layers"]  # 6
    assert round(meta["manager_count"] / meta["total_employees"] * 100, 1) == EXPECTED[
        "manager_ratio_pct"
    ]  # 53.1


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


# ── Salary column header variants (fix: real client CSVs label it "Salary ($)") ──
SALARY_HEADER_VARIANTS = [
    "Salary ($)",      # the header in Eric's "Global Mkrting Co" upload
    "Salary (USD)",
    "Salary(SGD)",
    "Annual Salary",
    "Base Salary",
    "SALARY",
]


def _csv_with_salary_header(header: str) -> str:
    return (
        f"Name,Job Title,Grade,Department,Level,Line Manager,{header},Employee ID\n"
        "Boss,CEO,SVP,Exec,1,Top of Org,NA,E1\n"
        "Ann,Analyst,AO,Finance,2,Boss,80000,E2\n"
        "Ben,Analyst,AO,Ops,2,Boss,120000,E3\n"
    )


def test_salary_column_header_variants_are_recognized():
    """A salary column under common header variants must feed the cost metrics (not default to 0)."""
    for header in SALARY_HEADER_VARIANTS:
        result = OrgCSVParser(io.StringIO(_csv_with_salary_header(header))).parse()
        meta = result["metadata"]
        assert meta["total_salary_cost"] == 200000.0, f"header {header!r} not recognized"
        salaries = sorted(p["salary"] for p in result["positions"])
        assert salaries == [0.0, 80000.0, 120000.0], f"header {header!r} parsed wrong: {salaries}"


def test_currency_formatted_salary_values_are_parsed():
    """Values like '$120,000' (commas/symbols) are cleaned, regardless of the header label."""
    csv = (
        "Name,Job Title,Grade,Department,Level,Line Manager,Salary ($),Employee ID\n"
        "Boss,CEO,SVP,Exec,1,Top of Org,\"$300,000\",E1\n"
        "Ann,Analyst,AO,Finance,2,Boss,\"$80,000\",E2\n"
    )
    result = OrgCSVParser(io.StringIO(csv)).parse()
    assert result["metadata"]["total_salary_cost"] == 380000.0


# ── Validation guard ────────────────────────────────────────────────────────
def test_missing_required_columns_returns_error():
    result = OrgCSVParser(io.StringIO("Name,Title\nJohn,Manager")).parse()
    assert result["positions"] == []
    assert any("Missing required columns" in e for e in result["validation_warnings"])
