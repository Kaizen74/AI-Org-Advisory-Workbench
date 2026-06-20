"""P2.3 — seed loader tests against the real starter file (Build Spec B0/M2 acceptance #4)."""
from __future__ import annotations

import json

from sqlalchemy import func, select

from app.models import TaskAIOverlay, TaxonomyCrosswalk, TaxonomySource, TaxonomyTask
from app.services import taxonomy_loader
from app.services.taxonomy_loader import load_taxonomies


async def test_curated_workbank_overlay_is_loaded_when_present(async_session, tmp_path, monkeypatch):
    """The optional curated WORKBank overlay (D25) upserts authoritative rows keyed by O*NET code."""
    wb = tmp_path / "workbank_overlay.curated.json"
    wb.write_text(json.dumps({"task_ai_overlay": [
        {"onet_task_code": "11-2021.00", "occupation": "Marketing Managers", "has_level": 2,
         "capability_score": 0.81, "desire_score_us": 0.55, "zone": "GREEN_LIGHT", "source": "WORKBank"},
    ]}), encoding="utf-8")
    monkeypatch.setattr(taxonomy_loader, "WORKBANK_OVERLAY_PATH", wb)

    await load_taxonomies(async_session)
    row = await async_session.scalar(
        select(TaskAIOverlay).where(TaskAIOverlay.onet_task_code == "11-2021.00")
    )
    assert row is not None and row.source == "WORKBank"
    assert row.has_level == 2 and row.capability_score == 0.81
    assert row.desire_score_us == 0.55 and row.desire_score_local is None  # US only (A4)
    # The illustrative seed overlay still loads alongside it (additive).
    assert await async_session.scalar(
        select(TaskAIOverlay).where(TaskAIOverlay.onet_task_code == "43-5011.00")
    ) is not None


async def _counts(session):
    return {
        "sources": await session.scalar(select(func.count()).select_from(TaxonomySource)),
        "tasks": await session.scalar(select(func.count()).select_from(TaxonomyTask)),
        "overlays": await session.scalar(select(func.count()).select_from(TaskAIOverlay)),
        "crosswalks": await session.scalar(select(func.count()).select_from(TaxonomyCrosswalk)),
    }


async def test_loader_loads_starter_counts(async_session):
    result = await load_taxonomies(async_session)
    assert result == {"sources": 4, "tasks": 15, "overlays": 3, "crosswalks": 6}
    assert await _counts(async_session) == {
        "sources": 4, "tasks": 15, "overlays": 3, "crosswalks": 6,
    }


async def test_loader_is_idempotent(async_session):
    await load_taxonomies(async_session)
    await load_taxonomies(async_session)  # second run must not duplicate
    assert await _counts(async_session) == {
        "sources": 4, "tasks": 15, "overlays": 3, "crosswalks": 6,
    }


async def test_desire_score_maps_to_us_only(async_session):
    """seed desire_score -> desire_score_us; desire_score_local stays NULL (A4 dual-score)."""
    await load_taxonomies(async_session)
    overlay = await async_session.scalar(
        select(TaskAIOverlay).where(TaskAIOverlay.onet_task_code == "43-5011.00")
    )
    assert overlay.desire_score_us == 0.70
    assert overlay.desire_score_local is None
    # has_level and capability stay independent (not collapsed).
    assert overlay.has_level == 2
    assert overlay.capability_score == 0.78


async def test_low_confidence_crosswalk_routes_to_unreviewed(async_session):
    """The starter's 0.40 curated crosswalk must default to review_state=unreviewed (B0)."""
    await load_taxonomies(async_session)
    # The 0.40 row maps PSO_02 -> 43-4181.00.
    low = await async_session.scalars(
        select(TaxonomyCrosswalk).where(TaxonomyCrosswalk.confidence < 0.70)
    )
    low_rows = list(low)
    assert any(r.confidence == 0.40 for r in low_rows)
    assert all(r.review_state == "unreviewed" for r in low_rows)

    # A high-confidence curated row loads as approved (review triggered by confidence, not label).
    high = await async_session.scalar(
        select(TaxonomyCrosswalk).where(TaxonomyCrosswalk.confidence == 0.88)
    )
    assert high.review_state == "approved"
