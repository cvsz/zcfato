"""Small redaction and structured HTTP access-log helpers."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

_HEADER_SECRET_PATTERN = re.compile(r"(?i)(authorization|cookie|set-cookie)(\s*[=:]\s*)[^\r\n]+")
_VALUE_SECRET_PATTERN = re.compile(
    r"(?i)(csrf|captcha|password|room[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"stripe[_-]?token)(\s*[=:]\s*)([^\s,;]+)"
)


def redact_sensitive_text(value: str) -> str:
    """Redact common secret assignments before text enters an application log."""
    value = _HEADER_SECRET_PATTERN.sub(r"\1\2[REDACTED]", value)
    return _VALUE_SECRET_PATTERN.sub(r"\1\2[REDACTED]", value)


def log_http_request(
    logger: logging.Logger,
    *,
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
) -> None:
    """Emit only allowlisted request metadata; never include query, headers, or bodies."""
    record: dict[str, Any] = {
        "event": "http_request",
        "request_id": request_id,
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
    }
    logger.info(redact_sensitive_text(json.dumps(record, separators=(",", ":"))))
