from __future__ import annotations

import secrets
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from camfrog_control_server.app import create_app
from camfrog_control_server.config import Settings
from camfrog_control_server.models import Base
from camfrog_control_server.security import issue_dashboard_token

TEST_ADMIN_API_TOKEN = secrets.token_urlsafe(48)
TEST_JWT_SIGNING_SECRET = secrets.token_urlsafe(48)


@pytest.fixture
def api_client() -> Iterator[tuple[TestClient, object, str]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    settings = Settings(
        database_url="sqlite+pysqlite://",
        admin_api_token=TEST_ADMIN_API_TOKEN,
        jwt_signing_secret=TEST_JWT_SIGNING_SECRET,
        command_lease_seconds=15,
        command_max_attempts=3,
    )
    app = create_app(settings, engine=engine)
    with TestClient(app) as client:
        admin_jwt = issue_dashboard_token(settings.jwt_signing_secret)
        yield client, engine, admin_jwt
    engine.dispose()
