"""P1.9 + P1.10 — archetype port + activator pre-screen (pure logic + endpoints)."""
from __future__ import annotations

import json
from pathlib import Path

from app.parsers.csv_parser import OrgCSVParser
from app.resources.archetypes_reference import (
    ARCHETYPES,
    get_all_archetypes_summary,
    get_archetype_by_id,
)
from app.services.activator_service import compute_activator_screen
from app.services.metrics_service import MetricsCalculator

PAX_CSV = Path(__file__).parent / "fixtures" / "org_structure_PAX.csv"


# ── Archetype port (unchanged from v1) ──────────────────────────────────────
def test_seven_archetypes_present():
    assert len(ARCHETYPES) == 7
    summary = get_all_archetypes_summary()
    assert len(summary) == 7
    assert all({"id", "name", "core_tension"} <= set(a) for a in summary)
    assert get_archetype_by_id("4_process_based")["name"].startswith("Process-Based")


# ── Activator pre-screen ────────────────────────────────────────────────────
def _pax_metrics():
    positions = OrgCSVParser(str(PAX_CSV)).parse()["positions"]
    return MetricsCalculator(positions).calculate_all_metrics()


def test_activator_screen_shape_and_pax_triggers():
    screen = compute_activator_screen(_pax_metrics())
    assert len(screen["flags"]) == 5
    assert all(
        {"activator", "name", "triggered", "signal_metric", "basis"} <= set(f)
        for f in screen["flags"]
    )
    by_id = {f["activator"]: f for f in screen["flags"]}
    # PAX: avg span 1.85 (<5) and manager ratio 53.1 (>30) must trigger A3 and A4.
    assert by_id[3]["triggered"] is True
    assert by_id[4]["triggered"] is True
    # PAX has 6 layers (<=7) so A1 (layer bloat) must NOT trigger.
    assert by_id[1]["triggered"] is False
    assert screen["triggered_count"] >= 2
    assert "Heuristic" in screen["caveat"]


async def test_archetypes_and_activator_endpoints(api_client):
    arch = await api_client.get("/api/v1/diagnostics/archetypes")
    assert arch.status_code == 200
    assert len(arch.json()["archetypes"]) == 7

    # Activator endpoint needs a dataset.
    c = await api_client.post("/api/v1/engagements/clients", json={"name": "PAX"})
    e = await api_client.post(
        "/api/v1/engagements", json={"client_id": c.json()["id"], "name": "TOM"}
    )
    files = {"file": ("pax.csv", PAX_CSV.read_bytes(), "text/csv")}
    ds = await api_client.post(
        f"/api/v1/engagements/{e.json()['id']}/datasets", files=files
    )
    screen = await api_client.get(
        "/api/v1/diagnostics/activator-screen", params={"dataset_id": ds.json()["id"]}
    )
    assert screen.status_code == 200
    assert len(screen.json()["flags"]) == 5
