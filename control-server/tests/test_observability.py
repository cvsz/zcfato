from __future__ import annotations

import json
import logging
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from camfrog_control_server.app import create_app
from camfrog_control_server.config import Settings
from camfrog_control_server.models import Base
from camfrog_control_server.observability import (
    StructuredLogger,
    format_duration_ms,
    log_http_request,
    log_startup_event,
    redact_db_url,
    redact_sensitive_text,
)


def test_redact_sensitive_text_authorization_cookie_password() -> None:
    # Authorization header redaction
    auth_text = "GET / HTTP/1.1\r\nAuthorization: Bearer my-secret-token\r\nHost: example.com"
    redacted_auth = redact_sensitive_text(auth_text)
    assert "my-secret-token" not in redacted_auth
    assert "Authorization: [REDACTED]" in redacted_auth

    # Cookie headers redaction
    cookie_text = "Cookie: session_id=topsecret123; tracking=xyz"
    redacted_cookie = redact_sensitive_text(cookie_text)
    assert "session_id=topsecret123" not in redacted_cookie
    assert "Cookie: [REDACTED]" in redacted_cookie

    set_cookie_text = "Set-Cookie: user_token=secret_val; Secure; HttpOnly"
    redacted_set_cookie = redact_sensitive_text(set_cookie_text)
    assert "secret_val" not in redacted_set_cookie
    assert "Set-Cookie: [REDACTED]" in redacted_set_cookie

    # Password fields redaction
    pwd_query = "password=supersecretpassword"
    redacted_pwd = redact_sensitive_text(pwd_query)
    assert "supersecretpassword" not in redacted_pwd
    assert "password=[REDACTED]" in redacted_pwd

    pwd_header = "password: sensitive_pass_456"
    redacted_pwd_header = redact_sensitive_text(pwd_header)
    assert "sensitive_pass_456" not in redacted_pwd_header
    assert "password: [REDACTED]" in redacted_pwd_header

    # Other sensitive fields: csrf, access_token
    other_secrets = "csrf=csrf_secret_val; access_token=access_secret_val"
    redacted_other = redact_sensitive_text(other_secrets)
    assert "csrf_secret_val" not in redacted_other
    assert "access_secret_val" not in redacted_other
    assert "csrf=[REDACTED]" in redacted_other
    assert "access_token=[REDACTED]" in redacted_other


def test_redact_db_url_masks_credentials() -> None:
    # Standard postgresql with user and password
    raw_url = "postgresql://user:pass@host/db"
    redacted = redact_db_url(raw_url)
    assert "user" not in redacted
    assert "pass" not in redacted
    assert redacted == "postgresql://***:***@host/db"

    # URL with host, port, and database
    port_url = "postgresql://operator:secretpassword@db.example.internal:5432/production"
    redacted_port = redact_db_url(port_url)
    assert "operator" not in redacted_port
    assert "secretpassword" not in redacted_port
    assert redacted_port == "postgresql://***:***@db.example.internal:5432/production"

    # URL with driver prefix and query parameters
    psycopg_url = "postgresql+psycopg://admin:p%40ss@localhost:5432/mydb?sslmode=require"
    redacted_psycopg = redact_db_url(psycopg_url)
    assert "admin" not in redacted_psycopg
    assert "p%40ss" not in redacted_psycopg
    assert redacted_psycopg == "postgresql+psycopg://***:***@localhost:5432/mydb?sslmode=require"

    # URL with username only (no password)
    user_only_url = "postgresql://user@host/db"
    redacted_user_only = redact_db_url(user_only_url)
    assert "user" not in redacted_user_only
    assert redacted_user_only == "postgresql://***@host/db"

    # URL with no credentials
    no_cred_url = "postgresql://host:5432/mydb"
    assert redact_db_url(no_cred_url) == no_cred_url

    # SQLite URLs
    sqlite_url = "sqlite+pysqlite://"
    assert redact_db_url(sqlite_url) == sqlite_url

    # Empty and invalid strings
    assert redact_db_url("") == ""
    assert redact_db_url("not-a-url") == "not-a-url"


