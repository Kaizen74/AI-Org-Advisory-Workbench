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
P2_TABLES = {
    "taxonomy_source",
    "taxonomy_task",
    "taxonomy_crosswalk",
    "task_ai_overlay",
    "tasks",
    "task_benchmarks",
    "task_ai_scores",
    "desire_pulse_responses",
}
P4_TABLES = {"scenarios", "design_moves", "scenario_metrics"}


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


def test_migration_002_adds_and_removes_reference_and_task_tables(tmp_path):
    db_path = tmp_path / "migration2_test.db"
    cfg = _alembic_config(db_path)

    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db_path}")
    tables = set(inspect(engine).get_table_names())
    assert (CORE_TABLES | P2_TABLES) <= tables, f"missing: {(CORE_TABLES | P2_TABLES) - tables}"

    # Downgrade just one step removes only P2 tables; core tables remain (additive within phases).
    command.downgrade(cfg, "001_engagement_core")
    after_one = set(inspect(engine).get_table_names())
    assert not (P2_TABLES & after_one), f"P2 left behind: {P2_TABLES & after_one}"
    assert CORE_TABLES <= after_one, "001 tables must survive a single-step downgrade"

    command.downgrade(cfg, "base")
    assert not ((CORE_TABLES | P2_TABLES) & set(inspect(engine).get_table_names()))
    engine.dispose()


def test_migration_003_adds_and_removes_scenario_tables(tmp_path):
    db_path = tmp_path / "migration3_test.db"
    cfg = _alembic_config(db_path)

    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db_path}")
    tables = set(inspect(engine).get_table_names())
    assert (CORE_TABLES | P2_TABLES | P4_TABLES) <= tables

    command.downgrade(cfg, "002_reference_and_tasks")
    after = set(inspect(engine).get_table_names())
    assert not (P4_TABLES & after), f"P4 left behind: {P4_TABLES & after}"
    assert (CORE_TABLES | P2_TABLES) <= after  # earlier phases survive

    command.downgrade(cfg, "base")
    assert not ((CORE_TABLES | P2_TABLES | P4_TABLES) & set(inspect(engine).get_table_names()))
    engine.dispose()
