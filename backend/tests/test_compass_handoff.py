"""D50 — shared language and hand-off with Capability Compass.

Uses the sample packet (`fixtures/meridian_compass_handoff.json`, fictional data) and deliberately
broken copies (wrong `format`, missing `engagement.key`, a `cluster_ref` that points nowhere).
No real AI calls: tasks/scores are seeded directly or come from the `mock_claude` fixture.
"""
from __future__ import annotations

import copy
import csv
import io
import json
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models import (
    Client, CompassRole, Engagement, Position, Task, TaskAIScore, TaskBenchmark,
)
from app.services.shared_grade import shared_grade, weakest

SAMPLE = json.loads(
    (Path(__file__).parent / "fixtures" / "meridian_compass_handoff.json").read_text(encoding="utf-8"))

# A small fictional org file. Real-looking names so the "no names leave the app" tests have teeth.
ORG_CSV = (
    "Name,Job Title,Grade,Department,Level,Line Manager,Salary,Employee ID,Work Activities\n"
    "Alice Tan,Group CEO,E1,Exec,1,Top of Org,500000,M001,\n"
    "Bob Lee,Regional VP Cargo,E2,Cargo,2,Alice Tan,300000,M002,Plan trade lanes\n"
    "Carol Ng,Regional VP Cargo,E2,Cargo,2,Alice Tan,300000,M003,Plan trade lanes\n"
    "Dev Rao,Head of Analytics and AI,E2,Tech,2,Alice Tan,280000,M004,Build models\n"
    "Eve Lim,Core-system super-user,E4,Tech,3,Dev Rao,90000,M005,Run month-end workarounds\n"
    "Fay Wong,VP Global Account Management,E2,Commercial,2,Alice Tan,290000,M006,Manage renewals\n"
    "Gus Ho,Finance Analyst,E5,Finance,3,Alice Tan,70000,M007,Reconcile ledgers\n"
)
REAL_NAMES = ["Alice Tan", "Bob Lee", "Carol Ng", "Dev Rao", "Eve Lim", "Fay Wong", "Gus Ho"]


def broken(kind: str) -> dict:
    p = copy.deepcopy(SAMPLE)
    if kind == "wrong_format":
        p["format"] = "something-else"
    elif kind == "missing_key":
        del p["engagement"]["key"]
    elif kind == "dangling_cluster":
        p["for_apps"]["workbench"]["roles"][0]["cluster_ref"] = "CAP-99"
    return p


async def _counts(session):
    return (await session.scalar(select(func.count(Engagement.id))),
            await session.scalar(select(func.count(Client.id))),
            await session.scalar(select(func.count(CompassRole.id))))


async def _engagement_with_org(api_client, name="MERIDIAN Meridian Group (fictional demo)",
                               anonymized=False):
    c = await api_client.post("/api/v1/engagements/clients",
                              json={"name": "Meridian Group (fictional demo)"})
    e = await api_client.post("/api/v1/engagements", json={
        "client_id": c.json()["id"], "name": name, "anonymized": anonymized})
    eng_id = e.json()["id"]
    ds = await api_client.post(f"/api/v1/engagements/{eng_id}/datasets",
                               files={"file": ("org.csv", ORG_CSV.encode(), "text/csv")})
    assert ds.status_code == 201, ds.text
    return eng_id, ds.json()["id"]


async def _seed_tasks(session, ds_id):
    """Seed deterministic tasks + AI scores (no AI call). Returns {label: task}."""
    pos = {p.employee_key: p for p in await session.scalars(
        select(Position).where(Position.dataset_id == ds_id))}
    spec = [
        # label, employee, text, has_level, capability, source, review_state, reviewed?
        ("super_auto", "M005", "Run month-end reconciliation workarounds", 2, 0.80, "model-inferred", "approved", True),
        ("super_human", "M005", "Coach colleagues on undocumented system quirks", 5, 0.20, "model-inferred", "approved", True),
        ("cargo_auto", "M002", "Compile weekly trade-lane volume report", 1, 0.90, "WORKBank", "approved", True),
        ("cargo_unrev", "M003", "Draft regional cargo strategy memo", 2, 0.70, "model-inferred", "unreviewed", False),
        ("acct_aug", "M006", "Prepare renewal negotiation pack", 3, 0.60, "model-inferred", "approved", True),
        ("fin_auto", "M007", "Reconcile ledgers against bank statements", 1, 0.95, "WORKBank", "approved", True),
    ]
    out = {}
    for label, emp, text, has, cap, source, state, reviewed in spec:
        t = Task(position_id=pos[emp].id, task_text=text, extraction_source="model-inferred")
        session.add(t)
        await session.flush()
        session.add(TaskAIScore(
            task_id=t.id, has_level=has, capability_score=cap, desire_score_us=0.5,
            zone="GREEN_LIGHT" if has <= 2 else "RED_LIGHT", ai_opportunity_level="L2",
            source=source, confidence=0.8, review_state=state,
            reviewed_at=datetime.utcnow() if reviewed else None))
        out[label] = t
    await session.flush()
    return out


