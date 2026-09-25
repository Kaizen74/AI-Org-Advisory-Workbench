"""P4.4 — Scenario Studio API: moves, delta vs baseline, present/lock/fork, 3-way compare."""
from __future__ import annotations

from pathlib import Path

PAX_CSV = Path(__file__).parent / "fixtures" / "org_structure_PAX.csv"


async def _engagement_with_dataset(api_client):
    c = await api_client.post("/api/v1/engagements/clients", json={"name": "PAX"})
    e = await api_client.post("/api/v1/engagements",
                              json={"client_id": c.json()["id"], "name": "TOM"})
    eng_id = e.json()["id"]
    files = {"file": ("org.csv", PAX_CSV.read_bytes(), "text/csv")}
    ds = await api_client.post(f"/api/v1/engagements/{eng_id}/datasets", files=files)
    ds_id = ds.json()["id"]
    # Persist baseline metric_values so deltas compute against them.
    await api_client.post("/api/v1/diagnostics/compute", params={"dataset_id": ds_id})
    return eng_id, ds_id


async def test_scenario_delta_against_baseline(api_client):
    eng_id, ds_id = await _engagement_with_dataset(api_client)
    s = await api_client.post("/api/v1/scenarios",
                              json={"engagement_id": eng_id, "dataset_id": ds_id, "name": "Lean"})
    sid = s.json()["id"]

    # Delete a $60k IC and add a $120k role => cost +60k, headcount unchanged.
    await api_client.post(f"/api/v1/scenarios/{sid}/moves",
                          json={"move_type": "DELETE_POSITION", "params": {"employee_key": "E064"}})
    await api_client.post(f"/api/v1/scenarios/{sid}/moves",
                          json={"move_type": "ADD_POSITION",
                                "params": {"employee_key": "E999", "manager_key": "E001",
                                           "grade": "H5", "level": 3, "salary": 120000}})

    d = await api_client.get(f"/api/v1/scenarios/{sid}/delta")
    body = d.json()
    assert body["baseline"]["total_cost"] == 6620000
    assert body["scenario"]["total_cost"] == 6680000
    assert body["delta"]["total_cost"] == 60000
    assert body["delta"]["total_employees"] == 0


async def test_present_locks_and_fork_allows_edit(api_client):
    eng_id, ds_id = await _engagement_with_dataset(api_client)
    s = await api_client.post("/api/v1/scenarios",
                              json={"engagement_id": eng_id, "dataset_id": ds_id, "name": "Base"})
    sid = s.json()["id"]
    await api_client.post(f"/api/v1/scenarios/{sid}/moves",
                          json={"move_type": "CHANGE_GRADE",
                                "params": {"employee_key": "E002", "grade": "H7"}})

    pres = await api_client.post(f"/api/v1/scenarios/{sid}/present")
    assert pres.json()["status"] == "PRESENTED"

    # Editing a presented scenario is rejected (409).
    locked = await api_client.post(f"/api/v1/scenarios/{sid}/moves",
                                   json={"move_type": "CHANGE_GRADE",
                                         "params": {"employee_key": "E003", "grade": "H7"}})
    assert locked.status_code == 409

    # Fork creates an editable DRAFT copy (carrying the parent's moves).
    fork = await api_client.post(f"/api/v1/scenarios/{sid}/fork")
    fid = fork.json()["id"]
    assert fork.json()["parent_scenario_id"] == sid
    ok = await api_client.post(f"/api/v1/scenarios/{fid}/moves",
                               json={"move_type": "CHANGE_GRADE",
                                     "params": {"employee_key": "E003", "grade": "H7"}})
    assert ok.status_code == 201


async def test_three_way_compare(api_client):
    eng_id, ds_id = await _engagement_with_dataset(api_client)
    ids = []
    for i, salary in enumerate((0, 50000, 100000)):
        s = await api_client.post("/api/v1/scenarios",
                                  json={"engagement_id": eng_id, "dataset_id": ds_id,
                                        "name": f"S{i}"})
        sid = s.json()["id"]
        if salary:
            await api_client.post(f"/api/v1/scenarios/{sid}/moves",
                                  json={"move_type": "ADD_POSITION",
                                        "params": {"employee_key": f"N{i}", "manager_key": "E001",
                                                   "grade": "H5", "level": 3, "salary": salary}})
        ids.append(sid)

    cmp = await api_client.get("/api/v1/scenarios/compare", params={"ids": ",".join(ids)})
    rows = cmp.json()["scenarios"]
    assert len(rows) == 3
    assert rows[0]["delta"]["total_cost"] == 0
    assert rows[2]["delta"]["total_cost"] == 100000


async def test_delta_404_for_missing_scenario(api_client):
    miss = await api_client.get("/api/v1/scenarios/ghost/delta")
    assert miss.status_code == 404
