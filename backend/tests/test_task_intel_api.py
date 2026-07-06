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


def test_human_agency_band_maps_has_to_h0_h5():
    """Pure mapping (D17): None/<1 → H0, 1..5 → H1..H5, clamped above 5."""
    from app.services.task_intelligence_service import human_agency_band
    assert human_agency_band(None) == "H0"
    assert human_agency_band(0) == "H0"
    assert [human_agency_band(n) for n in (1, 2, 3, 4, 5)] == ["H1", "H2", "H3", "H4", "H5"]
    assert human_agency_band(7) == "H5"  # clamp


def _infer_ai(*, model, max_tokens=2048, messages):  # noqa: ARG001
    """Mock: extract + benchmark-everything-MISSING + HAS-rubric inference for unmatched tasks."""
    c = messages[0]["content"]
    if "HUMAN AGENCY SCALE BENCHMARK" in c:  # the rubric inference call
        payload = json.loads(c.split("TASKS:\n```json\n")[1].split("\n```")[0])
        return json.dumps({"scores": [
            {"task_id": t["task_id"], "has_level": 2, "capability_score": 0.8,
             "zone": "GREEN_LIGHT", "confidence": 0.6, "rationale": "Routine knowledge task."}
            for t in payload]})
    if "GROUNDING:" in c:  # marketing tasks match nothing in the air-transport seed
        tasks = json.loads(c.split("TASKS:\n```json\n")[1].split("\n```")[0])
        return json.dumps({"benchmarks": [
            {"task_id": t["task_id"], "status": "MISSING", "matched_task_ref": None,
             "onet_task_code": None, "taxonomy_source_code": None,
             "source": "model-inferred", "confidence": 0.3} for t in tasks]})
    items = json.loads(c.split("INPUT:\n```json\n")[1].split("\n```")[0])
    return json.dumps({"extractions": [
        {"employee_key": it["employee_key"],
         "tasks": [s.strip() for s in it["work_activities"].split(";") if s.strip()]}
        for it in items]})


async def test_infer_unmatched_potential_via_rubric(api_client, async_session, monkeypatch):
    """Robust benchmarking: tasks with no curated match are scored via the WORKBank HAS rubric,
    tagged model-inferred + unreviewed (export-blocked). Idempotent + needs a key."""
    from app.services import task_intelligence_service as _tis
    monkeypatch.setattr(type(claude_service), "has_api_key", property(lambda self: True))
    monkeypatch.setattr(claude_service, "complete", _infer_ai)
    monkeypatch.setattr(_tis, "INFER_BATCH", 1)  # force multiple batches (regression: D34 truncation)
    await load_taxonomies(async_session)
    c = await api_client.post("/api/v1/engagements/clients", json={"name": "GM"})
    e = await api_client.post("/api/v1/engagements",
                              json={"client_id": c.json()["id"], "name": "AI"})
    eng = e.json()["id"]
    csv = (
        "Name,Job Title,Grade,Department,Level,Line Manager,Salary,Employee ID,Work Activities\n"
        "Ann,Head of Content,H5,Marketing,1,Top,300000,E1,Develop content strategy; Oversee press releases; Write copy\n"
    )
    ds = (await api_client.post(f"/api/v1/engagements/{eng}/datasets",
          files={"file": ("o.csv", csv.encode(), "text/csv")})).json()["id"]
    await api_client.post("/api/v1/task-intel/extract", params={"dataset_id": ds})
    await api_client.post("/api/v1/task-intel/benchmark", params={"dataset_id": ds})

    aiopp = (await api_client.post("/api/v1/task-intel/ai-opportunity",
                                   params={"dataset_id": ds})).json()
    assert aiopp["robotics_levers"] == 0 and aiopp["unclassified"] >= 1  # all unmatched

    infer = (await api_client.post("/api/v1/task-intel/infer-potential",
                                   params={"dataset_id": ds})).json()
    assert infer["candidates"] >= 1 and infer["updated"] == infer["candidates"]

    # The queue now shows real HAS bands (H2) instead of H0 / NO_BENCHMARK_MATCH...
    q = (await api_client.get("/api/v1/validation/queue", params={"dataset_id": ds})).json()
    ai = [i for i in q["items"] if i["kind"] == "ai_score"]
    assert all(i["label"].startswith("H2") for i in ai)
    assert all("GREEN_LIGHT" in i["label"] for i in ai)
    # ...but they stay model-inferred + unreviewed → export-blocked until approved.
    assert all(i["source"] == "model-inferred" and i["review_state"] == "unreviewed" for i in ai)

    # Idempotent re-run: nothing left unmatched → 0 candidates.
    again = (await api_client.post("/api/v1/task-intel/infer-potential",
                                   params={"dataset_id": ds})).json()
    assert again["candidates"] == 0 and again["updated"] == 0