async def _import(api_client, eng_id=None, **extra):
    body = {"packet": SAMPLE, **extra}
    if eng_id:
        body["engagement_id"] = eng_id
    r = await api_client.post("/api/v1/compass/apply", json=body)
    assert r.status_code == 200, r.text
    return r.json()


# ── Import rule 1: reject what is not a hand-off, in plain language ──────────
@pytest.mark.parametrize("kind,needle", [
    ("wrong_format", "not a Capability Compass hand-off file"),
    ("missing_key", "no engagement key"),
    ("dangling_cluster", "CAP-99"),
])
async def test_broken_packets_are_refused_and_write_nothing(api_client, async_session, kind, needle):
    before = await _counts(async_session)
    pv = (await api_client.post("/api/v1/compass/preview", json={"packet": broken(kind)})).json()
    assert pv["ok"] is False
    assert any(needle in e for e in pv["errors"]), pv["errors"]
    ap = await api_client.post("/api/v1/compass/apply", json={"packet": broken(kind)})
    assert ap.status_code == 422
    assert needle in ap.json()["detail"]
    assert await _counts(async_session) == before  # nothing created


async def test_not_json_object_is_refused(api_client):
    for bad in (None, "hello", [1, 2]):
        pv = (await api_client.post("/api/v1/compass/preview", json={"packet": bad})).json()
        assert pv["ok"] is False and pv["errors"]


async def test_any_1x_accepted_unknown_fields_ignored_2x_refused(api_client):
    p = copy.deepcopy(SAMPLE)
    p["format_version"] = "1.7"
    p["brand_new_field"] = {"anything": True}
    p["for_apps"]["workbench"]["roles"][0]["future_flag"] = 1
    assert (await api_client.post("/api/v1/compass/preview", json={"packet": p})).json()["ok"] is True
    p["format_version"] = "2.0"
    pv = (await api_client.post("/api/v1/compass/preview", json={"packet": p})).json()
    assert pv["ok"] is False and "1.x" in pv["errors"][0]


# ── Import rule 2: preview first, nothing applied until confirmed ────────────
async def test_preview_writes_nothing_and_shows_matches_near_and_misses(api_client, async_session):
    eng_id, _ = await _engagement_with_org(api_client)
    before = await _counts(async_session)
    pv = (await api_client.post("/api/v1/compass/preview",
                                json={"packet": SAMPLE, "engagement_id": eng_id})).json()
    assert pv["ok"] is True
    assert await _counts(async_session) == before
    assert pv["engagement"]["action"] == "update" and pv["engagement"]["key"] == "MERIDIAN"
    by_ref = {r["ref"]: r for r in pv["roles"]}
    assert len(by_ref) == 12  # the list written for this app, in packet order
    assert [r["ref"] for r in pv["roles"]][:3] == ["RL-001", "RL-002", "RL-007"]
    # exact match
    assert by_ref["RL-001"]["match_state"] == "matched"
    assert by_ref["RL-001"]["matched_job_title"] == "Regional VP Cargo"
    assert by_ref["RL-001"]["positions"] == 2
    assert by_ref["RL-009"]["match_state"] == "matched"
    # near-match: suggested, NOT applied
    assert by_ref["RL-007"]["match_state"] == "near"
    assert by_ref["RL-007"]["matched_job_title"] is None
    assert "Head of Analytics and AI" in by_ref["RL-007"]["candidates"]
    # miss + absent ("no one in the seat")
    assert by_ref["RL-015"]["match_state"] == "missed"
    assert by_ref["RL-011"]["match_state"] == "absent"
    assert by_ref["RL-011"]["cluster_name"] == "Commercial Leadership"


