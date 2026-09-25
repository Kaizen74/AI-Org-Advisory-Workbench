"""scenario design tables (scenarios, design_moves, scenario_metrics)

Revision ID: 003_scenarios
Revises: 002_reference_and_tasks
Create Date: 2026-06-11

Phase 4, Build Spec B1. Additive and reversible: `downgrade()` drops ONLY what this migration adds.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_scenarios"
down_revision: Union[str, None] = "002_reference_and_tasks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scenarios",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("engagement_id", sa.String(length=36), nullable=False),
        sa.Column("dataset_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("parent_scenario_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["engagement_id"], ["engagements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_scenario_id"], ["scenarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scenarios_engagement_id", "scenarios", ["engagement_id"])
    op.create_index("ix_scenarios_dataset_id", "scenarios", ["dataset_id"])

    op.create_table(
        "design_moves",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("scenario_id", sa.String(length=36), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("move_type", sa.String(length=32), nullable=False),
        sa.Column("params", sa.JSON(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("activator_tag", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["scenario_id"], ["scenarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_design_moves_scenario_id", "design_moves", ["scenario_id"])

    op.create_table(
        "scenario_metrics",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("scenario_id", sa.String(length=36), nullable=False),
        sa.Column("metric_code", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("delta_vs_baseline", sa.Float(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["scenario_id"], ["scenarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scenario_metrics_scenario_id", "scenario_metrics", ["scenario_id"])


def downgrade() -> None:
    op.drop_index("ix_scenario_metrics_scenario_id", table_name="scenario_metrics")
    op.drop_table("scenario_metrics")

    op.drop_index("ix_design_moves_scenario_id", table_name="design_moves")
    op.drop_table("design_moves")

    op.drop_index("ix_scenarios_dataset_id", table_name="scenarios")
    op.drop_index("ix_scenarios_engagement_id", table_name="scenarios")
    op.drop_table("scenarios")
