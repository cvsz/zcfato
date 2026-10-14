"""Track account-scoped client process and room state separately.

Revision ID: 0004_account_runtime_snapshot
Revises: 0003_auth_profile_projection
Create Date: 2026-10-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_account_runtime_snapshot"
down_revision = "0003_auth_profile_projection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_runtime_snapshots",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("process_state", sa.String(length=16), nullable=False),
        sa.Column("room_state", sa.String(length=16), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "process_state IN ('unknown', 'starting', 'running', 'stopped', 'error')",
            name="ck_account_runtime_process_state",
        ),
        sa.CheckConstraint(
            "room_state IN ('unknown', 'disconnected', 'joining', 'in_room')",
            name="ck_account_runtime_room_state",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("account_id"),
    )


def downgrade() -> None:
    op.drop_table("account_runtime_snapshots")
