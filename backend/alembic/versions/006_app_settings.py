"""app_settings table (UI-managed LLM config + brand)

Revision ID: 006_app_settings
Revises: 005_deliverables
Create Date: 2026-06-14

Pre-P7 feature block (D11/D12). Additive and reversible.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_app_settings"
down_revision: Union[str, None] = "005_deliverables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
