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

    # PPTX export: a valid Office/zip file.
    ppt = await api_client.get("/api/v1/workflows/export.pptx",
                               params={"engagement_id": eng_id, "dataset_id": ds_id})
    assert ppt.status_code == 200
    assert "presentationml" in ppt.headers["content-type"]
    assert ppt.content[:2] == b"PK"


async def test_export_csv_empty_when_nothing_mapped(api_client, async_session, monkeypatch):
    eng_id, ds_id = await _setup(api_client, async_session, monkeypatch)
    await api_client.post("/api/v1/workflows", json={"engagement_id": eng_id, "name": "Empty"})
    csv_resp = await api_client.get("/api/v1/workflows/export.csv",
                                    params={"engagement_id": eng_id, "dataset_id": ds_id})
    assert csv_resp.status_code == 200
    rows = list(csv.DictReader(io.StringIO(csv_resp.text)))
    assert rows == []  # header only, no mapped tasks
