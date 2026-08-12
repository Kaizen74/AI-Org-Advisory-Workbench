"""D32 — export the finalized workflow as CSV (mapped task→step→process) and as a PPTX deck."""
from __future__ import annotations

import csv
import io

from sqlalchemy import select

from app.models import Task
from tests.test_workflow_board import _setup


async def test_export_csv_and_pptx(api_client, async_session, monkeypatch):
    eng_id, ds_id = await _setup(api_client, async_session, monkeypatch)
    p = (await api_client.post("/api/v1/workflows",
                               json={"engagement_id": eng_id, "name": "Cargo", "value_stream": "Ops"})).json()
    pid = p["id"]
    s1 = (await api_client.post(f"/api/v1/workflows/{pid}/steps", json={"name": "Acceptance"})).json()
    tids = [t.id for t in await async_session.scalars(select(Task))]
    await api_client.post(f"/api/v1/workflows/steps/{s1['id']}/map-tasks", json={"task_ids": tids[:2]})

    # CSV export: header + one row per mapped task, carrying process/step/role/H-band.
    csv_resp = await api_client.get("/api/v1/workflows/export.csv",
                                    params={"engagement_id": eng_id, "dataset_id": ds_id})
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]
    rows = list(csv.DictReader(io.StringIO(csv_resp.text)))
    assert len(rows) == 2
    r0 = rows[0]
    assert r0["process"] == "Cargo" and r0["value_stream"] == "Ops"
    assert r0["step_name"] == "Acceptance" and r0["task_text"]
    for col in ("role", "human_agency_level", "zone", "ai_opportunity_level", "review_state", "source"):
        assert col in r0

    # PPTX export: a valid Office/zip file that VISUALLY renders the process + step names as shapes.
    ppt = await api_client.get("/api/v1/workflows/export.pptx",
                               params={"engagement_id": eng_id, "dataset_id": ds_id})
    assert ppt.status_code == 200
    assert "presentationml" in ppt.headers["content-type"]
    assert ppt.content[:2] == b"PK"
    import io as _io

    from pptx import Presentation
    prs = Presentation(_io.BytesIO(ppt.content))
    texts = [sh.text_frame.text for s in prs.slides for sh in s.shapes if sh.has_text_frame]
    blob = "\n".join(texts)
    assert "Cargo" in blob and "Acceptance" in blob  # process + step drawn as board shapes
    assert any(t.startswith("Mapped 2 / ") for t in texts)  # board footer summary


async def test_export_csv_empty_when_nothing_mapped(api_client, async_session, monkeypatch):
    eng_id, ds_id = await _setup(api_client, async_session, monkeypatch)
    await api_client.post("/api/v1/workflows", json={"engagement_id": eng_id, "name": "Empty"})
    csv_resp = await api_client.get("/api/v1/workflows/export.csv",
                                    params={"engagement_id": eng_id, "dataset_id": ds_id})
    assert csv_resp.status_code == 200
    rows = list(csv.DictReader(io.StringIO(csv_resp.text)))
    assert rows == []  # header only, no mapped tasks


