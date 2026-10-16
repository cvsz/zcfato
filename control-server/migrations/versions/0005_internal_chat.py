"""Add the account-scoped operator and agent chat transport.

Revision ID: 0005_internal_chat
Revises: 0004_account_runtime_snapshot
Create Date: 2026-10-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_internal_chat"
down_revision = "0004_account_runtime_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("client_message_id", sa.Uuid(), nullable=False),
        sa.Column("direction", sa.String(length=24), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("claim_attempts", sa.Integer(), nullable=False),
        sa.Column("claim_token_hash", sa.String(length=64), nullable=True),
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "direction IN ('operator_to_agent', 'agent_to_operator')",
            name="ck_chat_messages_direction",
        ),
        sa.CheckConstraint(
            "state IN ('queued', 'claimed', 'received', 'delivered', 'failed', 'canceled')",
            name="ck_chat_messages_state",
        ),
        sa.CheckConstraint(
            "(direction = 'agent_to_operator' AND state = 'received') OR "
            "(direction = 'operator_to_agent' AND state != 'received')",
            name="ck_chat_messages_direction_state",
        ),
        sa.CheckConstraint(
            "(state = 'claimed' AND claim_token_hash IS NOT NULL AND claim_expires_at IS NOT NULL) "
            "OR (state != 'claimed' AND claim_token_hash IS NULL AND claim_expires_at IS NULL)",
            name="ck_chat_messages_claim_state",
        ),
        sa.CheckConstraint(
            "(direction = 'agent_to_operator' AND delivered_at IS NOT NULL) OR "
            "(direction = 'operator_to_agent' AND "
            "((state = 'delivered' AND delivered_at IS NOT NULL) OR "
            "(state != 'delivered' AND delivered_at IS NULL)))",
            name="ck_chat_messages_delivery_timestamp",
        ),
        sa.CheckConstraint("claim_attempts >= 0", name="ck_chat_messages_claim_attempts"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id", "direction", "client_message_id", name="uq_chat_messages_idempotency"
        ),
    )
    op.create_index(
        "ix_chat_messages_agent_state_created",
        "chat_messages",
        ["agent_id", "direction", "state", "created_at"],
    )
    op.create_index(
        "ix_chat_messages_account_created",
        "chat_messages",
        ["account_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_account_created", table_name="chat_messages")
    op.drop_index("ix_chat_messages_agent_state_created", table_name="chat_messages")
    op.drop_table("chat_messages")
