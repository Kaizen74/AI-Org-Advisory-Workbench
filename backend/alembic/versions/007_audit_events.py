"""audit_events table

Revision ID: 007_audit_events
Revises: 006_app_settings
Create Date: 2026-06-14

Phase 7 (M7). Additive and reversible.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007_audit_events"
down_revision: Union[str, None] = "006_app_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("engagement_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["engagement_id"], ["engagements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_engagement_id", "audit_events", ["engagement_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_engagement_id", table_name="audit_events")
    op.drop_table("audit_events")