async def test_readiness_false_warns_but_does_not_block(api_client):
    p = copy.deepcopy(SAMPLE)
    p["readiness"] = {"ready": False, "verdict": "Not ready", "open": ["Two cells unscored"]}
    pv = (await api_client.post("/api/v1/compass/preview", json={"packet": p})).json()
    assert pv["ok"] is True
    assert any("NOT ready" in w and "Two cells unscored" in w for w in pv["warnings"])
    assert (await api_client.post("/api/v1/compass/apply", json={"packet": p})).status_code == 200


# ── Import rule 4 + A: create/update, keep the key and every Compass ref ─────
async def test_apply_creates_engagement_and_keeps_ids_exactly(api_client, async_session):
    res = await _import(api_client)  # no engagement chosen -> created from the packet
    eng = await async_session.get(Engagement, res["engagement_id"])
    assert eng.name == "MERIDIAN Meridian Group (fictional demo)" and eng.compass_key == "MERIDIAN"
    client = await async_session.get(Client, eng.client_id)
    assert client.name == "Meridian Group (fictional demo)"
    roles = list(await async_session.scalars(
        select(CompassRole).where(CompassRole.engagement_id == eng.id).order_by(CompassRole.seq)))
    want = SAMPLE["for_apps"]["workbench"]["roles"]
    assert [(r.ref, r.title, r.cluster_ref, r.route, r.status) for r in roles] == \
        [(w["ref"], w["title"], w["cluster_ref"], w["route"], w["status"]) for w in want]
    # detail enriched from the top-level roles[]
    rl2 = next(r for r in roles if r.ref == "RL-002")
    assert rl2.criticality_index == 4.6 and rl2.tacit_intensity == 4.5
    # The two charter lists are stored (only stored) for the later OS module.
    pk = eng.compass_packet
    assert [c["ref"] for c in pk["reference_model"]] == [f"C{i}" for i in range(1, 9)]
    assert [c["ref"] for c in pk["leapfrog_gate"]] == [f"LG-{i}" for i in range(1, 6)]
    # Rule 6: only the whitelisted subset is kept — no thesis text, no evidence, nothing key-like.
    blob = json.dumps(pk).lower()
    assert "api_key" not in blob and "thesis" not in blob and "rationale" not in blob
    # listed by the API with its key
    listed = (await api_client.get("/api/v1/engagements")).json()
    assert listed[0]["compass_key"] == "MERIDIAN"
    # importing the same key again updates rather than duplicating
    again = await _import(api_client)
    assert again["engagement_id"] == res["engagement_id"]
    assert await async_session.scalar(select(func.count(Engagement.id))) == 1


async def test_near_match_only_applied_when_consultant_chooses(api_client, async_session):
    eng_id, ds_id = await _engagement_with_org(api_client)
    await _import(api_client, eng_id)
    st = (await api_client.get(f"/api/v1/compass/{eng_id}")).json()
    by_ref = {r["ref"]: r for r in st["roles"]}
    assert st["imported"] is True and st["key"] == "MERIDIAN"
    assert by_ref["RL-007"]["matched_job_title"] is None  # never guessed silently
    assert by_ref["RL-007"]["match_state"] == "missed"
    assert "Head of Analytics and AI" in by_ref["RL-007"]["candidates"]
    assert by_ref["RL-011"]["seat"] == "no one in the seat"
    assert by_ref["RL-001"]["positions"] == 2
    # the consultant corrects it
    r = await api_client.put(f"/api/v1/compass/{eng_id}/roles/RL-007",
                             json={"job_title": "Head of Analytics and AI"})
    assert r.status_code == 200 and r.json()["match_state"] == "manual"
    # or confirms matches at import time
    await _import(api_client, eng_id, matches={"RL-007": "Head of Analytics and AI", "RL-001": None})
    by_ref = {r["ref"]: r for r in (await api_client.get(f"/api/v1/compass/{eng_id}")).json()["roles"]}
    assert by_ref["RL-007"]["match_state"] == "manual"
    assert by_ref["RL-001"]["matched_job_title"] is None and by_ref["RL-001"]["match_state"] == "missed"
    assert (await api_client.put(f"/api/v1/compass/{eng_id}/roles/RL-999",
                                 json={"job_title": "x"})).status_code == 404


