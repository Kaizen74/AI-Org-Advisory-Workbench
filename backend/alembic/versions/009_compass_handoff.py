"""Capability Compass hand-off: engagement key/packet, compass_roles, shared IDs + grade

Revision ID: 009_compass_handoff
Revises: 008_access_users
Create Date: 2026-11-12

D50 — shared language with the other three apps. Additive and reversible: new nullable columns on
engagements / tasks / process_steps / task_ai_scores / task_benchmarks and one new table.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009_compass_handoff"
down_revision: Union[str, None] = "008_access_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = [
    ("engagements", sa.Column("compass_key", sa.String(length=64), nullable=True)),
    ("engagements", sa.Column("compass_packet", sa.JSON(), nullable=True)),
    ("engagements", sa.Column("task_seq", sa.Integer(), nullable=True)),
    ("tasks", sa.Column("code", sa.String(length=16), nullable=True)),
    ("process_steps", sa.Column("pms_step_id", sa.String(length=32), nullable=True)),
    ("task_ai_scores", sa.Column("grade_override", sa.String(length=16), nullable=True)),
    ("task_benchmarks", sa.Column("grade_override", sa.String(length=16), nullable=True)),
]


def upgrade() -> None:
    for table, column in _COLUMNS:
        op.add_column(table, sa.Column(column.name, column.type, nullable=True))
    op.create_index("ix_engagements_compass_key", "engagements", ["compass_key"])
    op.create_index("ix_tasks_code", "tasks", ["code"])
    op.create_table(
        "compass_roles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("engagement_id", sa.String(length=36), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("ref", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("cluster_ref", sa.String(length=32), nullable=True),
        sa.Column("route", sa.String(length=16), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=True),
        sa.Column("criticality_index", sa.Float(), nullable=True),
        sa.Column("tacit_intensity", sa.Float(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("matched_job_title", sa.String(length=255), nullable=True),
        sa.Column("match_state", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["engagement_id"], ["engagements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_compass_roles_engagement_id", "compass_roles", ["engagement_id"])
    op.create_index("ix_compass_roles_ref", "compass_roles", ["ref"])


def downgrade() -> None:
    op.drop_index("ix_compass_roles_ref", table_name="compass_roles")
    op.drop_index("ix_compass_roles_engagement_id", table_name="compass_roles")
    op.drop_table("compass_roles")
    op.drop_index("ix_tasks_code", table_name="tasks")
    op.drop_index("ix_engagements_compass_key", table_name="engagements")
    for table, column in reversed(_COLUMNS):
        with op.batch_alter_table(table) as batch:
            batch.drop_column(column.name)
