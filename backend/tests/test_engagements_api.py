"""P1.7 + P1.8 — engagement Hub + diagnostics API integration tests.

Covers the Phase 1 acceptance criteria: two-engagement isolation, PAX upload+compute parity,
typed metric_values persistence, guard pattern (404), and engagement purge cascade.
"""
from __future__ import annotations

import json
from pathlib import Path

PAX_CSV = Path(__file__).parent / "fixtures" / "org_structure_PAX.csv"
EXPECTED = json.loads((Path(__file__).parent / "fixtures" / "expected_pax_metrics.json").read_text())


async def _make_engagement(api_client, client_name="PAX Airlines", eng_name="TOM 2026"):
    c = await api_client.post("/api/v1/engagements/clients", json={"name": client_name})
    assert c.status_code == 201
    client_id = c.json()["id"]
    e = await api_client.post(
        "/api/v1/engagements", json={"client_id": client_id, "name": eng_name}
    )
    assert e.status_code == 201
    return client_id, e.json()["id"]


async def _upload_pax(api_client, engagement_id):
    files = {"file": ("org_structure_PAX.csv", PAX_CSV.read_bytes(), "text/csv")}
    r = await api_client.post(f"/api/v1/engagements/{engagement_id}/datasets", files=files)
    assert r.status_code == 201, r.text
    return r.json()


async def test_full_diagnostic_flow_and_pax_parity(api_client):
    _, engagement_id = await _make_engagement(api_client)
    dataset = await _upload_pax(api_client, engagement_id)
    assert dataset["row_count"] == 64
    assert dataset["version"] == 1

    # Compute diagnostics -> persisted typed metric_values, PAX parity.
    r = await api_client.post("/api/v1/diagnostics/compute", params={"dataset_id": dataset["id"]})
    assert r.status_code == 200, r.text
    metrics = r.json()["metrics"]
    assert metrics["total_employees"] == EXPECTED["total_employees"]
    assert metrics["total_managers"] == EXPECTED["total_managers"]
    assert metrics["total_cost"] == EXPECTED["total_cost"]
    assert metrics["organizational_layers"] == EXPECTED["organizational_layers"]

    # Summary reads the persisted rows back.
    s = await api_client.get("/api/v1/diagnostics/summary", params={"dataset_id": dataset["id"]})
    assert s.status_code == 200
    assert s.json()["computed"] is True
    assert s.json()["metrics"]["manager_ratio_pct"] == EXPECTED["manager_ratio_pct"]


async def test_two_engagement_isolation(api_client):
    c1, e1 = await _make_engagement(api_client, "Client A", "Engagement A")
    c2, e2 = await _make_engagement(api_client, "Client B", "Engagement B")

    only_a = await api_client.get("/api/v1/engagements", params={"client_id": c1})
    ids = {e["id"] for e in only_a.json()}
    assert ids == {e1}  # B's engagement is not listed under client A


async def test_guards_return_404(api_client):
    # Engagement with non-existent client.
    bad = await api_client.post(
        "/api/v1/engagements", json={"client_id": "nope", "name": "X"}
    )
    assert bad.status_code == 404
    # Compute on a missing dataset.
    miss = await api_client.post("/api/v1/diagnostics/compute", params={"dataset_id": "ghost"})
    assert miss.status_code == 404


async def test_purge_cascades(api_client):
    _, engagement_id = await _make_engagement(api_client)
    dataset = await _upload_pax(api_client, engagement_id)
    await api_client.post("/api/v1/diagnostics/compute", params={"dataset_id": dataset["id"]})

    purged = await api_client.delete(f"/api/v1/engagements/{engagement_id}/purge")
    assert purged.status_code == 200

    # Engagement gone; its dataset's metrics no longer computable.
    assert (await api_client.get(f"/api/v1/engagements/{engagement_id}")).status_code == 404
    summary = await api_client.get(
        "/api/v1/diagnostics/summary", params={"dataset_id": dataset["id"]}
    )
    assert summary.json()["computed"] is False  # rows purged