# ── D48 — Landscape & Roll-up exports mirror the on-screen views ─────────────────────────────
async def test_landscape_export_csv_and_pptx(api_client, async_session, monkeypatch):
    eng_id, ds_id = await _setup(api_client, async_session, monkeypatch)

    csv_resp = await api_client.get("/api/v1/workflows/landscape.csv",
                                    params={"dataset_id": ds_id})
    assert csv_resp.status_code == 200
    rows = list(csv.DictReader(io.StringIO(csv_resp.text)))
    # One row per plotted dot — exactly the fields the on-screen scatter encodes.
    assert rows, "capability-scored tasks should plot"
    for col in ("task_text", "role", "human_agency_level", "capability_score",
                "desire_score", "workbank_quadrant", "zone", "review_state", "source"):
        assert col in rows[0]
    for r in rows:
        assert 0.0 <= float(r["capability_score"]) <= 1.0
        assert r["role"] in {"Director", "Cargo Officer", "Unassigned"}  # job title, never a name
        # Quadrant agrees with the UI's 0.5-split grid ('' = desire not captured → hollow dot).
        if r["desire_score"] == "":
            assert r["workbank_quadrant"] == ""
        else:
            cap, des = float(r["capability_score"]), float(r["desire_score"])
            expect = ("Green Light — automate" if des >= 0.5 else "Red Light — caution") \
                if cap >= 0.5 else ("R&D Opportunity" if des >= 0.5 else "Low Priority")
            assert r["workbank_quadrant"] == expect

    ppt = await api_client.get("/api/v1/workflows/landscape.pptx",
                               params={"dataset_id": ds_id})
    assert ppt.status_code == 200 and ppt.content[:2] == b"PK"
    import io as _io

    from pptx import Presentation
    prs = Presentation(_io.BytesIO(ppt.content))
    blob = "\n".join(sh.text_frame.text for s in prs.slides
                     for sh in s.shapes if sh.has_text_frame)
    assert "AI opportunity landscape" in blob
    # The four WORKBank quadrant labels are drawn on the plot (D47 orientation).
    for label in ("GREEN LIGHT — AUTOMATE", "RED LIGHT — CAUTION",
                  "R&D OPPORTUNITY", "LOW PRIORITY"):
        assert label in blob


async def test_landscape_export_reviewed_only_filter(api_client, async_session, monkeypatch):
    _, ds_id = await _setup(api_client, async_session, monkeypatch)
    csv_resp = await api_client.get("/api/v1/workflows/landscape.csv",
                                    params={"dataset_id": ds_id, "reviewed_only": "true"})
    assert csv_resp.status_code == 200
    rows = list(csv.DictReader(io.StringIO(csv_resp.text)))
    assert all(r["review_state"] == "approved" for r in rows)  # nothing approved yet → header only


async def test_rollup_export_csv_and_pptx(api_client, async_session, monkeypatch):
    _, ds_id = await _setup(api_client, async_session, monkeypatch)

    csv_resp = await api_client.get("/api/v1/workflows/rollup.csv",
                                    params={"dataset_id": ds_id})
    assert csv_resp.status_code == 200
    rows = list(csv.DictReader(io.StringIO(csv_resp.text)))
    assert len(rows) == 2  # Director + Cargo Officer
    # Depth-first, on-screen order: the root first, its report indented one level beneath it.
    assert rows[0]["role"] == "Director" and rows[0]["depth"] == "0"
    assert rows[1]["role"] == "Cargo Officer" and rows[1]["depth"] == "1"
    # Own vs team: the head's team count rolls up their whole line (own + every report's tasks).
    assert int(rows[0]["team_tasks"]) == int(rows[0]["own_tasks"]) + int(rows[1]["team_tasks"])
    assert int(rows[0]["total_reports"]) == 1
    for col in ("rollup_index", "reviewed_pct", "H0", "H1", "H2", "H3", "H4", "H5"):
        assert col in rows[0]
    # Role identity only — never a real name (privacy posture, same rule as the workflow CSV).
    assert "Boss" not in csv_resp.text and "Cargo Joe" not in csv_resp.text

    ppt = await api_client.get("/api/v1/workflows/rollup.pptx",
                               params={"dataset_id": ds_id})
    assert ppt.status_code == 200 and ppt.content[:2] == b"PK"
    import io as _io

    from pptx import Presentation
    prs = Presentation(_io.BytesIO(ppt.content))
    blob = "\n".join(sh.text_frame.text for s in prs.slides
                     for sh in s.shapes if sh.has_text_frame)
    assert "Org-hierarchy AI roll-up" in blob
    assert "Director" in blob and "Cargo Officer" in blob
    assert "Boss" not in blob and "Cargo Joe" not in blob
    assert "Org index" in blob


