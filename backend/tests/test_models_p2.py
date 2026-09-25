"""P2.1 — reference-layer + task model smoke test, incl. provenance fields + logical overlay join."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from app.models import (
    TaskAIOverlay,
    TaskAIScore,
    TaskBenchmark,
    TaxonomyCrosswalk,
    TaxonomySource,
    TaxonomyTask,
)
from app.models.database import Base


@pytest.fixture
def session():
    engine = create_engine("sqlite://", future=True)

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _rec):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_reference_layer_and_overlay_logical_join(session):
    src = TaxonomySource(code="SFW_AIR_TRANSPORT", name="SFw Air Transport", is_default=True)
    task = TaxonomyTask(source=src, task_ref="SFW_AT_CGO_01", task_text="Process air waybills",
                        task_code=None)
    overlay = TaskAIOverlay(onet_task_code="43-5011.00", has_level=2, desire_score_us=0.70,
                            capability_score=0.78, zone="GREEN_LIGHT", source="WORKBank")
    cw = TaxonomyCrosswalk(from_source_id=None, from_task_id=None, to_source_code="ONET",
                           to_task_code="43-5011.00", confidence=0.40, method="CURATED")
    session.add_all([src, task, overlay, cw])
    session.commit()

    # Overlay has NO FK to tasks — it is reached by matching onet_task_code (D1).
    fk_targets = {fk.column.table.name for fk in TaskAIOverlay.__table__.foreign_keys}
    assert "tasks" not in fk_targets and "taxonomy_task" not in fk_targets

    # desire_score_us populated, desire_score_local stays NULL (dual-score design, A4).
    o = session.scalar(select(TaskAIOverlay))
    assert o.desire_score_us == 0.70
    assert o.desire_score_local is None


def test_provenance_fields_present_on_ai_rows():
    """Every AI-derived row model carries source / confidence / review_state (A4)."""
    for model in (TaskBenchmark, TaskAIScore):
        cols = set(model.__table__.columns.keys())
        assert {"source", "confidence", "review_state"} <= cols
    # The crosswalk also carries review_state so the <0.70 routing can mark seed rows unreviewed.
    assert "review_state" in TaxonomyCrosswalk.__table__.columns.keys()
