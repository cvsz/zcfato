from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from camfrog_control_server.account_identity import account_nickname_key
from camfrog_control_server.models import Account, AccountNicknameClaim, utcnow


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_account_nickname_key_normalizes_unicode_case_and_whitespace() -> None:
    assert len(account_nickname_key("  Straẞe  ")) == 64
    assert account_nickname_key("  Straẞe  ") == account_nickname_key("STRASSE")
    assert account_nickname_key("Cafe\u0301") == account_nickname_key("Café")


def test_account_creation_rejects_case_insensitive_duplicates_without_rotating_agent_token(
    api_client: tuple[TestClient, object, str],
) -> None:
    client, engine, admin_token = api_client
    headers = _headers(admin_token)
    first_agent = client.post(
        "/api/v1/agents", headers=headers, json={"name": "duplicate-owner"}
    ).json()
    first_account = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"nickname": "Seaza", "agent_id": first_agent["id"]},
    )
    assert first_account.status_code == 201

    second_agent = client.post(
        "/api/v1/agents", headers=headers, json={"name": "duplicate-candidate"}
    ).json()
    duplicate = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"nickname": "  sEaZa  ", "agent_id": second_agent["id"]},
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Account nickname is already registered."
    still_valid = client.post(
        "/api/v1/agent/heartbeat",
        headers=_headers(second_agent["agent_token"]),
        json={"state": "running"},
    )
    assert still_valid.status_code == 200

    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Account)) == 1
        assert session.scalar(select(func.count()).select_from(AccountNicknameClaim)) == 1


def test_nickname_claim_migration_preserves_legacy_duplicate_accounts(
    tmp_path: Path, monkeypatch,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    control_server = repo_root / "control-server"
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'migration.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    config = Config(str(control_server / "alembic.ini"))
    config.set_main_option("script_location", str(control_server / "migrations"))
    command.upgrade(config, "0005_internal_chat")

    engine = create_engine(database_url)
    with Session(engine) as session:
        session.add_all(
            [
                Account(nickname="Seaza", created_at=utcnow()),
                Account(nickname="seaza", created_at=utcnow()),
            ]
        )
        session.commit()
    engine.dispose()

    command.upgrade(config, "head")
    assert not logging.getLogger("camfrog_control_server.http").disabled

    migrated_engine = create_engine(database_url)
    try:
        with Session(migrated_engine) as session:
            assert session.scalar(select(func.count()).select_from(Account)) == 2
            claim = session.get(AccountNicknameClaim, account_nickname_key("Seaza"))
            assert claim is not None
    finally:
        migrated_engine.dispose()
