"""D30 — delete process / step in the Workflow Mapper (linked tasks return to the unmapped tray)."""
from __future__ import annotations

from sqlalchemy import select

from app.models import Task
from tests.test_workflow_board import _setup


async def test_delete_step_and_process(api_client, async_session, monkeypatch):
    eng_id, ds_id = await _setup(api_client, async_session, monkeypatch)
    p = (await api_client.post("/api/v1/workflows",
                               json={"engagement_id": eng_id, "name": "P"})).json()
    pid = p["id"]
    s1 = (await api_client.post(f"/api/v1/workflows/{pid}/steps", json={"name": "S1"})).json()
    s2 = (await api_client.post(f"/api/v1/workflows/{pid}/steps", json={"name": "S2"})).json()
    tid = (await async_session.scalars(select(Task))).first().id
    await api_client.post(f"/api/v1/workflows/steps/{s1['id']}/map-tasks", json={"task_ids": [tid]})

    # Delete a step → it's gone and its task returns to the unmapped tray.
    r = await api_client.delete(f"/api/v1/workflows/steps/{s1['id']}")
    assert r.status_code == 200 and r.json()["deleted"] == s1["id"]
    board = (await api_client.get(f"/api/v1/workflows/{pid}/board",
                                  params={"dataset_id": ds_id})).json()
    assert [s["id"] for s in board["steps"]] == [s2["id"]]
    assert any(t["id"] == tid for t in board["unmapped"])
    assert (await api_client.delete(f"/api/v1/workflows/steps/{s1['id']}")).status_code == 404

    # Delete the process → gone (board 404), not listed.
    rp = await api_client.delete(f"/api/v1/workflows/{pid}")
    assert rp.status_code == 200 and rp.json()["deleted"] == pid
    assert (await api_client.get(f"/api/v1/workflows/{pid}/board",
                                 params={"dataset_id": ds_id})).status_code == 404
    listed = (await api_client.get("/api/v1/workflows",
                                   params={"engagement_id": eng_id})).json()
    assert all(x["id"] != pid for x in listed)
    assert (await api_client.delete(f"/api/v1/workflows/{pid}")).status_code == 404
