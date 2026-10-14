"""Add authentication-state evidence and allowlisted profile summaries.

Revision ID: 0003_auth_profile_projection
Revises: 0002_operator_integrations
Create Date: 2026-10-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_auth_profile_projection"
down_revision = "0002_operator_integrations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("commands") as batch_op:
        batch_op.drop_constraint("ck_commands_operation", type_="check")
        batch_op.create_check_constraint(
            "ck_commands_operation",
            "operation IN ('launch', 'stop', 'restart', 'join_room', 'leave_room', "
            "'add_friend', 'open_im')",
        )

    op.add_column(
        "profile_snapshots",
        sa.Column(
            "summary_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    with op.batch_alter_table("profile_snapshots") as batch_op:
        batch_op.alter_column("summary_json", server_default=None)

    op.create_table(
        "auth_state_snapshots",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("page_type", sa.String(length=16), nullable=True),
        sa.Column("csrf_present", sa.Boolean(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('unknown', 'login_required', 'authenticated', 'public')",
            name="ck_auth_state_snapshots_state",
        ),
        sa.CheckConstraint(
            "page_type IS NULL OR page_type IN ('profile', 'settings', 'public')",
            name="ck_auth_state_snapshots_page_type",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("account_id"),
    )


def downgrade() -> None:
    op.drop_table("auth_state_snapshots")
    op.drop_column("profile_snapshots", "summary_json")
    with op.batch_alter_table("commands") as batch_op:
        batch_op.drop_constraint("ck_commands_operation", type_="check")
        batch_op.create_check_constraint(
            "ck_commands_operation",
            "operation IN ('launch', 'stop', 'join_room', 'leave_room')",
        )