# ── Import rule 3: never overwrite what was typed without asking ─────────────
async def test_reimport_keeps_typed_name_and_manual_matches(api_client, async_session):
    eng_id, _ = await _engagement_with_org(api_client, name="My own engagement name")
    pv = (await api_client.post("/api/v1/compass/preview",
                                json={"packet": SAMPLE, "engagement_id": eng_id})).json()
    assert any(a["field"] == "overwrite_name" for a in pv["asks"])
    await _import(api_client, eng_id)
    eng = await async_session.get(Engagement, eng_id)
    assert eng.name == "My own engagement name"  # kept
    await api_client.put(f"/api/v1/compass/{eng_id}/roles/RL-015", json={"job_title": "Group CEO"})
    await _import(api_client, eng_id)  # re-import
    role = await async_session.scalar(select(CompassRole).where(
        CompassRole.engagement_id == eng_id, CompassRole.ref == "RL-015"))
    assert role.matched_job_title == "Group CEO" and role.match_state == "manual"
    await _import(api_client, eng_id, overwrite_name=True)  # only when asked
    await async_session.refresh(eng)
    assert eng.name == "MERIDIAN Meridian Group (fictional demo)"


async def test_key_change_needs_confirmation(api_client, async_session):
    eng_id, _ = await _engagement_with_org(api_client)
    await _import(api_client, eng_id)
    other = copy.deepcopy(SAMPLE)
    other["engagement"]["key"] = "ORION"
    r = await api_client.post("/api/v1/compass/apply", json={"packet": other, "engagement_id": eng_id})
    assert r.status_code == 422 and "MERIDIAN" in r.json()["detail"]
    r = await api_client.post("/api/v1/compass/apply", json={
        "packet": other, "engagement_id": eng_id, "confirm_key_change": True})
    assert r.status_code == 200 and r.json()["key"] == "ORION"


# ── B: shared IDs ────────────────────────────────────────────────────────────
async def test_task_codes_are_minted_and_never_reused(api_client, async_session, mock_claude):
    mock_claude.set_text(json.dumps({"extractions": [
        {"employee_key": "M007", "tasks": ["Reconcile ledgers"]},
        {"employee_key": "M005", "tasks": ["Run workarounds", "Coach colleagues"]},
        {"employee_key": "M002", "tasks": ["Plan trade lanes"]},
    ]}))
    eng_id, ds_id = await _engagement_with_org(api_client)
    await _import(api_client, eng_id)
    await api_client.post("/api/v1/task-intel/extract", params={"dataset_id": ds_id})
    rows = (await async_session.execute(
        select(Task.code, Position.employee_key).join(Position, Task.position_id == Position.id)
        .order_by(Task.code))).all()
    first = [c for c, _ in rows]
    assert first == ["T-001", "T-002", "T-003", "T-004"]
    # Compass priority roles are worked first: RL-001 (M002), then RL-009 (M005), others after.
    assert [k for _, k in rows] == ["M002", "M005", "M005", "M007"]
    # Re-extract replaces the tasks: the new tasks get NEW codes; old codes are never reused.
    await api_client.post("/api/v1/task-intel/extract", params={"dataset_id": ds_id})
    async_session.expire_all()
    second = sorted(t.code for t in await async_session.scalars(select(Task)))
    assert second == ["T-005", "T-006", "T-007", "T-008"]
    listed = (await api_client.get("/api/v1/task-intel/tasks", params={"dataset_id": ds_id})).json()
    assert second[0] in json.dumps(listed)


