"""engagement core tables (clients, engagements, datasets, positions, metric_values)

Revision ID: 001_engagement_core
Revises:
Create Date: 2026-06-11

Phase 1, Build Spec B1. Additive and reversible: `downgrade()` drops ONLY what this migration adds,
in reverse FK order (A3 Rule 5).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001_engagement_core"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "clients",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("industry", sa.String(length=255), nullable=True),
        sa.Column("anonymization_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clients_name", "clients", ["name"])

    op.create_table(
        "engagements",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("client_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("strategy_context", sa.Text(), nullable=True),
        sa.Column("design_criteria", sa.Text(), nullable=True),
        sa.Column("default_taxonomy_code", sa.String(length=64), nullable=True),
        sa.Column("anonymized", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_engagements_client_id", "engagements", ["client_id"])

    op.create_table(
        "datasets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("engagement_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("validation_warnings", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["engagement_id"], ["engagements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_datasets_engagement_id", "datasets", ["engagement_id"])

    op.create_table(
        "positions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("dataset_id", sa.String(length=36), nullable=False),
        sa.Column("employee_key", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("pseudonym", sa.String(length=255), nullable=True),
        sa.Column("job_title", sa.String(length=255), nullable=True),
        sa.Column("grade", sa.String(length=64), nullable=True),
        sa.Column("level", sa.Integer(), nullable=True),
        sa.Column("manager_key", sa.String(length=255), nullable=True),
        sa.Column("department", sa.String(length=255), nullable=True),
        sa.Column("salary", sa.Float(), nullable=True),
        sa.Column("work_activities", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_positions_dataset_id", "positions", ["dataset_id"])
    op.create_index("ix_positions_employee_key", "positions", ["employee_key"])
    op.create_index("ix_positions_manager_key", "positions", ["manager_key"])

    op.create_table(
        "metric_values",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("dataset_id", sa.String(length=36), nullable=False),
        sa.Column("metric_code", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("scope_key", sa.String(length=255), nullable=True),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("computed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_metric_values_dataset_id", "metric_values", ["dataset_id"])
    op.create_index("ix_metric_values_metric_code", "metric_values", ["metric_code"])


def downgrade() -> None:
    # Reverse FK order — drops ONLY what this migration created.
    op.drop_index("ix_metric_values_metric_code", table_name="metric_values")
    op.drop_index("ix_metric_values_dataset_id", table_name="metric_values")
    op.drop_table("metric_values")

    op.drop_index("ix_positions_manager_key", table_name="positions")
    op.drop_index("ix_positions_employee_key", table_name="positions")
    op.drop_index("ix_positions_dataset_id", table_name="positions")
    op.drop_table("positions")

    op.drop_index("ix_datasets_engagement_id", table_name="datasets")
    op.drop_table("datasets")

    op.drop_index("ix_engagements_client_id", table_name="engagements")
    op.drop_table("engagements")

    op.drop_index("ix_clients_name", table_name="clients")
    op.drop_table("clients")
