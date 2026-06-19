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


async def test_delete_dataset_engagement_and_client(api_client):
    client_id, engagement_id = await _make_engagement(api_client)
    d1 = await _upload_pax(api_client, engagement_id)
    d2 = await _upload_pax(api_client, engagement_id)  # v2

    # Delete one CSV upload: it's gone, the other remains, the engagement stays.
    rd = await api_client.delete(f"/api/v1/engagements/datasets/{d1['id']}")
    assert rd.status_code == 200 and rd.json()["deleted"] == d1["id"]
    remaining = (await api_client.get(f"/api/v1/engagements/{engagement_id}/datasets")).json()
    assert {x["id"] for x in remaining} == {d2["id"]}
    assert (await api_client.delete(f"/api/v1/engagements/datasets/{d1['id']}")).status_code == 404

    # Delete the engagement: gone; not listed under its client.
    re = await api_client.delete(f"/api/v1/engagements/{engagement_id}")
    assert re.status_code == 200 and re.json()["deleted"] == engagement_id
    assert (await api_client.get(f"/api/v1/engagements/{engagement_id}")).status_code == 404
    under_client = (await api_client.get(
        "/api/v1/engagements", params={"client_id": client_id})).json()
    assert under_client == []

    # Delete the client: gone from the list.
    rc = await api_client.delete(f"/api/v1/engagements/clients/{client_id}")
    assert rc.status_code == 200 and rc.json()["deleted"] == client_id
    clients = (await api_client.get("/api/v1/engagements/clients")).json()
    assert client_id not in {c["id"] for c in clients}
    assert (await api_client.delete(f"/api/v1/engagements/clients/{client_id}")).status_code == 404


async def test_delete_client_cascades_through_full_pipeline(api_client, async_session, monkeypatch):
    """A client delete must remove tasks/scores/benchmarks/processes/links, not just the top rows."""
    from sqlalchemy import func, select

    from app.models import Process, Task, TaskAIScore, TaskLink
    from app.services.claude_service import claude_service

    def _ai(*, model, max_tokens=2048, messages):  # noqa: ARG001
        c = messages[0]["content"]
        if "GROUNDING:" in c:
            import json as _j
            tasks = _j.loads(c.split("TASKS:\n```json\n")[1].split("\n```")[0])
            return _j.dumps({"benchmarks": [
                {"task_id": t["task_id"], "status": "MISSING", "matched_task_ref": None,
                 "onet_task_code": None, "taxonomy_source_code": None,
                 "source": "model-inferred", "confidence": 0.3} for t in tasks]})
        import json as _j
        items = _j.loads(c.split("INPUT:\n```json\n")[1].split("\n```")[0])
        return _j.dumps({"extractions": [
            {"employee_key": it["employee_key"],
             "tasks": [s.strip() for s in it["work_activities"].split(";") if s.strip()]}
            for it in items]})

    monkeypatch.setattr(type(claude_service), "has_api_key", property(lambda self: True))
    monkeypatch.setattr(claude_service, "complete", _ai)

    csv = (
        "Name,Job Title,Grade,Department,Level,Line Manager,Salary,Employee ID,Work Activities\n"
        "Boss,Director,SVP,Cargo,1,Top of Org,300000,E1,Lead the cargo function\n"
        "Joe,Cargo Officer,AO,Cargo,2,Boss,80000,E2,Process air waybills; reconcile documents\n"
    )
    client_id, engagement_id = await _make_engagement(api_client)
    ds = (await api_client.post(f"/api/v1/engagements/{engagement_id}/datasets",
          files={"file": ("o.csv", csv.encode(), "text/csv")})).json()
    await api_client.post("/api/v1/task-intel/extract", params={"dataset_id": ds["id"]})
    await api_client.post("/api/v1/task-intel/benchmark", params={"dataset_id": ds["id"]})
    await api_client.post("/api/v1/task-intel/ai-opportunity", params={"dataset_id": ds["id"]})
    proc = await api_client.post("/api/v1/workflows",
                                 json={"engagement_id": engagement_id, "name": "P"})
    pid = proc.json()["id"]
    step = await api_client.post(f"/api/v1/workflows/{pid}/steps", json={"name": "S"})
    board = (await api_client.get(f"/api/v1/workflows/{pid}/board",
                                  params={"dataset_id": ds["id"]})).json()
    await api_client.post(f"/api/v1/workflows/steps/{step.json()['id']}/map-tasks",
                          json={"task_ids": [board["unmapped"][0]["id"]]})
    assert await async_session.scalar(select(func.count()).select_from(Task)) > 0

    rc = await api_client.delete(f"/api/v1/engagements/clients/{client_id}")
    assert rc.status_code == 200
    async_session.expire_all()
    for model in (Task, TaskAIScore, TaskLink, Process):
        assert await async_session.scalar(select(func.count()).select_from(model)) == 0