async def test_step_carries_process_map_studio_id(api_client, async_session):
    eng_id, ds_id = await _engagement_with_org(api_client)
    tasks = await _seed_tasks(async_session, ds_id)
    pid = (await api_client.post("/api/v1/workflows", json={
        "engagement_id": eng_id, "name": "Bid to contract renewal"})).json()["id"]
    s1 = (await api_client.post(f"/api/v1/workflows/{pid}/steps",
                                json={"name": "Qualify", "pms_step_id": "s-04"})).json()
    assert s1["pms_step_id"] == "S-04"
    s2 = (await api_client.post(f"/api/v1/workflows/{pid}/steps", json={"name": "Price"})).json()
    assert s2["pms_step_id"] is None  # optional
    bad = await api_client.patch(f"/api/v1/workflows/steps/{s2['id']}", json={"pms_step_id": "X1"})
    assert bad.status_code == 422 and "S-04" in bad.json()["detail"]  # never mint a foreign prefix
    ok = await api_client.patch(f"/api/v1/workflows/steps/{s2['id']}", json={"pms_step_id": "S-05"})
    assert ok.json()["pms_step_id"] == "S-05"
    steps = (await api_client.get(f"/api/v1/workflows/{pid}/steps")).json()["steps"]
    assert [s["pms_step_id"] for s in steps] == ["S-04", "S-05"]
    await api_client.post(f"/api/v1/workflows/steps/{s1['id']}/map-tasks",
                          json={"task_ids": [tasks["acct_aug"].id]})
    rows = list(csv.DictReader(io.StringIO((await api_client.get(
        "/api/v1/workflows/export.csv", params={"engagement_id": eng_id, "dataset_id": ds_id})).text)))
    assert rows[0]["pms_step_id"] == "S-04" and rows[0]["task_code"].startswith("T-")
    assert rows[0]["grade"] == "indicated"
    cleared = await api_client.patch(f"/api/v1/workflows/steps/{s2['id']}", json={"pms_step_id": ""})
    assert cleared.json()["pms_step_id"] is None


# ── C: shared grade ──────────────────────────────────────────────────────────
def test_shared_grade_rules():
    now = datetime.utcnow()
    g = shared_grade
    # unreviewed AI output -> Hypothesis, whatever the confidence
    assert g(source="model-inferred", confidence=0.95, review_state="unreviewed") == "hypothesis"
    assert g(source="WORKBank", confidence=0.4, review_state="unreviewed") == "hypothesis"
    assert g(source="model-inferred", confidence=0.9, review_state="rejected") == "hypothesis"
    # auto-routed "approved" that no person has seen: AI output or <0.70 stays Hypothesis
    assert g(source="model-inferred", confidence=0.9, review_state="approved") == "hypothesis"
    assert g(source="SFw", confidence=0.6, review_state="approved") == "hypothesis"
    assert g(source="SFw", confidence=0.9, review_state="approved") == "indicated"
    # approved in the Validation Queue -> Indicated
    assert g(source="model-inferred", confidence=0.5, review_state="approved", reviewed_at=now) == "indicated"
    assert g(source="consultant-approved", confidence=1.0, review_state="approved") == "indicated"
    # only the consultant raises it to Confirmed — and only on reviewed content
    assert g(source="model-inferred", confidence=0.5, review_state="approved", reviewed_at=now,
             grade_override="confirmed") == "confirmed"
    assert g(source="model-inferred", confidence=0.99, review_state="unreviewed",
             grade_override="confirmed") == "hypothesis"
    assert weakest(["confirmed", "indicated"]) == "indicated"
    assert weakest(["confirmed", "hypothesis", "indicated"]) == "hypothesis"


async def test_queue_shows_grade_and_consultant_can_raise_to_confirmed(api_client, async_session):
    eng_id, ds_id = await _engagement_with_org(api_client)
    tasks = await _seed_tasks(async_session, ds_id)
    q = (await api_client.get("/api/v1/validation/queue", params={"dataset_id": ds_id})).json()
    item = next(i for i in q["items"] if i["task_id"] == tasks["cargo_unrev"].id)
    assert item["grade"] == "hypothesis" and item["task_code"].startswith("T-")
    # a Hypothesis cannot be raised without review
    r = await api_client.post("/api/v1/validation/grade", json={
        "kind": "ai_score", "id": item["id"], "grade": "confirmed"})
    assert r.status_code == 409
    await api_client.post("/api/v1/validation/review", json=[
        {"kind": "ai_score", "id": item["id"], "action": "approve"}])
    q = (await api_client.get("/api/v1/validation/queue", params={
        "dataset_id": ds_id, "include_reviewed": True})).json()
    item = next(i for i in q["items"] if i["task_id"] == tasks["cargo_unrev"].id)
    assert item["grade"] == "indicated"
    r = await api_client.post("/api/v1/validation/grade", json={
        "kind": "ai_score", "id": item["id"], "grade": "confirmed"})
    assert r.status_code == 200 and r.json()["grade"] == "confirmed"
    r = await api_client.post("/api/v1/validation/grade", json={
        "kind": "ai_score", "id": item["id"], "grade": "indicated"})
    assert r.json()["grade"] == "indicated"
    assert (await api_client.post("/api/v1/validation/grade", json={
        "kind": "ai_score", "id": "nope", "grade": "confirmed"})).status_code == 404
    assert (await api_client.post("/api/v1/validation/grade", json={
        "kind": "ai_score", "id": item["id"], "grade": "certain"})).status_code == 400


