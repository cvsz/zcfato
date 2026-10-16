"""Canonical account identity keys used to prevent duplicate account records."""

from __future__ import annotations

import hashlib
import unicodedata


def account_nickname_key(nickname: str) -> str:
    """Return a whitespace-trimmed, Unicode-normalized, case-insensitive nickname key."""
    if not isinstance(nickname, str):
        raise TypeError("Account nickname must be text.")
    normalized = unicodedata.normalize("NFC", nickname.strip()).casefold()
    normalized = unicodedata.normalize("NFC", normalized)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
