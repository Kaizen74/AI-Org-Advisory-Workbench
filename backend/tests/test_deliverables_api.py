"""P6.4 + P6.5 — Deliverable Factory: generation, export-block, provenance, list/download."""
from __future__ import annotations

import json

from app.services.claude_service import claude_service
from app.services.taxonomy_loader import load_taxonomies

CSV = (
    "Name,Job Title,Grade,Department,Level,Line Manager,Salary,Employee ID,Work Activities\n"
    "Boss,Director,SVP,Cargo,1,Top of Org,300000,E1,Lead the cargo function\n"
    "Cargo Joe,Cargo Officer,AO,Cargo,2,Boss,80000,E2,Process air waybills and documents\n"
    "Ramp Ann,Ramp Officer,AO,Ramp,2,Boss,70000,E3,Load and unload baggage onto aircraft\n"
)


def _ai(*, model, max_tokens=2048, messages):  # noqa: ARG001
    c = messages[0]["content"]
    if "GROUNDING:" in c:
        tasks = json.loads(c.split("TASKS:\n```json\n")[1].split("\n```")[0])
        out = []
        for t in tasks:
            text = t["task_text"].lower()
            if "waybill" in text or "document" in text:
                out.append({"task_id": t["task_id"], "status": "MATCHED",
                            "matched_task_ref": "SFW_AT_CGO_01", "onet_task_code": "43-5011.00",
                            "taxonomy_source_code": "SFW_AIR_TRANSPORT", "source": "SFw",
                            "confidence": 0.85})
            else:  # baggage -> physical, no overlay -> model-inferred robotics lever
                out.append({"task_id": t["task_id"], "status": "MATCHED",
                            "matched_task_ref": "SFW_AT_RHO_01", "onet_task_code": "53-7062.00",
                            "taxonomy_source_code": "SFW_AIR_TRANSPORT", "source": "SFw",
                            "confidence": 0.60})
        return json.dumps({"benchmarks": out})
    items = json.loads(c.split("INPUT:\n```json\n")[1].split("\n```")[0])
    return json.dumps({"extractions": [
        {"employee_key": it["employee_key"],
         "tasks": [s.strip() for s in it["work_activities"].split(";") if s.strip()]}
        for it in items]})


async def _setup(api_client, async_session, monkeypatch):
    monkeypatch.setattr(type(claude_service), "has_api_key", property(lambda self: True))
    monkeypatch.setattr(claude_service, "complete", _ai)
    await load_taxonomies(async_session)
    c = await api_client.post("/api/v1/engagements/clients", json={"name": "PAX"})
    e = await api_client.post("/api/v1/engagements",
                              json={"client_id": c.json()["id"], "name": "TOM"})
    eng_id = e.json()["id"]
    ds = await api_client.post(f"/api/v1/engagements/{eng_id}/datasets",
                               files={"file": ("o.csv", CSV.encode(), "text/csv")})
    ds_id = ds.json()["id"]
    await api_client.post("/api/v1/task-intel/extract", params={"dataset_id": ds_id})
    await api_client.post("/api/v1/task-intel/benchmark", params={"dataset_id": ds_id})
    await api_client.post("/api/v1/task-intel/ai-opportunity", params={"dataset_id": ds_id})
    await api_client.post("/api/v1/diagnostics/compute", params={"dataset_id": ds_id})
    return eng_id, ds_id