async def test_infer_corrects_spurious_robotics_keeps_physical(api_client, async_session, monkeypatch):
    """A knowledge task auto-tagged ROBOTICS_GSE_LEVER (matched an O*NET code with no overlay) is
    re-banded by the HAS rubric, while a genuinely physical task stays a robotics/GSE lever (B-fix)."""
    def _ai(*, model, max_tokens=2048, messages):  # noqa: ARG001
        c = messages[0]["content"]
        if "HUMAN AGENCY SCALE BENCHMARK" in c:
            payload = json.loads(c.split("TASKS:\n```json\n")[1].split("\n```")[0])
            out = []
            for t in payload:
                if "baggage" in t["task_text"].lower() or "load" in t["task_text"].lower():
                    out.append({"task_id": t["task_id"], "has_level": None, "capability_score": None,
                                "zone": "ROBOTICS_GSE_LEVER", "confidence": 0.5,
                                "rationale": "Physical handling task."})
                else:
                    out.append({"task_id": t["task_id"], "has_level": 2, "capability_score": 0.8,
                                "zone": "GREEN_LIGHT", "confidence": 0.6, "rationale": "Knowledge task."})
            return json.dumps({"scores": out})
        if "GROUNDING:" in c:  # match everything to an O*NET code with NO overlay -> robotics
            tasks = json.loads(c.split("TASKS:\n```json\n")[1].split("\n```")[0])
            return json.dumps({"benchmarks": [
                {"task_id": t["task_id"], "status": "MATCHED", "matched_task_ref": "X",
                 "onet_task_code": "53-7062.00", "taxonomy_source_code": "SFW_AIR_TRANSPORT",
                 "source": "SFw", "confidence": 0.6} for t in tasks]})
        items = json.loads(c.split("INPUT:\n```json\n")[1].split("\n```")[0])
        return json.dumps({"extractions": [
            {"employee_key": it["employee_key"],
             "tasks": [s.strip() for s in it["work_activities"].split(";") if s.strip()]}
            for it in items]})

    monkeypatch.setattr(type(claude_service), "has_api_key", property(lambda self: True))
    monkeypatch.setattr(claude_service, "complete", _ai)
    await load_taxonomies(async_session)
    c = await api_client.post("/api/v1/engagements/clients", json={"name": "GM"})
    e = await api_client.post("/api/v1/engagements",
                              json={"client_id": c.json()["id"], "name": "AI"})
    eng = e.json()["id"]
    csv = (
        "Name,Job Title,Grade,Department,Level,Line Manager,Salary,Employee ID,Work Activities\n"
        "Ann,Head,H5,Marketing,1,Top,300000,E1,Develop content strategy\n"
        "Ben,Ramp,AO,Ops,2,Ann,70000,E2,Load baggage onto aircraft\n"
    )
    ds = (await api_client.post(f"/api/v1/engagements/{eng}/datasets",
          files={"file": ("o.csv", csv.encode(), "text/csv")})).json()["id"]
    await api_client.post("/api/v1/task-intel/extract", params={"dataset_id": ds})
    await api_client.post("/api/v1/task-intel/benchmark", params={"dataset_id": ds})
    aiopp = (await api_client.post("/api/v1/task-intel/ai-opportunity",
                                   params={"dataset_id": ds})).json()
    assert aiopp["robotics_levers"] == 2  # both auto-tagged robotics (matched, no overlay)

    infer = (await api_client.post("/api/v1/task-intel/infer-potential",
                                   params={"dataset_id": ds})).json()
    assert infer["updated"] == 2
    q = (await api_client.get("/api/v1/validation/queue", params={"dataset_id": ds})).json()
    ai = {i["task_text"]: i["label"] for i in q["items"] if i["kind"] == "ai_score"}
    assert ai["Develop content strategy"].startswith("H2") and "GREEN_LIGHT" in ai["Develop content strategy"]
    assert ai["Load baggage onto aircraft"].startswith("H0") and "ROBOTICS_GSE_LEVER" in ai["Load baggage onto aircraft"]

    # Idempotent: the confirmed physical lever is not re-inferred on a second pass.
    again = (await api_client.post("/api/v1/task-intel/infer-potential",
                                   params={"dataset_id": ds})).json()
    assert again["candidates"] == 0


