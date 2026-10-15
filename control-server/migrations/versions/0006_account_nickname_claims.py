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
    op.create_table(
        "account_nickname_claims",
        sa.Column("nickname_key", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("nickname_key"),
    )

    connection = op.get_bind()
    accounts = sa.table(
        "accounts",
        sa.column("nickname", sa.String(length=256)),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    claims = sa.table(
        "account_nickname_claims",
        sa.column("nickname_key", sa.String(length=64)),
    )
    seen: set[str] = set()
    pending: list[dict[str, str]] = []
    result = connection.execute(
        sa.select(accounts.c.nickname).order_by(accounts.c.created_at, accounts.c.nickname)
    )
    for row in result:
        key = _nickname_key(row.nickname)
        if not key or key in seen:
            continue
        seen.add(key)
        pending.append({"nickname_key": key})
        if len(pending) >= 1000:
            connection.execute(claims.insert(), pending)
            pending.clear()
    if pending:
        connection.execute(claims.insert(), pending)


def downgrade() -> None:
    op.drop_table("account_nickname_claims")
