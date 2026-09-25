"""deliverables table

Revision ID: 005_deliverables
Revises: 004_workflows
Create Date: 2026-06-14

Phase 6, Build Spec B1. Additive and reversible: `downgrade()` drops ONLY what this migration adds.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_deliverables"
down_revision: Union[str, None] = "004_workflows"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "deliverables",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("engagement_id", sa.String(length=36), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("template", sa.String(length=32), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=True),
        sa.Column("provenance_summary", sa.JSON(), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["engagement_id"], ["engagements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deliverables_engagement_id", "deliverables", ["engagement_id"])


def downgrade() -> None:
    op.drop_index("ix_deliverables_engagement_id", table_name="deliverables")
    op.drop_table("deliverables")