async def test_inferred_zone_is_derived_from_has_not_model_label(api_client, async_session, monkeypatch):
    """D45 coherence: the inference path must DERIVE the GREEN/RED zone from capability + HAS (GREEN =
    AI-amenable H1–H2 + high capability), not trust the model's separate zone label — otherwise the
    board shows the same H-band in two colours (an H3 task tagged GREEN). Physical tasks stay robotics."""
    def _ai(*, model, max_tokens=2048, messages):  # noqa: ARG001
        c = messages[0]["content"]
        if "HUMAN AGENCY SCALE BENCHMARK" in c:  # the model deliberately returns INCOHERENT zones
            payload = json.loads(c.split("TASKS:\n```json\n")[1].split("\n```")[0])
            out = []
            for t in payload:
                low = t["task_text"].lower()
                if "physical" in low:
                    out.append({"task_id": t["task_id"], "has_level": None, "capability_score": None,
                                "zone": "ROBOTICS_GSE_LEVER", "confidence": 0.5, "rationale": "Physical."})
                elif "amenable" in low:  # H2 + high cap → correctly GREEN
                    out.append({"task_id": t["task_id"], "has_level": 2, "capability_score": 0.8,
                                "zone": "GREEN_LIGHT", "confidence": 0.6, "rationale": "AI can do most."})
                elif "partner" in low:  # H3 but model WRONGLY says GREEN → must derive to RED
                    out.append({"task_id": t["task_id"], "has_level": 3, "capability_score": 0.9,
                                "zone": "GREEN_LIGHT", "confidence": 0.6, "rationale": "Equal partnership."})
                else:  # "humanled": H4 but model WRONGLY says GREEN → must derive to RED
                    out.append({"task_id": t["task_id"], "has_level": 4, "capability_score": 0.3,
                                "zone": "GREEN_LIGHT", "confidence": 0.6, "rationale": "Human leads."})
            return json.dumps({"scores": out})
        if "GROUNDING:" in c:  # nothing matches the seed
            tasks = json.loads(c.split("TASKS:\n```json\n")[1].split("\n```")[0])
            return json.dumps({"benchmarks": [
                {"task_id": t["task_id"], "status": "MISSING", "matched_task_ref": None,
                 "onet_task_code": None, "taxonomy_source_code": None,
                 "source": "model-inferred", "confidence": 0.3} for t in tasks]})
        items = json.loads(c.split("INPUT:\n```json\n")[1].split("\n```")[0])
        return json.dumps({"extractions": [
            {"employee_key": it["employee_key"],
             "tasks": [s.strip() for s in it["work_activities"].split(";") if s.strip()]}
            for it in items]})

    from sqlalchemy import select
    from app.models import Task, TaskAIScore
    monkeypatch.setattr(type(claude_service), "has_api_key", property(lambda self: True))
    monkeypatch.setattr(claude_service, "complete", _ai)
    await load_taxonomies(async_session)
    c = await api_client.post("/api/v1/engagements/clients", json={"name": "GM"})
    e = await api_client.post("/api/v1/engagements", json={"client_id": c.json()["id"], "name": "AI"})
    eng = e.json()["id"]
    csv = ("Name,Job Title,Grade,Department,Level,Line Manager,Salary,Employee ID,Work Activities\n"
           "Ann,Head,H5,Marketing,1,Top,300000,E1,"
           "amenable routine drafting; partner cross-team decision; humanled leadership call; physical haul crates\n")
    ds = (await api_client.post(f"/api/v1/engagements/{eng}/datasets",
          files={"file": ("o.csv", csv.encode(), "text/csv")})).json()["id"]
    for ep in ("extract", "benchmark", "ai-opportunity", "infer-potential"):
        await api_client.post(f"/api/v1/task-intel/{ep}", params={"dataset_id": ds})

    by_text = {(await async_session.get(Task, s.task_id)).task_text: s
               for s in await async_session.scalars(select(TaskAIScore))}
    # H2 + high capability → GREEN (the only AI-amenable band that should be green).
    assert by_text["amenable routine drafting"].zone == "GREEN_LIGHT"
    # H3 with high capability but the model said GREEN → DERIVED to RED (not AI-amenable band).
    assert by_text["partner cross-team decision"].zone == "RED_LIGHT"
    # H4 → RED regardless of the model's GREEN label.
    assert by_text["humanled leadership call"].zone == "RED_LIGHT"
    # Physical → stays a robotics/GSE lever, off the software-agent scale.
    assert by_text["physical haul crates"].zone == "ROBOTICS_GSE_LEVER"
    assert by_text["physical haul crates"].has_level is None


