"""FA.4 — brand template: palette + logo flow into a generated deck (D12)."""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import pytest
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from app.models import Client, Dataset, Engagement, MetricValue
from app.services import deliverable_service
from app.services import settings_service as ss

# A minimal valid 1x1 PNG so python-pptx can embed a logo.
PNG_1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


@pytest.fixture(autouse=True)
def _reset():
    ss.reset_cache_for_tests()
    yield
    ss.reset_cache_for_tests()


async def _seed(async_session):
    client = Client(name="PAX", anonymization_default=False)
    eng = Engagement(client=client, name="TOM", anonymized=False)
    ds = Dataset(engagement=eng, version=1, row_count=2)
    async_session.add_all([client, eng, ds])
    await async_session.flush()
    for code, val, unit in [("total_employees", 64, "count"), ("total_cost", 6620000, "currency"),
                            ("organizational_layers", 6, "count"), ("manager_ratio_pct", 53.1, "percent"),
                            ("total_managers", 34, "count"), ("average_span", 1.85, "ratio")]:
        async_session.add(MetricValue(dataset_id=ds.id, metric_code=code, scope="org",
                                      value=val, unit=unit))
    await async_session.flush()
    return eng.id, ds.id


async def test_brand_template_records_name_and_embeds_logo(async_session, tmp_path):
    logo = tmp_path / "logo.png"
    logo.write_bytes(PNG_1x1)
    ss._cache["brand_name"] = "PAX Brand"
    ss._cache["brand_palette"] = json.dumps({"accent": "123456", "ink": "222222"})
    ss._cache["brand_logo_path"] = str(logo)

    eng_id, ds_id = await _seed(async_session)
    result = await deliverable_service.generate(
        async_session, engagement_id=eng_id, type="PPTX_DIAGNOSTIC", template="brand",
        dataset_id=ds_id,
    )
    assert result["template"] == "PAX Brand"  # brand name recorded on the deliverable row

    prs = Presentation(io.BytesIO(Path(result["file_path"]).read_bytes()))
    first_slide_shapes = prs.slides[0].shapes
    assert any(s.shape_type == MSO_SHAPE_TYPE.PICTURE for s in first_slide_shapes), "logo missing"


async def test_default_brand_is_sats_with_logo(async_session):
    """Out of the box (no UI changes), template='brand' renders SATS with its logo (preconfigured)."""
    eng_id, ds_id = await _seed(async_session)
    result = await deliverable_service.generate(
        async_session, engagement_id=eng_id, type="PPTX_DIAGNOSTIC", template="brand",
        dataset_id=ds_id,
    )
    assert result["template"] == "SATS"
    prs = Presentation(io.BytesIO(Path(result["file_path"]).read_bytes()))
    assert any(s.shape_type == MSO_SHAPE_TYPE.PICTURE for s in prs.slides[0].shapes)


async def test_minimal_template_still_default(async_session):
    eng_id, ds_id = await _seed(async_session)
    result = await deliverable_service.generate(
        async_session, engagement_id=eng_id, type="PPTX_DIAGNOSTIC", template="minimal",
        dataset_id=ds_id,
    )
    assert result["template"] == "minimal"  # unchanged default behaviour (regression)
