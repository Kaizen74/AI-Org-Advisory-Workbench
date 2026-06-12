"""P2.8 — Task Intelligence API integration (mocked AI), guards, and canonical rollup snapshot."""
from __future__ import annotations

import json

from app.services.claude_service import claude_service
from app.services.taxonomy_loader import load_taxonomies

CSV = (
    "Name,Job Title,Grade,Department,Level,Line Manager,Salary,Employee ID,Work Activities\n"
    "Boss,CEO,SVP,Exec,1,Top of Org,300000,E1,Lead the organisation\n"
    "Cargo Joe,Cargo Officer,AO,Cargo,2,Boss,80000,E2,Process air waybills and customs documents; Load and unload baggage onto aircraft\n"
    "Pax Pam,Pax Officer,AO,Pax,2,Boss,80000,E3,Perform passenger check-in and boarding\n"
)


def _pipeline_ai(*, model, max_tokens=2048, messages):  # noqa: ARG001
    """Combined fake AI: dispatch on prompt shape (extract vs benchmark)."""
    content = messages[0]["content"]
    if "GROUNDING:" in content:  # benchmark prompt
        tasks = json.loads(content.split("TASKS:\n```json\n")[1].split("\n```")[0])
        out = []
        for t in tasks:
            text = t["task_text"].lower()
            if any(k in text for k in ("waybill", "document", "cargo")):
                out.append({"task_id": t["task_id"], "status": "MATCHED",
                            "matched_task_ref": "SFW_AT_CGO_01", "onet_task_code": "43-5011.00",
                            "taxonomy_source_code": "SFW_AIR_TRANSPORT", "source": "SFw",
                            "confidence": 0.85})
            elif any(k in text for k in ("check-in", "boarding")):
                out.append({"task_id": t["task_id"], "status": "MATCHED",
                            "matched_task_ref": "SFW_AT_PSO_01", "onet_task_code": "43-4181.00",
                            "taxonomy_source_code": "SFW_AIR_TRANSPORT", "source": "SFw",
                            "confidence": 0.88})
            elif any(k in text for k in ("load", "baggage")):
                out.append({"task_id": t["task_id"], "status": "MATCHED",
                            "matched_task_ref": "SFW_AT_RHO_01", "onet_task_code": "53-7062.00",
                            "taxonomy_source_code": "SFW_AIR_TRANSPORT", "source": "SFw",
                            "confidence": 0.60})
            else:
                out.append({"task_id": t["task_id"], "status": "MISSING",
                            "matched_task_ref": None, "onet_task_code": None,
                            "taxonomy_source_code": None, "source": "model-inferred",
                            "confidence": 0.30})
        return json.dumps({"benchmarks": out})
    # extraction prompt
    items = json.loads(content.split("INPUT:\n```json\n")[1].split("\n```")[0])
    return json.dumps({"extractions": [
        {"employee_key": it["employee_key"],
         "tasks": [s.strip() for s in it["work_activities"].split(";") if s.strip()]}
        for it in items
    ]})


async def _make_dataset(api_client):
    c = await api_client.post("/api/v1/engagements/clients", json={"name": "PAX"})
    e = await api_client.post("/api/v1/engagements",
                              json={"client_id": c.json()["id"], "name": "TOM"})
    files = {"file": ("org.csv", CSV.encode(), "text/csv")}
    ds = await api_client.post(f"/api/v1/engagements/{e.json()['id']}/datasets", files=files)
    return ds.json()["id"]


async def test_quick_works_without_api_key(api_client):
    dataset_id = await _make_dataset(api_client)
    r = await api_client.get("/api/v1/task-intel/quick", params={"dataset_id": dataset_id})
    assert r.status_code == 200
    body = r.json()
    assert body["positions_with_activities"] == 3
    assert body["coverage_pct"] == 100.0


async def test_ai_endpoint_requires_key(api_client, monkeypatch):
    monkeypatch.setattr(type(claude_service), "has_api_key", property(lambda self: False))
    dataset_id = await _make_dataset(api_client)
    r = await api_client.post("/api/v1/task-intel/extract", params={"dataset_id": dataset_id})
    assert r.status_code == 400


async def test_full_pipeline_via_api(api_client, async_session, monkeypatch):
    monkeypatch.setattr(type(claude_service), "has_api_key", property(lambda self: True))
    monkeypatch.setattr(claude_service, "complete", _pipeline_ai)
    await load_taxonomies(async_session)  # reference layer in the same session
    dataset_id = await _make_dataset(api_client)

    ext = await api_client.post("/api/v1/task-intel/extract", params={"dataset_id": dataset_id})
    assert ext.status_code == 200
    assert ext.json()["tasks_created"] == 4  # 1 + 2 + 1

    bench = await api_client.post("/api/v1/task-intel/benchmark", params={"dataset_id": dataset_id})
    assert bench.json()["matched"] == 3

    aiopp = await api_client.post("/api/v1/task-intel/ai-opportunity",
                                  params={"dataset_id": dataset_id})
    assert aiopp.json()["with_overlay"] == 2
    assert aiopp.json()["robotics_levers"] >= 1

    roll = await api_client.get("/api/v1/task-intel/rollup", params={"dataset_id": dataset_id})
    body = roll.json()
    assert body["overall"]["tasks"] == 4
    assert "Cargo" in body["by_department"]
    assert any("occupation-level" in c for c in body["caveats"])

    # 404 guard for a missing dataset.
    miss = await api_client.get("/api/v1/task-intel/rollup", params={"dataset_id": "ghost"})
    assert miss.json()["overall"]["tasks"] == 0  # rollup tolerates empty; quick/extract 404
    miss2 = await api_client.get("/api/v1/task-intel/quick", params={"dataset_id": "ghost"})
    assert miss2.status_code == 404
