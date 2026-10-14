"""Add snapshot, Cloud Bot, Store consent, and subscription records.

Revision ID: 0002_operator_integrations
Revises: 0001_control_plane
Create Date: 2026-10-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_operator_integrations"
down_revision = "0001_control_plane"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profile_snapshots",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("nickname_color", sa.String(length=24), nullable=True),
        sa.Column("nickname_flair", sa.String(length=80), nullable=True),
        sa.Column("avatar_id", sa.Integer(), nullable=True),
        sa.Column("alevel", sa.Integer(), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("gender", sa.Integer(), nullable=True),
        sa.Column("country", sa.String(length=128), nullable=True),
        sa.Column("status_text", sa.String(length=500), nullable=True),
        sa.Column("client_presence", sa.String(length=16), nullable=False),
        sa.Column("subscription_type", sa.String(length=32), nullable=True),
        sa.Column("xp_count", sa.BigInteger(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "client_presence IN ('unknown', 'online', 'away', 'busy', 'offline')",
            name="ck_profile_snapshots_presence",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("account_id"),
    )
    op.create_table(
        "friend_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("nickname", sa.String(length=256), nullable=False),
        sa.Column("display_name", sa.String(length=256), nullable=True),
        sa.Column("presence", sa.String(length=16), nullable=False),
        sa.Column("nickname_color", sa.String(length=24), nullable=True),
        sa.Column("avatar_id", sa.Integer(), nullable=True),
        sa.Column("alevel", sa.Integer(), nullable=True),
        sa.Column("gender", sa.Integer(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "presence IN ('unknown', 'online', 'away', 'busy', 'offline')",
            name="ck_friend_snapshots_presence",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "nickname", name="uq_friend_snapshots_account_nickname"),
    )
    op.create_index(
        "ix_friend_snapshots_account_presence", "friend_snapshots", ["account_id", "presence"]
    )
    op.create_table(
        "presence_snapshots",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('unknown', 'online', 'away', 'busy', 'offline')",
            name="ck_presence_snapshots_state",
        ),
        sa.CheckConstraint(
            "source IN ('profile', 'friend_list', 'public_profile', 'status_image', 'operator')",
            name="ck_presence_snapshots_source",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("account_id"),
    )
    op.create_table(
        "subscription_entitlements",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("base_tier", sa.String(length=16), nullable=False),
        sa.Column("base_term", sa.String(length=16), nullable=False),
        sa.Column("evidence_source", sa.String(length=24), nullable=False),
        sa.Column("evidence_note", sa.String(length=300), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "base_tier IN ('unknown', 'free', 'pro', 'extreme', 'gold')",
            name="ck_subscription_entitlements_tier",
        ),
        sa.CheckConstraint(
            "base_term IN ('unknown', 'lifetime')",
            name="ck_subscription_entitlements_term",
        ),
        sa.CheckConstraint(
            "evidence_source IN ('unknown', 'operator_report', 'official_record', 'manual_entry')",
            name="ck_subscription_entitlements_source",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("account_id"),
    )
    op.create_table(
        "subscription_overlays",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("tier", sa.String(length=16), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_source", sa.String(length=24), nullable=False),
        sa.Column("evidence_note", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "tier IN ('pro', 'extreme', 'gold')", name="ck_subscription_overlays_tier"
        ),
        sa.CheckConstraint("expires_at > starts_at", name="ck_subscription_overlays_interval"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_subscription_overlays_account_interval",
        "subscription_overlays",
        ["account_id", "starts_at", "expires_at"],
    )
    op.create_table(
        "cloud_bots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", name="uq_cloud_bots_agent_id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "cloud_bot_status_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cloud_bot_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("raw_status", sa.String(length=80), nullable=True),
        sa.Column("reason", sa.String(length=160), nullable=True),
        sa.Column("uptime_seconds", sa.BigInteger(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('unknown', 'starting', 'disconnected', 'authenticating', 'authenticated', "
            "'room_session_closed', 'joining_room', 'online', 'paused', 'invalid_room_key', "
            "'bot_not_allowed', 'room_not_found')",
            name="ck_cloud_bot_status_state",
        ),
        sa.ForeignKeyConstraint(["cloud_bot_id"], ["cloud_bots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cloud_bot_status_snapshots_bot_observed",
        "cloud_bot_status_snapshots",
        ["cloud_bot_id", "observed_at"],
    )
    op.create_table(
        "store_catalog_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_item_id", sa.String(length=120), nullable=False),
        sa.Column("item_type", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("currency", sa.String(length=12), nullable=False),
        sa.Column("price_minor", sa.BigInteger(), nullable=False),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "item_type IN ('gift', 'sticker', 'chest', 'background', 'subscription')",
            name="ck_store_items_type",
        ),
        sa.CheckConstraint("price_minor >= 0", name="ck_store_items_price"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_item_id", "item_type", name="uq_store_items_source_type"),
    )
    op.create_index("ix_store_items_available", "store_catalog_items", ["available", "item_type"])
    op.create_table(
        "purchase_intents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("catalog_item_id", sa.Uuid(), nullable=False),
        sa.Column("item_name", sa.String(length=256), nullable=False),
        sa.Column("item_type", sa.String(length=24), nullable=False),
        sa.Column("currency", sa.String(length=12), nullable=False),
        sa.Column("price_minor", sa.BigInteger(), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("confirmation_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('pending_confirmation', 'confirmed', 'canceled', 'expired')",
            name="ck_purchase_intents_state",
        ),
        sa.CheckConstraint("price_minor >= 0", name="ck_purchase_intents_price"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["catalog_item_id"], ["store_catalog_items.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_purchase_intents_account_created", "purchase_intents", ["account_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_purchase_intents_account_created", table_name="purchase_intents")
    op.drop_table("purchase_intents")
    op.drop_index("ix_store_items_available", table_name="store_catalog_items")
    op.drop_table("store_catalog_items")
    op.drop_index(
        "ix_cloud_bot_status_snapshots_bot_observed", table_name="cloud_bot_status_snapshots"
    )
    op.drop_table("cloud_bot_status_snapshots")
    op.drop_table("cloud_bots")
    op.drop_index("ix_subscription_overlays_account_interval", table_name="subscription_overlays")
    op.drop_table("subscription_overlays")
    op.drop_table("subscription_entitlements")
    op.drop_table("presence_snapshots")
    op.drop_index("ix_friend_snapshots_account_presence", table_name="friend_snapshots")
    op.drop_table("friend_snapshots")
    op.drop_table("profile_snapshots")