# ── A: ordering, route badge, tacit-knowledge warning ────────────────────────
async def test_board_offers_compass_roles_first_with_route_and_warning(api_client, async_session):
    eng_id, ds_id = await _engagement_with_org(api_client)
    tasks = await _seed_tasks(async_session, ds_id)
    await _import(api_client, eng_id)
    pid = (await api_client.post("/api/v1/workflows", json={
        "engagement_id": eng_id, "name": "Roster to shift cover"})).json()["id"]
    board = (await api_client.get(f"/api/v1/workflows/{pid}/board", params={"dataset_id": ds_id})).json()
    by_id = {t["id"]: t for t in board["unmapped"]}
    # Compass roles first, in packet order (RL-001 cargo, RL-009 super-user, RL-014 accounts), others last.
    refs = [t["compass_ref"] for t in board["unmapped"]]
    assert refs == sorted(refs, key=lambda r: (r is None, r or ""))
    assert refs[-1] is None and board["unmapped"][-1]["role"] == "Finance Analyst"
    sup = by_id[tasks["super_auto"].id]
    assert (sup["compass_ref"], sup["compass_route"], sup["compass_cluster_ref"]) == \
        ("RL-009", "specialist", "CAP-03")
    assert sup["code"].startswith("T-") and sup["grade"] == "indicated"
    # specialist + H2 -> warning; specialist + H5 -> none; dual + H1 -> warning; dual + H3 -> none
    assert "tacit" in sup["tacit_warning"].lower() and "H2" in sup["tacit_warning"]
    assert by_id[tasks["super_human"].id]["tacit_warning"] is None
    assert by_id[tasks["cargo_auto"].id]["tacit_warning"]
    assert by_id[tasks["acct_aug"].id]["tacit_warning"] is None
    # not a Compass role -> no badge, no warning even at H1
    fin = by_id[tasks["fin_auto"].id]
    assert fin["compass_ref"] is None and fin["tacit_warning"] is None
    # the same warning reaches the Validation Queue and the org roll-up
    q = (await api_client.get("/api/v1/validation/queue", params={"dataset_id": ds_id})).json()
    unrev = next(i for i in q["items"] if i["task_id"] == tasks["cargo_unrev"].id)
    assert unrev["compass_route"] == "dual" and unrev["tacit_warning"]
    roll = (await api_client.get("/api/v1/task-intel/org-rollup", params={"dataset_id": ds_id})).json()
    node = next(n for n in roll["nodes"] if n["employee_key"] == "M005")
    assert node["compass_ref"] == "RL-009" and node["compass_route"] == "specialist"
    assert any(t["tacit_warning"] for t in node["tasks"]) and all(t["code"] for t in node["tasks"])


async def test_absent_roles_are_listed_not_analysed(api_client, async_session):
    eng_id, ds_id = await _engagement_with_org(api_client)
    await _seed_tasks(async_session, ds_id)
    await _import(api_client, eng_id)
    st = (await api_client.get(f"/api/v1/compass/{eng_id}", params={"dataset_id": ds_id})).json()
    absent = [r for r in st["roles"] if r["status"] == "absent"]
    assert len(absent) == 5
    assert all(r["seat"] == "no one in the seat" and r["tasks"] == 0 and r["positions"] == 0
               for r in absent)
    assert next(r for r in st["roles"] if r["ref"] == "RL-009")["tasks"] == 2