def test_log_startup_event_fires_without_error(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("test.startup.logger")
    with caplog.at_level(logging.INFO):
        log_startup_event(
            logger,
            version="1.2.3",
            db_url_redacted="postgresql://user:pass@host/db",
        )
    assert len(caplog.records) >= 1
    last_record = caplog.records[-1]
    data = json.loads(last_record.message)
    assert data["event"] == "startup"
    assert data["version"] == "1.2.3"
    assert "user" not in data["database_url"]
    assert "pass" not in data["database_url"]
    assert data["database_url"] == "postgresql://***:***@host/db"

    # Also test with StructuredLogger directly
    mock_log = MagicMock()
    mock_logger = logging.Logger("mock")
    mock_logger.log = mock_log
    structured = StructuredLogger(mock_logger)
    log_startup_event(
        structured,
        version="2.0.0",
        db_url_redacted="postgresql://alice:secret@prod:5432/camfrog",
    )
    assert mock_log.called
    emitted_json = mock_log.call_args[0][1]
    parsed = json.loads(emitted_json)
    assert parsed["event"] == "startup"
    assert parsed["version"] == "2.0.0"
    assert parsed["database_url"] == "postgresql://***:***@prod:5432/camfrog"
    assert "alice" not in parsed["database_url"]
    assert "secret" not in parsed["database_url"]


def test_structured_logger_emits_valid_json() -> None:
    captured: list[tuple[int, str]] = []

    class CapturingLogger(logging.Logger):
        def log(self, level: int, msg: object, *args: object, **kwargs: object) -> None:
            captured.append((level, str(msg)))

    raw_logger = CapturingLogger("structured_test")
    structured = StructuredLogger(raw_logger)

    # Info log with request_id and custom attributes
    output = structured.info(
        "user_login",
        request_id="req-12345",
        user_id="u_999",
        duration_ms=42.5,
    )
    assert len(captured) == 1
    level_no, log_line = captured[0]
    assert level_no == logging.INFO

    # Must be valid JSON
    data = json.loads(log_line)
    assert output == log_line
    assert data["event"] == "user_login"
    assert data["level"] == "INFO"
    assert data["request_id"] == "req-12345"
    assert data["user_id"] == "u_999"
    assert data["duration_ms"] == 42.5

    # Check ts is a valid ISO-8601 datetime
    parsed_dt = datetime.fromisoformat(data["ts"])
    assert parsed_dt.year >= 2026

    # Test warning, error, debug, critical methods
    structured.warning("disk_space_low", percent_free=5)
    warn_data = json.loads(captured[-1][1])
    assert warn_data["level"] == "WARNING"
    assert warn_data["event"] == "disk_space_low"
    assert warn_data["percent_free"] == 5
    assert warn_data["request_id"] is None

    structured.error("db_connection_failed", host="db1")
    err_data = json.loads(captured[-1][1])
    assert err_data["level"] == "ERROR"
    assert err_data["event"] == "db_connection_failed"
    assert err_data["host"] == "db1"

    structured.debug("cache_lookup", key="user:1")
    debug_data = json.loads(captured[-1][1])
    assert debug_data["level"] == "DEBUG"
    assert debug_data["key"] == "user:1"

    structured.critical("system_halted", reason="fatal error")
    crit_data = json.loads(captured[-1][1])
    assert crit_data["level"] == "CRITICAL"
    assert crit_data["reason"] == "fatal error"


def test_format_duration_ms_rounds_correctly() -> None:
    assert format_duration_ms(12.3456) == "12.35ms"
    assert format_duration_ms(12.3412) == "12.34ms"
    assert format_duration_ms(100.5) == "100.5ms"
    assert format_duration_ms(0.0) == "0.0ms"
    assert format_duration_ms(99.999) == "100.0ms"


def test_log_http_request_supports_structured_logger() -> None:
    captured: list[str] = []

    class MockLogger(logging.Logger):
        def log(self, level: int, msg: object, *args: object, **kwargs: object) -> None:
            captured.append(str(msg))

    mock = MockLogger("test_http")
    structured = StructuredLogger(mock)
    log_http_request(
        structured,
        request_id="req-abc",
        method="GET",
        path="/api/v1/overview",
        status_code=200,
        duration_ms=15.456,
    )
    assert len(captured) == 1
    data = json.loads(captured[0])
    assert data["event"] == "http_request"
    assert data["request_id"] == "req-abc"
    assert data["method"] == "GET"
    assert data["path"] == "/api/v1/overview"
    assert data["status_code"] == 200
    assert data["duration_ms"] == 15.46


def test_config_log_settings_and_validation() -> None:
    # Default values
    s = Settings(
        database_url="sqlite+pysqlite://",
        admin_api_token="a" * 32,
        jwt_signing_secret="b" * 32,
    )
    assert s.log_level == "INFO"
    assert s.log_format == "json"
    assert s.cors_origins == []
    assert s.trusted_hosts == []

    # Custom valid values
    s2 = Settings(
        database_url="sqlite+pysqlite://",
        admin_api_token="a" * 32,
        jwt_signing_secret="b" * 32,
        log_level="DEBUG",
        log_format="text",
        cors_origins=["http://localhost:3000"],
        trusted_hosts=["localhost", "127.0.0.1"],
    )
    assert s2.log_level == "DEBUG"
    assert s2.log_format == "text"
    assert s2.cors_origins == ["http://localhost:3000"]
    assert s2.trusted_hosts == ["localhost", "127.0.0.1"]

    # Invalid log_level raises ValueError
    with pytest.raises(ValueError, match="CONTROL_LOG_LEVEL"):
        Settings(
            database_url="sqlite+pysqlite://",
            admin_api_token="a" * 32,
            jwt_signing_secret="b" * 32,
            log_level="VERBOSE",
        )

    # Invalid log_format raises ValueError
    with pytest.raises(ValueError, match="CONTROL_LOG_FORMAT"):
        Settings(
            database_url="sqlite+pysqlite://",
            admin_api_token="a" * 32,
            jwt_signing_secret="b" * 32,
            log_format="xml",  # type: ignore[arg-type]
        )


def test_cors_middleware_and_security_headers() -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    settings = Settings(
        database_url="sqlite+pysqlite://",
        admin_api_token="a" * 32,
        jwt_signing_secret="b" * 32,
        command_lease_seconds=15,
        command_max_attempts=3,
        cors_origins=["http://localhost:3000"],
    )
    app = create_app(settings, engine=engine)
    with TestClient(app) as client:
        # Preflight OPTIONS request
        cors_res = client.options(
            "/api/v1/overview",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert cors_res.status_code == 200
        assert cors_res.headers.get("access-control-allow-origin") == "http://localhost:3000"

        # Regular GET request to healthz check security headers
        health_res = client.get("/healthz")
        assert health_res.status_code == 200
        assert health_res.headers.get("x-content-type-options") == "nosniff"
        assert health_res.headers.get("referrer-policy") == "no-referrer"

        # API unauthenticated request also contains security headers
        api_res = client.get("/api/v1/overview")
        assert api_res.status_code == 401
        assert api_res.headers.get("x-content-type-options") == "nosniff"
        assert api_res.headers.get("referrer-policy") == "no-referrer"
        assert api_res.headers.get("cache-control") == "no-store"

    engine.dispose()
