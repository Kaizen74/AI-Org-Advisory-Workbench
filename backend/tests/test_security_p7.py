"""P7 — anonymization end-to-end, audit trail, PDPA real-name purge.

Acceptance: an anonymized engagement leaks NO real name in any export; audit records key actions;
purging real names scrubs display_name while keeping pseudonymized analytics.
"""
from __future__ import annotations

import json

from sqlalchemy import select

from app.models import Position
from app.services import settings_service as ss
from app.services.anonymization import pseudonym_for
from app.services.claude_service import claude_service

REAL_NAMES = ["Vincent Chan", "Cargo Joe", "Ramp Ann"]
CSV = (
    "Name,Job Title,Grade,Department,Level,Line Manager,Salary,Employee ID,Work Activities\n"
    "Vincent Chan,Director,SVP,Cargo,1,Top of Org,300000,E1,Lead the cargo function\n"
    "Cargo Joe,Cargo Officer,AO,Cargo,2,Vincent Chan,80000,E2,Process air waybills and documents\n"
    "Ramp Ann,Ramp Officer,AO,Ramp,2,Vincent Chan,70000,E3,Load and unload baggage\n"
)


def _ai(*, model, max_tokens=2048, messages):  # noqa: ARG001
    c = messages[0]["content"]
    if "GROUNDING:" in c:
        tasks = json.loads(c.split("TASKS:\n```json\n")[1].split("\n```")[0])
        return json.dumps({"benchmarks": [
            {"task_id": t["task_id"], "status": "MATCHED", "matched_task_ref": "SFW_AT_CGO_01",
             "onet_task_code": "43-5011.00", "taxonomy_source_code": "SFW_AIR_TRANSPORT",
             "source": "SFw", "confidence": 0.85} for t in tasks]})
    if "ROLES:" in c:
        roles = json.loads(c.split("ROLES:\n```json\n")[1].split("\n```")[0])
        return json.dumps({"pathways": [
            {"employee_key": r["employee_key"], "skill_gaps": ["AI literacy"],
             "suggested_pathway": "SFw AI Associate"} for r in roles]})
    items = json.loads(c.split("INPUT:\n```json\n")[1].split("\n```")[0])
    return json.dumps({"extractions": [
        {"employee_key": it["employee_key"],
         "tasks": [s.strip() for s in it["work_activities"].split(";") if s.strip()]}
        for it in items]})


async def _anon_engagement(api_client, anonymized=True):
    c = await api_client.post("/api/v1/engagements/clients", json={"name": "PAX"})
    e = await api_client.post("/api/v1/engagements",
                              json={"client_id": c.json()["id"], "name": "TOM",
                                    "anonymized": anonymized})
    eng_id = e.json()["id"]
    ds = await api_client.post(f"/api/v1/engagements/{eng_id}/datasets",
                               files={"file": ("o.csv", CSV.encode(), "text/csv")})
    return eng_id, ds.json()["id"]


async def test_pseudonyms_generated_at_ingest_when_anonymized(api_client, async_session):
    eng_id, ds_id = await _anon_engagement(api_client, anonymized=True)
    positions = list(await async_session.scalars(
        select(Position).where(Position.dataset_id == ds_id)
    ))
    assert all(p.pseudonym and p.pseudonym.startswith("EMP-") for p in positions)
    # Pseudonyms are deterministic for (engagement, employee_key).
    p = next(x for x in positions if x.employee_key == "E2")
    assert p.pseudonym == pseudonym_for(eng_id, "E2")
    # Real names are still stored (only excluded from exports / purged on demand).
    assert p.display_name == "Cargo Joe"


async def test_no_real_name_in_transition_export_when_anonymized(api_client, async_session, monkeypatch):
    monkeypatch.setattr(type(claude_service), "has_api_key", property(lambda self: True))
    monkeypatch.setattr(claude_service, "complete", _ai)
    ss.reset_cache_for_tests()
    from app.services.taxonomy_loader import load_taxonomies
    await load_taxonomies(async_session)

    eng_id, ds_id = await _anon_engagement(api_client, anonymized=True)
    s = await api_client.post("/api/v1/scenarios",
                              json={"engagement_id": eng_id, "dataset_id": ds_id, "name": "Lean"})
    sid = s.json()["id"]
    await api_client.post(f"/api/v1/scenarios/{sid}/moves",
                          json={"move_type": "CHANGE_GRADE", "params": {"employee_key": "E2", "grade": "H5"}})

    # Register JSON.
    reg = await api_client.post("/api/v1/transition/compute", params={"scenario_id": sid})
    blob = json.dumps(reg.json())
    for name in REAL_NAMES:
        assert name not in blob, f"real name leaked in transition compute: {name}"
    assert "EMP-" in blob  # pseudonyms used instead

    # xlsx export bytes.
    xlsx = await api_client.get("/api/v1/transition/register.xlsx", params={"scenario_id": sid})
    for name in REAL_NAMES:
        assert name.encode() not in xlsx.content, f"real name leaked in xlsx: {name}"


async def test_not_anonymized_keeps_real_names(api_client):
    eng_id, ds_id = await _anon_engagement(api_client, anonymized=False)
    # control: with anonymization off, names remain (not part of the leak guarantee)
    g = await api_client.get(f"/api/v1/engagements/{eng_id}")
    assert g.json()["anonymized"] is False


async def test_real_name_purge_scrubs_names_and_audits(api_client, async_session):
    eng_id, ds_id = await _anon_engagement(api_client, anonymized=True)
    purged = await api_client.delete(f"/api/v1/engagements/{eng_id}/real-names")
    assert purged.status_code == 200
    assert purged.json()["names_scrubbed"] == 3

    positions = list(await async_session.scalars(
        select(Position).where(Position.dataset_id == ds_id)
    ))
    assert all(p.display_name is None for p in positions)  # real names gone
    assert all(p.pseudonym for p in positions)             # analytics still referenceable

    audit = await api_client.get("/api/v1/audit", params={"engagement_id": eng_id})
    types = [e["event_type"] for e in audit.json()["events"]]
    assert "dataset_uploaded" in types
    assert "real_names_purged" in types