async def test_generate_all_types_and_provenance(api_client, async_session, monkeypatch):
    eng_id, ds_id = await _setup(api_client, async_session, monkeypatch)
    # A scenario for scenario/transition deliverables.
    s = await api_client.post("/api/v1/scenarios",
                              json={"engagement_id": eng_id, "dataset_id": ds_id, "name": "Lean"})
    sid = s.json()["id"]
    await api_client.post(f"/api/v1/scenarios/{sid}/moves",
                          json={"move_type": "DELETE_POSITION", "params": {"employee_key": "E3"}})

    specs = [
        ("PPTX_DIAGNOSTIC", {"dataset_id": ds_id}),
        ("PPTX_AI_ROADMAP", {"dataset_id": ds_id}),
        ("PPTX_WORKFLOW", {"dataset_id": ds_id}),
        ("DOCX_TOM", {"dataset_id": ds_id}),
        ("XLSX_METRICS", {"dataset_id": ds_id}),
        ("PPTX_SCENARIOS", {}),
        ("XLSX_TRANSITION", {"scenario_id": sid}),
    ]
    ids = []
    for dtype, params in specs:
        r = await api_client.post("/api/v1/deliverables/generate",
                                  params={"engagement_id": eng_id, "type": dtype, **params})
        assert r.status_code == 200, f"{dtype}: {r.text}"
        body = r.json()
        assert body["bytes"] > 0
        assert "provenance_summary" in body
        ids.append(body["id"])

    # List + download a generated file (valid Office/zip file → 'PK').
    listed = await api_client.get("/api/v1/deliverables/list", params={"engagement_id": eng_id})
    assert len(listed.json()["deliverables"]) == 7
    dl = await api_client.get(f"/api/v1/deliverables/{ids[0]}/download")
    assert dl.status_code == 200
    assert dl.content[:2] == b"PK"


async def test_export_block_excludes_unreviewed_model_inferred(api_client, async_session, monkeypatch):
    eng_id, ds_id = await _setup(api_client, async_session, monkeypatch)
    r = await api_client.post("/api/v1/deliverables/generate",
                              params={"engagement_id": eng_id, "type": "PPTX_AI_ROADMAP",
                                      "dataset_id": ds_id})
    prov = r.json()["provenance_summary"]
    # The ramp/baggage task is model-inferred + unreviewed -> export-blocked from client content.
    assert prov["excluded_unreviewed_model_inferred"] >= 1
    assert prov["client_ready"] >= 1
    assert prov["total"] >= 2
    # Disclosure carries the binding caveats.
    assert any("occupation-level" in c for c in prov["caveats"])


async def test_workflow_deliverable_reflects_mapping(api_client, async_session, monkeypatch):
    """The 'finalized workflow' deck builds from the real board: a mapped task produces a valid file."""
    from sqlalchemy import select

    from app.models import Task

    eng_id, ds_id = await _setup(api_client, async_session, monkeypatch)
    proc = await api_client.post("/api/v1/workflows",
                                 json={"engagement_id": eng_id, "name": "Cargo Acceptance"})
    pid = proc.json()["id"]
    step = await api_client.post(f"/api/v1/workflows/{pid}/steps", json={"name": "Documentation"})
    sid = step.json()["id"]
    tid = (await async_session.scalars(select(Task))).first().id
    await api_client.post(f"/api/v1/workflows/steps/{sid}/map-tasks", json={"task_ids": [tid]})

    r = await api_client.post("/api/v1/deliverables/generate",
                              params={"engagement_id": eng_id, "type": "PPTX_WORKFLOW",
                                      "dataset_id": ds_id})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["type"] == "PPTX_WORKFLOW"
    assert body["bytes"] > 0
    dl = await api_client.get(f"/api/v1/deliverables/{body['id']}/download")
    assert dl.status_code == 200
    assert dl.content[:2] == b"PK"  # valid Office/zip file

    # The new type is offered by the /types endpoint (backend↔frontend alignment).
    types = (await api_client.get("/api/v1/deliverables/types")).json()["types"]
    assert "PPTX_WORKFLOW" in types


async def test_unknown_type_rejected(api_client, async_session, monkeypatch):
    eng_id, _ = await _setup(api_client, async_session, monkeypatch)
    r = await api_client.post("/api/v1/deliverables/generate",
                              params={"engagement_id": eng_id, "type": "PPTX_BOGUS"})
    assert r.status_code == 400
