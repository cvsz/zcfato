"""Small token helpers. Raw agent credentials are issued once and never persisted."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from typing import Any


def new_agent_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def issue_dashboard_token(secret: str, *, ttl_seconds: int = 900, now: int | None = None) -> str:
    """Issue a short-lived, fixed-algorithm dashboard bearer token."""
    issued_at = int(time.time()) if now is None else now
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64url(
        json.dumps(
            {
                "aud": "camfrog-dashboard",
                "exp": issued_at + ttl_seconds,
                "iat": issued_at,
                "iss": "zeaz-camfrog-control",
                "sub": "operator",
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    )
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = _b64url(hmac_sha256(secret, signing_input))
    return f"{header}.{payload}.{signature}"


def verify_dashboard_token(
    token: str, secret: str, *, now: int | None = None
) -> dict[str, Any] | None:
    """Verify only locally issued HS256 dashboard JWTs with fixed issuer and audience."""
    if len(token) > 4096:
        return None
    parts = token.split(".")
    if len(parts) != 3:
        return None
    header_part, payload_part, supplied_signature = parts
    signing_input = f"{header_part}.{payload_part}".encode("ascii", errors="ignore")
    expected_signature = _b64url(hmac_sha256(secret, signing_input))
    if not secrets.compare_digest(supplied_signature, expected_signature):
        return None
    try:
        header = json.loads(_b64url_decode(header_part))
        payload = json.loads(_b64url_decode(payload_part))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(header, dict) or header != {"alg": "HS256", "typ": "JWT"}:
        return None
    if not isinstance(payload, dict):
        return None
    current_time = int(time.time()) if now is None else now
    if (
        payload.get("iss") != "zeaz-camfrog-control"
        or payload.get("aud") != "camfrog-dashboard"
        or payload.get("sub") != "operator"
        or not isinstance(payload.get("iat"), int)
        or not isinstance(payload.get("exp"), int)
        or payload["iat"] > current_time + 30
        or payload["exp"] <= current_time
        or payload["exp"] - payload["iat"] > 3600
    ):
        return None
    return payload


def hmac_sha256(secret: str, data: bytes) -> bytes:
    import hmac

    return hmac.new(secret.encode("utf-8"), data, hashlib.sha256).digest()


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
