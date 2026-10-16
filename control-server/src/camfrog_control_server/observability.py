"""Small redaction and structured HTTP access-log helpers."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

_HEADER_SECRET_PATTERN = re.compile(r"(?i)(authorization|cookie|set-cookie)(\s*[=:]\s*)[^\r\n]+")
_VALUE_SECRET_PATTERN = re.compile(
    r"(?i)(csrf|captcha|password|room[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"stripe[_-]?token)(\s*[=:]\s*)([^\s,;]+)"
)


def redact_sensitive_text(value: str) -> str:
    """Redact common secret assignments before text enters an application log."""
    value = _HEADER_SECRET_PATTERN.sub(r"\1\2[REDACTED]", value)
    return _VALUE_SECRET_PATTERN.sub(r"\1\2[REDACTED]", value)


def format_duration_ms(ms: float) -> str:
    """Format duration in milliseconds rounded to two decimal places."""
    return f"{round(ms, 2)}ms"


def redact_db_url(url: str) -> str:
    """Mask credentials (username, password) in database URLs including query parameters."""
    if not url or (
        "@" not in url
        and not any(s in url.lower() for s in ("password=", "secret=", "token=", "key="))
    ):
        return url
    parsed = urlsplit(url)
    netloc = parsed.netloc
    if parsed.netloc and "@" in parsed.netloc:
        userinfo, hostinfo = parsed.netloc.rsplit("@", 1)
        masked_userinfo = "***:***" if ":" in userinfo else "***"
        netloc = f"{masked_userinfo}@{hostinfo}"
    query = parsed.query
    if query:
        qs_pairs: list[str] = []
        for pair in query.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                if any(s in k.lower() for s in ("pass", "secret", "token", "key")):
                    qs_pairs.append(f"{k}=[REDACTED]")
                else:
                    qs_pairs.append(pair)
            else:
                qs_pairs.append(pair)
        query = "&".join(qs_pairs)
    return urlunsplit((parsed.scheme, netloc, parsed.path, query, parsed.fragment))


class StructuredLogger:
    """Emits JSON log lines with schema fields: {"ts", "level", "event", "request_id", ...}."""

    def __init__(
        self,
        logger_or_name: logging.Logger | str | None = None,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        if logger is not None:
            self._logger = logger
        elif isinstance(logger_or_name, logging.Logger):
            self._logger = logger_or_name
        elif isinstance(logger_or_name, str):
            self._logger = logging.getLogger(logger_or_name)
        elif logger_or_name is None:
            self._logger = logging.getLogger("camfrog_control_server")
        else:
            self._logger = logger_or_name

    @property
    def logger(self) -> logging.Logger:
        return self._logger

    def log(
        self,
        level: int | str,
        event: str,
        *,
        request_id: str | None = None,
        **extra: Any,
    ) -> str:
        if isinstance(level, str):
            level_name = level.upper()
            level_no = getattr(logging, level_name, logging.INFO)
        else:
            level_no = level
            name = logging.getLevelName(level_no)
            level_name = name if isinstance(name, str) else str(name)

        if request_id is None and "request_id" in extra:
            req_val = extra.pop("request_id")
            request_id = str(req_val) if req_val is not None else None

        if "extra" in extra and isinstance(extra["extra"], dict):
            extra_dict = extra.pop("extra")
            for k, v in extra_dict.items():
                extra.setdefault(k, v)

        record: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": level_name,
            "event": event,
            "request_id": request_id,
            **extra,
        }
        line = json.dumps(record, default=str, separators=(",", ":"))
        self._logger.log(level_no, line)
        return line

    def info(self, event: str, *, request_id: str | None = None, **extra: Any) -> str:
        return self.log(logging.INFO, event, request_id=request_id, **extra)

    def debug(self, event: str, *, request_id: str | None = None, **extra: Any) -> str:
        return self.log(logging.DEBUG, event, request_id=request_id, **extra)

    def warning(self, event: str, *, request_id: str | None = None, **extra: Any) -> str:
        return self.log(logging.WARNING, event, request_id=request_id, **extra)

    def error(self, event: str, *, request_id: str | None = None, **extra: Any) -> str:
        return self.log(logging.ERROR, event, request_id=request_id, **extra)

    def critical(self, event: str, *, request_id: str | None = None, **extra: Any) -> str:
        return self.log(logging.CRITICAL, event, request_id=request_id, **extra)

    def exception(self, event: str, *, request_id: str | None = None, **extra: Any) -> str:
        if "exc_info" not in extra:
            extra["exc_info"] = True
        return self.log(logging.ERROR, event, request_id=request_id, **extra)

    emit = log


def log_startup_event(
    logger: logging.Logger | StructuredLogger,
    *,
    version: str,
    db_url_redacted: str,
) -> None:
    """Log server start with version and redacted DB URL."""
    safe_db_url = redact_db_url(db_url_redacted)
    if isinstance(logger, StructuredLogger):
        logger.info(
            "startup",
            version=version,
            database_url=safe_db_url,
            db_url_redacted=safe_db_url,
        )
    elif hasattr(logger, "info"):
        record: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": "INFO",
            "event": "startup",
            "request_id": None,
            "version": version,
            "database_url": safe_db_url,
            "db_url_redacted": safe_db_url,
        }
        logger.info(json.dumps(record, default=str, separators=(",", ":")))


def log_http_request(
    logger: logging.Logger | StructuredLogger,
    *,
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
) -> None:
    """Emit only allowlisted request metadata; never include query, headers, or bodies."""
    record: dict[str, Any] = {
        "ts": datetime.now(UTC).isoformat(),
        "level": "INFO",
        "event": "http_request",
        "request_id": request_id,
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
    }
    if isinstance(logger, StructuredLogger):
        logger.info(
            "http_request",
            request_id=request_id,
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=round(duration_ms, 2),
        )
    else:
        logger.info(redact_sensitive_text(json.dumps(record, separators=(",", ":"))))
