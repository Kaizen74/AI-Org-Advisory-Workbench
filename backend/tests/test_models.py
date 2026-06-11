"""P1.2 — engagement-core model smoke test, including FK cascade purge (PRD §5)."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from app.models import Client, Dataset, Engagement, MetricValue, Position
from app.models.database import Base


@pytest.fixture
def session():
    """A synchronous in-memory SQLite session with FK enforcement on (for cascade testing)."""
    engine = create_engine("sqlite://", future=True)

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _rec):  # SQLite needs PRAGMA to enforce FKs
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _seed(s: Session) -> Engagement:
    client = Client(name="PAX Airlines", industry="Aviation")
    eng = Engagement(client=client, name="TOM 2026")
    ds = Dataset(engagement=eng, version=1, filename="org.csv", row_count=2)
    ds.positions = [
        Position(employee_key="E001", display_name="Vincent Chan", level=1),
        Position(employee_key="E002", display_name="Daniel Boy", level=2, manager_key="E001"),
    ]
    ds.metric_values = [MetricValue(metric_code="total_employees", scope="org", value=2, unit="count")]
    s.add(client)
    s.commit()
    return eng


def test_create_and_relationships(session):
    eng = _seed(session)
    assert session.scalar(select(func.count()).select_from(Client)) == 1
    assert session.scalar(select(func.count()).select_from(Position)) == 2
    assert eng.datasets[0].positions[0].employee_key == "E001"
    # UUID PKs are generated.
    assert len(eng.id) == 36


def test_purge_cascades_to_all_engagement_data(session):
    """Deleting a client cascades to engagements -> datasets -> positions + metric_values."""
    _seed(session)
    client = session.scalar(select(Client))
    session.delete(client)
    session.commit()

    for model in (Client, Engagement, Dataset, Position, MetricValue):
        assert session.scalar(select(func.count()).select_from(model)) == 0
