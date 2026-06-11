"""P1.3 — Alembic migration 001 round-trip: upgrade creates the tables, downgrade removes them.

Proves the migration is additive AND reversible (A3 Rule 5).
"""
from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

BACKEND = Path(__file__).resolve().parents[1]
CORE_TABLES = {"clients", "engagements", "datasets", "positions", "metric_values"}


def _alembic_config(db_path: Path) -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def test_migration_upgrade_then_downgrade(tmp_path):
    db_path = tmp_path / "migration_test.db"
    cfg = _alembic_config(db_path)

    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db_path}")
    tables = set(inspect(engine).get_table_names())
    assert CORE_TABLES <= tables, f"missing after upgrade: {CORE_TABLES - tables}"

    command.downgrade(cfg, "base")
    tables_after = set(inspect(engine).get_table_names())
    assert not (CORE_TABLES & tables_after), f"left behind after downgrade: {CORE_TABLES & tables_after}"
    engine.dispose()