# ── D: the return file ───────────────────────────────────────────────────────
async def test_return_file_shape_grades_and_privacy(api_client, async_session):
    eng_id, ds_id = await _engagement_with_org(api_client)
    tasks = await _seed_tasks(async_session, ds_id)
    await _import(api_client, eng_id)
    resp = await api_client.get(f"/api/v1/compass/{eng_id}/return.json", params={"dataset_id": ds_id})
    assert resp.status_code == 200
    assert "meridian_compass_return.json" in resp.headers["content-disposition"]
    pkt = resp.json()
    assert set(pkt) == {"format", "format_version", "generated_at", "source_app", "engagement_key",
                        "findings"}  # exactly the agreed shape
    assert (pkt["format"], pkt["format_version"], pkt["engagement_key"]) == \
        ("compass-return", "1.0", "MERIDIAN")
    for f in pkt["findings"]:
        assert set(f) == {"ref", "kind", "title", "detail", "grade", "figure", "relates_to",
                          "source_note"}
        assert f["grade"] in {"confirmed", "indicated", "hypothesis"}
        assert f["kind"] in {"task_disposition", "role_impact", "capacity"}
    disp = {f["title"]: f for f in pkt["findings"] if f["kind"] == "task_disposition"}
    # export-block rule stays: the unreviewed model-inferred task is NOT in the file
    assert "Draft regional cargo strategy memo" not in disp
    assert len(disp) == 5 and all(f["ref"].startswith("T-") for f in disp.values())
    sup = disp["Run month-end reconciliation workarounds"]
    assert sup["relates_to"] == ["RL-009", "CAP-03"] and sup["grade"] == "indicated"
    assert "H2" in sup["detail"] and "AI capability 0.80" in sup["detail"]
    assert "Worker desire 0.50" in sup["detail"] and "Green light" in sup["detail"]
    assert "Warning" in sup["detail"]
    assert disp["Reconcile ledgers against bank statements"]["relates_to"] == []
    roles = {f["ref"]: f for f in pkt["findings"] if f["kind"] == "role_impact"}
    assert set(roles) == {"RL-001", "RL-009", "RL-014"}  # matched roles with reviewed evidence only
    assert roles["RL-009"]["relates_to"] == ["RL-009", "CAP-03"]
    assert "1 suited to automation" in roles["RL-009"]["detail"]
    cap = {f["ref"]: f for f in pkt["findings"] if f["kind"] == "capacity"}
    assert cap["RL-009"]["figure"] == "0.5 FTE (estimate)"  # 1 person x 1 of 2 reviewed tasks
    assert cap["RL-001"]["figure"] == "2.0 FTE (estimate)"  # 2 people x 1 of 1 reviewed task
    assert all(f["grade"] == "hypothesis" for f in cap.values())  # an estimate never decides alone
    assert "RL-014" not in cap  # nothing at H1-H2
    # privacy: no names of individual people, no key material
    text = (await api_client.get(f"/api/v1/compass/{eng_id}/return.txt",
                                 params={"dataset_id": ds_id})).text
    for blob in (resp.text, text):
        assert not any(n in blob for n in REAL_NAMES)
        assert "api_key" not in blob.lower() and "sk-ant" not in blob
    assert "MERIDIAN:RL-009" in text and "TASK DISPOSITIONS (5)" in text
    assert "1 task(s) are left out" in text and "No one in the seat" in text
    # raising a task to Confirmed travels in the file; the role roll-up stays capped at Indicated
    score = await async_session.scalar(
        select(TaskAIScore).where(TaskAIScore.task_id == tasks["super_auto"].id))
    await api_client.post("/api/v1/validation/grade", json={
        "kind": "ai_score", "id": score.id, "grade": "confirmed"})
    pkt = (await api_client.get(f"/api/v1/compass/{eng_id}/return.json",
                                params={"dataset_id": ds_id})).json()
    f = next(f for f in pkt["findings"] if f["title"] == "Run month-end reconciliation workarounds")
    assert f["grade"] == "confirmed"
    assert next(f for f in pkt["findings"]
                if f["kind"] == "role_impact" and f["ref"] == "RL-009")["grade"] == "indicated"


