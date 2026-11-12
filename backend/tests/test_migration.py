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
P5_TABLES = {"processes", "process_steps", "task_links"}
P6_TABLES = {"deliverables"}
SETTINGS_TABLES = {"app_settings"}
AUDIT_TABLES = {"audit_events"}
ACCESS_TABLES = {"access_users"}


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


def test_migration_004_adds_and_removes_workflow_tables(tmp_path):
    db_path = tmp_path / "migration4_test.db"
    cfg = _alembic_config(db_path)

    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db_path}")
    assert (CORE_TABLES | P2_TABLES | P4_TABLES | P5_TABLES) <= set(inspect(engine).get_table_names())

    command.downgrade(cfg, "003_scenarios")
    after = set(inspect(engine).get_table_names())
    assert not (P5_TABLES & after)
    assert (CORE_TABLES | P2_TABLES | P4_TABLES) <= after

    command.downgrade(cfg, "base")
    assert not (P5_TABLES & set(inspect(engine).get_table_names()))
    engine.dispose()


def test_migration_005_adds_and_removes_deliverables(tmp_path):
    db_path = tmp_path / "migration5_test.db"
    cfg = _alembic_config(db_path)

    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db_path}")
    all_tables = CORE_TABLES | P2_TABLES | P4_TABLES | P5_TABLES | P6_TABLES
    assert all_tables <= set(inspect(engine).get_table_names())

    command.downgrade(cfg, "004_workflows")
    after = set(inspect(engine).get_table_names())
    assert not (P6_TABLES & after)
    assert (CORE_TABLES | P2_TABLES | P4_TABLES | P5_TABLES) <= after

    command.downgrade(cfg, "base")
    assert not (P6_TABLES & set(inspect(engine).get_table_names()))
    engine.dispose()


def test_migration_006_adds_and_removes_app_settings(tmp_path):
    db_path = tmp_path / "migration6_test.db"
    cfg = _alembic_config(db_path)

    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db_path}")
    all_tables = CORE_TABLES | P2_TABLES | P4_TABLES | P5_TABLES | P6_TABLES | SETTINGS_TABLES
    assert all_tables <= set(inspect(engine).get_table_names())

    command.downgrade(cfg, "005_deliverables")
    after = set(inspect(engine).get_table_names())
    assert not (SETTINGS_TABLES & after)
    assert P6_TABLES <= after

    command.downgrade(cfg, "base")
    assert not (SETTINGS_TABLES & set(inspect(engine).get_table_names()))
    engine.dispose()


def test_migration_007_adds_and_removes_audit_events(tmp_path):
    db_path = tmp_path / "migration7_test.db"
    cfg = _alembic_config(db_path)

    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db_path}")
    everything = (CORE_TABLES | P2_TABLES | P4_TABLES | P5_TABLES | P6_TABLES
                  | SETTINGS_TABLES | AUDIT_TABLES)
    assert everything <= set(inspect(engine).get_table_names())

    command.downgrade(cfg, "006_app_settings")
    after = set(inspect(engine).get_table_names())
    assert not (AUDIT_TABLES & after)
    assert SETTINGS_TABLES <= after

    command.downgrade(cfg, "base")
    assert not (AUDIT_TABLES & set(inspect(engine).get_table_names()))
    engine.dispose()


def test_migration_008_adds_and_removes_access_users(tmp_path):
    db_path = tmp_path / "migration8_test.db"
    cfg = _alembic_config(db_path)

    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db_path}")
    assert ACCESS_TABLES <= set(inspect(engine).get_table_names())

    command.downgrade(cfg, "007_audit_events")
    after = set(inspect(engine).get_table_names())
    assert not (ACCESS_TABLES & after)
    assert AUDIT_TABLES <= after

    command.downgrade(cfg, "base")
    assert not (ACCESS_TABLES & set(inspect(engine).get_table_names()))
    engine.dispose()


def test_migration_009_adds_and_removes_compass_handoff(tmp_path):
    """D50: additive columns + compass_roles; downgrade removes only what 009 added."""
    db_path = tmp_path / "migration9_test.db"
    cfg = _alembic_config(db_path)
    added = {"engagements": {"compass_key", "compass_packet", "task_seq"}, "tasks": {"code"},
             "process_steps": {"pms_step_id"}, "task_ai_scores": {"grade_override"},
             "task_benchmarks": {"grade_override"}}

    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db_path}")
    insp = inspect(engine)
    assert "compass_roles" in insp.get_table_names()
    for table, cols in added.items():
        assert cols <= {c["name"] for c in insp.get_columns(table)}, table

    command.downgrade(cfg, "008_access_users")
    insp = inspect(engine)
    assert "compass_roles" not in insp.get_table_names()
    for table, cols in added.items():
        names = {c["name"] for c in insp.get_columns(table)}
        assert not (cols & names), f"{table} kept {cols & names}"
    assert {"name", "anonymized"} <= {c["name"] for c in insp.get_columns("engagements")}
    assert ACCESS_TABLES <= set(insp.get_table_names())  # earlier phases survive

    command.downgrade(cfg, "base")
    engine.dispose()
