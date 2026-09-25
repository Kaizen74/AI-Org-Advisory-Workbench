"""access_users table (private access control)

Revision ID: 008_access_users
Revises: 007_audit_events
Create Date: 2026-06-14

D13 — app-level access control. Additive and reversible.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008_access_users"
down_revision: Union[str, None] = "007_audit_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "access_users",
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("passcode_hash", sa.String(length=255), nullable=False),
        sa.Column("salt", sa.String(length=64), nullable=False),
        sa.Column("is_owner", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("email"),
    )


def downgrade() -> None:
    op.drop_table("access_users")
