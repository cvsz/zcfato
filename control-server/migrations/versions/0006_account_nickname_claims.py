"""Protect new account creation from case-insensitive nickname duplicates.

Revision ID: 0006_account_nickname_claims
Revises: 0005_internal_chat
Create Date: 2026-10-16
"""

from __future__ import annotations

import hashlib
import unicodedata

import sqlalchemy as sa
from alembic import op

revision = "0006_account_nickname_claims"
down_revision = "0005_internal_chat"
branch_labels = None
depends_on = None


def _nickname_key(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value.strip()).casefold()
    normalized = unicodedata.normalize("NFC", normalized)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        # Keep legacy account writers from committing between the backfill scan
        # and the constraint that requires every account to have a claim key.
        # The lock is held until Alembic commits this migration transaction.
        connection.exec_driver_sql("LOCK TABLE accounts IN ACCESS EXCLUSIVE MODE")

    op.create_table(
        "account_nickname_claims",
        sa.Column("nickname_key", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("nickname_key"),
    )

    op.add_column("accounts", sa.Column("nickname_key", sa.String(length=64), nullable=True))
    accounts = sa.table(
        "accounts",
        sa.column("id", sa.Uuid()),
        sa.column("nickname", sa.String(length=256)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("nickname_key", sa.String(length=64)),
    )
    claims = sa.table(
        "account_nickname_claims",
        sa.column("nickname_key", sa.String(length=64)),
    )
    seen: set[str] = set()
    pending: list[dict[str, str]] = []
    pending_account_updates: list[dict[str, object]] = []
    update_accounts = accounts.update().where(
        accounts.c.id == sa.bindparam("account_id_param")
    ).values(nickname_key=sa.bindparam("nickname_key_param"))
    result = connection.execute(
        sa.select(accounts.c.id, accounts.c.nickname).order_by(
            accounts.c.created_at, accounts.c.nickname, accounts.c.id
        )
    )
    for row in result:
        key = _nickname_key(row.nickname)
        pending_account_updates.append(
            {"account_id_param": row.id, "nickname_key_param": key}
        )
        if len(pending_account_updates) >= 1000:
            connection.execute(update_accounts, pending_account_updates)
            pending_account_updates.clear()
        if not key or key in seen:
            continue
        seen.add(key)
        pending.append({"nickname_key": key})
        if len(pending) >= 1000:
            connection.execute(claims.insert(), pending)
            pending.clear()
    if pending:
        connection.execute(claims.insert(), pending)
    if pending_account_updates:
        connection.execute(update_accounts, pending_account_updates)
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.alter_column(
            "nickname_key", existing_type=sa.String(length=64), nullable=False
        )
    op.create_index("ix_accounts_nickname_key", "accounts", ["nickname_key"])


def downgrade() -> None:
    op.drop_index("ix_accounts_nickname_key", table_name="accounts")
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.drop_column("nickname_key")
    op.drop_table("account_nickname_claims")
