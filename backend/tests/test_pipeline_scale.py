"""D35 — scalability: the full pipeline must handle many tasks across multiple batches with no silent
loss, and the extract/benchmark/inference Claude calls must use a large-enough token budget."""
from __future__ import annotations

import json

from sqlalchemy import func, select

from app.models import TaskAIScore
from app.services import task_intelligence_service as tis
from app.services.claude_service import claude_service
from app.services.taxonomy_loader import load_taxonomies

N = 25  # positions/tasks — enough to span several extract + inference batches


def _make_ai(seen: dict):
    def _ai(*, model, max_tokens=2048, messages):  # noqa: ARG001
        c = messages[0]["content"]
        if "HUMAN AGENCY SCALE BENCHMARK" in c:
            seen.setdefault("infer", []).append(max_tokens)
            payload = json.loads(c.split("TASKS:\n```json\n")[1].split("\n```")[0])
            return json.dumps({"scores": [
                {"task_id": t["task_id"], "has_level": 2, "capability_score": 0.8,
                 "zone": "GREEN_LIGHT", "confidence": 0.6, "rationale": "k"} for t in payload]})
        if "GROUNDING:" in c:
            seen.setdefault("benchmark", []).append(max_tokens)
            tasks = json.loads(c.split("TASKS:\n```json\n")[1].split("\n```")[0])
            return json.dumps({"benchmarks": [
                {"task_id": t["task_id"], "status": "MISSING", "matched_task_ref": None,
                 "onet_task_code": None, "taxonomy_source_code": None,
                 "source": "model-inferred", "confidence": 0.3} for t in tasks]})
        seen.setdefault("extract", []).append(max_tokens)
        items = json.loads(c.split("INPUT:\n```json\n")[1].split("\n```")[0])
        return json.dumps({"extractions": [
            {"employee_key": it["employee_key"],
             "tasks": [s.strip() for s in it["work_activities"].split(";") if s.strip()]}
            for it in items]})
    return _ai


async def test_full_pipeline_scales_across_batches(api_client, async_session, monkeypatch):
    seen: dict = {}
    monkeypatch.setattr(type(claude_service), "has_api_key", property(lambda self: True))
    monkeypatch.setattr(claude_service, "complete", _make_ai(seen))
    monkeypatch.setattr(tis, "INFER_BATCH", 5)  # force several inference batches
    await load_taxonomies(async_session)

    cl = await api_client.post("/api/v1/engagements/clients", json={"name": "Big Co"})
    e = await api_client.post("/api/v1/engagements", json={"client_id": cl.json()["id"], "name": "AI"})
    eng = e.json()["id"]
    header = "Name,Job Title,Grade,Department,Level,Line Manager,Salary,Employee ID,Work Activities\n"
    rows = "".join(
        f"P{i},Role {i},H3,{'Marketing' if i % 2 else 'Comms'},2,Top,90000,E{i},Task number {i}\n"
        for i in range(N)
    )
    ds = (await api_client.post(f"/api/v1/engagements/{eng}/datasets",
          files={"file": ("o.csv", (header + rows).encode(), "text/csv")})).json()["id"]

    # Extract in small batches (multi-batch), then benchmark + score + infer.
    ext = (await api_client.post("/api/v1/task-intel/extract",
                                 params={"dataset_id": ds, "batch_size": 5})).json()
    assert ext["tasks_created"] == N
    await api_client.post("/api/v1/task-intel/benchmark", params={"dataset_id": ds})
    aiopp = (await api_client.post("/api/v1/task-intel/ai-opportunity",
                                   params={"dataset_id": ds})).json()
    assert aiopp["scored"] == N and aiopp["unclassified"] == N  # all unmatched before inference
    infer = (await api_client.post("/api/v1/task-intel/infer-potential",
                                   params={"dataset_id": ds})).json()
    assert infer["candidates"] == N and infer["updated"] == N  # NOTHING dropped across batches

    # Every task ended up inferred (no row left at H0/NO_BENCHMARK_MATCH).
    scores = list(await async_session.scalars(select(TaskAIScore)))
    assert len(scores) == N
    assert all(s.zone == "GREEN_LIGHT" and s.has_level == 2 for s in scores)
    roll = (await api_client.get("/api/v1/task-intel/rollup", params={"dataset_id": ds})).json()
    assert roll["source_mix"]["ai_inferred"] == N and roll["source_mix"]["unclassified"] == 0

    # Multi-batch actually happened, and the token budgets are the hardened ones (not the 2048 default).
    assert len(seen["extract"]) >= 2 and all(mt >= 8192 for mt in seen["extract"])
    assert all(mt >= 4096 for mt in seen["benchmark"])
    assert len(seen["infer"]) == (N + 4) // 5 and all(mt >= 3072 for mt in seen["infer"])
