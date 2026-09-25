"""reference layer + task tables (taxonomy_*, task_ai_overlay, tasks, task_benchmarks,
task_ai_scores, desire_pulse_responses)

Revision ID: 002_reference_and_tasks
Revises: 001_engagement_core
Create Date: 2026-06-11

Phase 2, Build Spec B1. Additive and reversible: `downgrade()` drops ONLY what this migration adds,
in reverse FK order (A3 Rule 5). The engagement-core tables from 001 are untouched.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_reference_and_tasks"
down_revision: Union[str, None] = "001_engagement_core"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "taxonomy_source",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("region", sa.String(length=16), nullable=True),
        sa.Column("version", sa.String(length=64), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_taxonomy_source_code", "taxonomy_source", ["code"])

    op.create_table(
        "taxonomy_task",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("task_ref", sa.String(length=128), nullable=False),
        sa.Column("role_label", sa.String(length=255), nullable=True),
        sa.Column("track", sa.String(length=255), nullable=True),
        sa.Column("function", sa.String(length=255), nullable=True),
        sa.Column("task_text", sa.Text(), nullable=False),
        sa.Column("task_code", sa.String(length=64), nullable=True),
        sa.Column("skills", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["source_id"], ["taxonomy_source.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_ref"),
    )
    op.create_index("ix_taxonomy_task_source_id", "taxonomy_task", ["source_id"])
    op.create_index("ix_taxonomy_task_task_ref", "taxonomy_task", ["task_ref"])

    op.create_table(
        "taxonomy_crosswalk",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("from_source_id", sa.String(length=36), nullable=True),
        sa.Column("from_task_id", sa.String(length=36), nullable=True),
        sa.Column("to_source_code", sa.String(length=64), nullable=False),
        sa.Column("to_task_code", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("method", sa.String(length=32), nullable=False),
        sa.Column("review_state", sa.String(length=16), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["from_source_id"], ["taxonomy_source.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["from_task_id"], ["taxonomy_task.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_taxonomy_crosswalk_from_source_id", "taxonomy_crosswalk", ["from_source_id"])
    op.create_index("ix_taxonomy_crosswalk_from_task_id", "taxonomy_crosswalk", ["from_task_id"])

    op.create_table(
        "task_ai_overlay",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("onet_task_code", sa.String(length=64), nullable=False),
        sa.Column("onet_task_text", sa.Text(), nullable=True),
        sa.Column("occupation", sa.String(length=255), nullable=True),
        sa.Column("has_level", sa.Integer(), nullable=True),
        sa.Column("desire_score_us", sa.Float(), nullable=True),
        sa.Column("desire_score_local", sa.Float(), nullable=True),
        sa.Column("capability_score", sa.Float(), nullable=True),
        sa.Column("zone", sa.String(length=32), nullable=True),
        sa.Column("source", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("onet_task_code"),
    )
    op.create_index("ix_task_ai_overlay_onet_task_code", "task_ai_overlay", ["onet_task_code"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("position_id", sa.String(length=36), nullable=False),
        sa.Column("task_text", sa.Text(), nullable=False),
        sa.Column("batch_id", sa.String(length=64), nullable=True),
        sa.Column("extraction_source", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tasks_position_id", "tasks", ["position_id"])
    op.create_index("ix_tasks_batch_id", "tasks", ["batch_id"])

    op.create_table(
        "task_benchmarks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("taxonomy_source_code", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("matched_taxonomy_task_id", sa.String(length=36), nullable=True),
        sa.Column("onet_task_code", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("review_state", sa.String(length=16), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["matched_taxonomy_task_id"], ["taxonomy_task.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_benchmarks_task_id", "task_benchmarks", ["task_id"])

    op.create_table(
        "task_ai_scores",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("has_level", sa.Integer(), nullable=True),
        sa.Column("zone", sa.String(length=32), nullable=True),
        sa.Column("desire_score_us", sa.Float(), nullable=True),
        sa.Column("desire_score_local", sa.Float(), nullable=True),
        sa.Column("capability_score", sa.Float(), nullable=True),
        sa.Column("ai_opportunity_level", sa.String(length=8), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("review_state", sa.String(length=16), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_ai_scores_task_id", "task_ai_scores", ["task_id"])

    op.create_table(
        "desire_pulse_responses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("engagement_id", sa.String(length=36), nullable=False),
        sa.Column("task_ref", sa.String(length=128), nullable=True),
        sa.Column("respondent_hash", sa.String(length=64), nullable=True),
        sa.Column("desire_rating", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["engagement_id"], ["engagements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_desire_pulse_responses_engagement_id", "desire_pulse_responses", ["engagement_id"]
    )
    op.create_index("ix_desire_pulse_responses_task_ref", "desire_pulse_responses", ["task_ref"])


def downgrade() -> None:
    op.drop_index("ix_desire_pulse_responses_task_ref", table_name="desire_pulse_responses")
    op.drop_index("ix_desire_pulse_responses_engagement_id", table_name="desire_pulse_responses")
    op.drop_table("desire_pulse_responses")

    op.drop_index("ix_task_ai_scores_task_id", table_name="task_ai_scores")
    op.drop_table("task_ai_scores")

    op.drop_index("ix_task_benchmarks_task_id", table_name="task_benchmarks")
    op.drop_table("task_benchmarks")

    op.drop_index("ix_tasks_batch_id", table_name="tasks")
    op.drop_index("ix_tasks_position_id", table_name="tasks")
    op.drop_table("tasks")

    op.drop_index("ix_task_ai_overlay_onet_task_code", table_name="task_ai_overlay")
    op.drop_table("task_ai_overlay")

    op.drop_index("ix_taxonomy_crosswalk_from_task_id", table_name="taxonomy_crosswalk")
    op.drop_index("ix_taxonomy_crosswalk_from_source_id", table_name="taxonomy_crosswalk")
    op.drop_table("taxonomy_crosswalk")

    op.drop_index("ix_taxonomy_task_task_ref", table_name="taxonomy_task")
    op.drop_index("ix_taxonomy_task_source_id", table_name="taxonomy_task")
    op.drop_table("taxonomy_task")

    op.drop_index("ix_taxonomy_source_code", table_name="taxonomy_source")
    op.drop_table("taxonomy_source")