# ── D49 — visual parity: the deck must carry what the on-screen card/plot/row shows ───────────
async def test_flow_deck_carries_card_zone_review_and_unmapped_tray(api_client, async_session,
                                                                    monkeypatch):
    """The Flow board on screen shows, per card, the zone chip + review dot, a per-step task count,
    and an 'Unmapped tasks' tray column. The deck mirror must carry all four."""
    eng_id, ds_id = await _setup(api_client, async_session, monkeypatch)
    p = (await api_client.post("/api/v1/workflows",
                               json={"engagement_id": eng_id, "name": "Cargo",
                                     "value_stream": "Ops"})).json()
    s1 = (await api_client.post(f"/api/v1/workflows/{p['id']}/steps",
                                json={"name": "Acceptance"})).json()
    tids = [t.id for t in await async_session.scalars(select(Task))]
    await api_client.post(f"/api/v1/workflows/steps/{s1['id']}/map-tasks",
                          json={"task_ids": tids[:2]})

    ppt = await api_client.get("/api/v1/workflows/export.pptx",
                               params={"engagement_id": eng_id, "dataset_id": ds_id})
    import io as _io

    from pptx import Presentation
    prs = Presentation(_io.BytesIO(ppt.content))
    texts = [sh.text_frame.text for s in prs.slides for sh in s.shapes if sh.has_text_frame]
    blob = "\n".join(texts)
    assert any("Unmapped tasks" in t for t in texts), "the tray column is part of the Flow visual"
    # Step header carries its card count, like the column header on screen.
    assert any(t.startswith("1.") and "Acceptance" in t and "2" in t for t in texts)
    # Cards carry the zone chip + review state the on-screen card shows.
    assert "Red light" in blob or "Green light" in blob or "Robotics lever" in blob
    assert "unreviewed" in blob.lower() or "approved" in blob.lower()


async def test_landscape_export_honours_agency_band_filter(api_client, async_session, monkeypatch):
    """The Landscape plots only the Agency bands left switched on; the export must match the
    filtered picture, not the unfiltered dataset."""
    _, ds_id = await _setup(api_client, async_session, monkeypatch)
    everything = list(csv.DictReader(io.StringIO(
        (await api_client.get("/api/v1/workflows/landscape.csv",
                              params={"dataset_id": ds_id})).text)))
    bands_present = {r["human_agency_level"] for r in everything}
    keep = sorted(bands_present)[0]
    filtered = list(csv.DictReader(io.StringIO(
        (await api_client.get("/api/v1/workflows/landscape.csv",
                              params={"dataset_id": ds_id, "bands": keep})).text)))
    assert filtered, "the kept band should still plot"
    assert {r["human_agency_level"] for r in filtered} == {keep}
    assert len(filtered) <= len(everything)


async def test_rollup_org_index_matches_the_on_screen_formula(api_client, async_session,
                                                              monkeypatch):
    """The Roll-up's org-wide index sums every position's OWN bands once (the UI's formula), so it
    stays correct even when a malformed reporting line leaves nodes outside the root forest."""
    from app.services.deliverable_builders import has_index
    from app.services.task_intelligence_service import org_rollup

    _, ds_id = await _setup(api_client, async_session, monkeypatch)
    rollup = await org_rollup(async_session, ds_id)
    own_bands: dict = {}
    for n in rollup["nodes"]:
        for b, c in n["self_bands"].items():
            own_bands[b] = own_bands.get(b, 0) + c
    expected = has_index(own_bands)

    ppt = await api_client.get("/api/v1/workflows/rollup.pptx", params={"dataset_id": ds_id})
    import io as _io

    from pptx import Presentation
    prs = Presentation(_io.BytesIO(ppt.content))
    blob = "\n".join(sh.text_frame.text for s in prs.slides
                     for sh in s.shapes if sh.has_text_frame)
    assert f"Org index  {expected}/100" in blob
    # The org-wide stat cards from the top of the Roll-up view travel with the deck (the deck
    # renders the labels upper-cased, as the on-screen cards do via their `uppercase` styling).
    for card in ("People", "Reporting layers", "AI-amenable tasks", "Reviewed"):
        assert card.upper() in blob.upper()
