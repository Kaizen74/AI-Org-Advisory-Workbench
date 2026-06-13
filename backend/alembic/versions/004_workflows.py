"""workflow tables (processes, process_steps, task_links)

Revision ID: 004_workflows
Revises: 003_scenarios
Create Date: 2026-06-11

Phase 5, Build Spec B1. Additive and reversible: `downgrade()` drops ONLY what this migration adds.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_workflows"
down_revision: Union[str, None] = "003_scenarios"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "processes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("engagement_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("value_stream", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["engagement_id"], ["engagements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_processes_engagement_id", "processes", ["engagement_id"])

    op.create_table(
        "process_steps",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("process_id", sa.String(length=36), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["process_id"], ["processes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_process_steps_process_id", "process_steps", ["process_id"])

    op.create_table(
        "task_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("process_step_id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["process_step_id"], ["process_steps.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_links_process_step_id", "task_links", ["process_step_id"])
    op.create_index("ix_task_links_task_id", "task_links", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_task_links_task_id", table_name="task_links")
    op.drop_index("ix_task_links_process_step_id", table_name="task_links")
    op.drop_table("task_links")

    op.drop_index("ix_process_steps_process_id", table_name="process_steps")
    op.drop_table("process_steps")

    op.drop_index("ix_processes_engagement_id", table_name="processes")
    op.drop_table("processes")