async def test_org_rollup_endpoint_returns_reporting_hierarchy(api_client, async_session, monkeypatch):
    """GET /task-intel/org-rollup returns the reporting hierarchy with AI rolled up to the head (the
    shape the Workflow Mapper Roll-up org chart consumes). No API key needed for the read itself."""
    monkeypatch.setattr(type(claude_service), "has_api_key", property(lambda self: True))
    monkeypatch.setattr(claude_service, "complete", _pipeline_ai)
    await load_taxonomies(async_session)
    dataset_id = await _make_dataset(api_client)
    for ep in ("extract", "benchmark", "ai-opportunity"):
        await api_client.post(f"/api/v1/task-intel/{ep}", params={"dataset_id": dataset_id})

    r = await api_client.get("/api/v1/task-intel/org-rollup", params={"dataset_id": dataset_id})
    assert r.status_code == 200
    body = r.json()
    nodes = {n["employee_key"]: n for n in body["nodes"]}
    # Boss (E1) is the only root; Cargo (E2) and Pax (E3) report to it.
    assert body["roots"] == ["E1"]
    assert nodes["E2"]["manager_key"] == "E1" and nodes["E3"]["manager_key"] == "E1"
    # The head rolls up the whole org: 4 tasks (1 + 2 + 1) with 2 direct reports.
    assert nodes["E1"]["rollup_tasks"] == 4
    assert nodes["E1"]["direct_reports"] == 2 and nodes["E1"]["total_reports"] == 2
    # Names present (not anonymized) and the HAS scale ships for the legend.
    assert nodes["E1"]["name"] == "Boss" and nodes["E1"]["job_title"] == "CEO"
    assert set(body["human_agency_scale"]) == {"H0", "H1", "H2", "H3", "H4", "H5"}

    miss = await api_client.get("/api/v1/task-intel/org-rollup", params={"dataset_id": "ghost"})
    assert miss.status_code == 404  # unknown dataset → 404 (guarded by _positions)


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

    tasks = await api_client.get("/api/v1/task-intel/tasks", params={"dataset_id": dataset_id})
    assert len(tasks.json()["tasks"]) == 4  # GET /tasks lists extracted tasks (no key)

    roll = await api_client.get("/api/v1/task-intel/rollup", params={"dataset_id": dataset_id})
    body = roll.json()
    assert body["overall"]["tasks"] == 4
    assert "Cargo" in body["by_department"]
    assert any("occupation-level" in c for c in body["caveats"])

    # Headline AI-potential band (D17): every task lands in an H0–H5 band; H0 counts the no-overlay
    # (robotics) tasks, and the HAS rubric is shipped for the UI legend.
    agency = body["overall"]["agency"]
    assert sum(agency.values()) == 4  # all tasks banded
    assert agency.get("H0", 0) >= 1  # robotics lever(s) with no overlay → H0
    assert set(body["human_agency_scale"]) == {"H0", "H1", "H2", "H3", "H4", "H5"}

    # 404 guard for a missing dataset.
    miss = await api_client.get("/api/v1/task-intel/rollup", params={"dataset_id": "ghost"})
    assert miss.json()["overall"]["tasks"] == 0  # rollup tolerates empty; quick/extract 404
    miss2 = await api_client.get("/api/v1/task-intel/quick", params={"dataset_id": "ghost"})
    assert miss2.status_code == 404