async def test_return_file_is_a_deliverable_and_respects_anonymisation(api_client, async_session,
                                                                       tmp_path, monkeypatch):
    from app.services import deliverable_service
    monkeypatch.setattr(deliverable_service, "OUTPUT_DIR", tmp_path)
    eng_id, ds_id = await _engagement_with_org(api_client, anonymized=True)
    await _seed_tasks(async_session, ds_id)
    await _import(api_client, eng_id)
    pseudonyms = [p.pseudonym for p in await async_session.scalars(
        select(Position).where(Position.dataset_id == ds_id)) if p.pseudonym]
    assert pseudonyms
    types = (await api_client.get("/api/v1/deliverables/types")).json()["types"]
    assert {"COMPASS_RETURN_JSON", "COMPASS_RETURN_TXT"} <= set(types)
    for dtype, ext in (("COMPASS_RETURN_JSON", ".json"), ("COMPASS_RETURN_TXT", ".txt")):
        gen = await api_client.post("/api/v1/deliverables/generate", params={
            "engagement_id": eng_id, "type": dtype, "dataset_id": ds_id})
        assert gen.status_code == 200, gen.text
        body = Path(gen.json()["file_path"]).read_text(encoding="utf-8")
        assert gen.json()["file_path"].endswith(ext) and "MERIDIAN" in body
        assert not any(n in body for n in REAL_NAMES + pseudonyms)
        dl = await api_client.get(f"/api/v1/deliverables/{gen.json()['id']}/download")
        assert dl.status_code == 200


# ── Standalone: the app must work with no packet at all ──────────────────────
async def test_standalone_without_any_compass_packet(api_client, async_session):
    eng_id, ds_id = await _engagement_with_org(api_client, name="Standalone")
    tasks = await _seed_tasks(async_session, ds_id)
    st = (await api_client.get(f"/api/v1/compass/{eng_id}")).json()
    assert st["imported"] is False and st["roles"] == [] and st["key"] is None
    assert (await api_client.get("/api/v1/engagements")).json()[0]["compass_key"] is None
    pid = (await api_client.post("/api/v1/workflows", json={
        "engagement_id": eng_id, "name": "P"})).json()["id"]
    step = (await api_client.post(f"/api/v1/workflows/{pid}/steps", json={"name": "S"})).json()
    board = (await api_client.get(f"/api/v1/workflows/{pid}/board", params={"dataset_id": ds_id})).json()
    assert len(board["unmapped"]) == 6
    assert all(t["compass_ref"] is None and t["tacit_warning"] is None for t in board["unmapped"])
    assert all(t["code"].startswith("T-") and t["grade"] for t in board["unmapped"])  # IDs/grades still work
    await api_client.post(f"/api/v1/workflows/steps/{step['id']}/map-tasks",
                          json={"task_ids": [tasks["fin_auto"].id]})
    header = (await api_client.get("/api/v1/workflows/export.csv", params={
        "engagement_id": eng_id, "dataset_id": ds_id})).text.splitlines()[0].split(",")
    assert header[:13] == ["process", "value_stream", "step_seq", "step_name", "task_text", "role",
                           "department", "human_agency_level", "has_level", "zone",
                           "ai_opportunity_level", "review_state", "source"]  # old columns unmoved
    pkt = (await api_client.get(f"/api/v1/compass/{eng_id}/return.json")).json()
    assert pkt["engagement_key"] == "" and pkt["format"] == "compass-return"
    assert all(f["relates_to"] == [] and f["kind"] == "task_disposition" for f in pkt["findings"])
    assert (await api_client.get("/api/v1/compass/nope")).status_code == 404
    assert (await api_client.get("/api/v1/compass/nope/return.json")).status_code == 404


async def test_delete_engagement_removes_compass_roles(api_client, async_session):
    eng_id, _ = await _engagement_with_org(api_client)
    await _import(api_client, eng_id)
    assert await async_session.scalar(select(func.count(CompassRole.id))) == 12
    assert (await api_client.delete(f"/api/v1/engagements/{eng_id}")).status_code == 200
    assert await async_session.scalar(select(func.count(CompassRole.id))) == 0


async def test_compass_routes_are_behind_the_login(anon_client):
    assert (await anon_client.post("/api/v1/compass/preview", json={"packet": SAMPLE})).status_code == 401
    assert (await anon_client.get("/api/v1/compass/x/return.json")).status_code == 401


async def test_import_is_audited(api_client):
    res = await _import(api_client)
    events = (await api_client.get("/api/v1/audit", params={"engagement_id": res["engagement_id"]})).json()
    assert "compass_imported" in json.dumps(events)
