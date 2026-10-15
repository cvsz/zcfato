from __future__ import annotations

import secrets
from datetime import timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from camfrog_control_server.models import Agent, ControlCommand, utcnow


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _provision(
    api_client: tuple[TestClient, object, str],
) -> tuple[TestClient, object, str, str, str]:
    client, engine, admin_token = api_client
    created = client.post(
        "/api/v1/agents", headers=_headers(admin_token), json={"name": "agent-01"}
    )
    assert created.status_code == 201
    agent = created.json()
    account = client.post(
        "/api/v1/accounts",
        headers=_headers(admin_token),
        json={"nickname": "test-account", "agent_id": agent["id"]},
    )
    assert account.status_code == 201
    return client, engine, admin_token, agent["agent_token"], account.json()["id"]


def test_health_docs_and_admin_auth(api_client: tuple[TestClient, object, str]) -> None:
    client, _, admin_token = api_client
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ready"}
    assert client.get("/readyz").json() == {"status": "ready"}
    assert client.get("/docs").status_code == 404
    unauthenticated = client.get("/api/v1/overview")
    assert unauthenticated.status_code == 401
    assert unauthenticated.headers["cache-control"] == "no-store"
    wrong_headers = _headers(secrets.token_urlsafe(48))
    assert client.get("/api/v1/overview", headers=wrong_headers).status_code == 401
    authenticated = client.get("/api/v1/overview", headers=_headers(admin_token))
    assert authenticated.status_code == 200
    assert authenticated.headers["cache-control"] == "no-store"


def test_dashboard_is_zchat_branded_and_serves_accessible_assets(
    api_client: tuple[TestClient, object, str],
) -> None:
    client, _, _ = api_client
    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "<title>ZChat Control</title>" in dashboard.text
    assert 'aria-label="Command queue" tabindex="0"' in dashboard.text
    stylesheet = client.get("/dashboard/assets/dashboard.css")
    assert stylesheet.status_code == 200
    assert "min-width: 640px" in stylesheet.text


def test_bootstrap_admin_token_exchanges_for_short_lived_jwt(
    api_client: tuple[TestClient, object, str],
) -> None:
    client, _, jwt_token = api_client
    bootstrap = client.app.state.settings.admin_api_token
    session = client.post("/api/v1/auth/session", headers=_headers(bootstrap))
    assert session.status_code == 200
    data = session.json()
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 900
    assert client.get("/api/v1/overview", headers=_headers(data["access_token"])).status_code == 200
    assert client.get("/api/v1/overview", headers=_headers(bootstrap)).status_code == 401
    assert client.get("/api/v1/overview", headers=_headers(jwt_token + "x")).status_code == 401


def test_agent_token_is_one_time_and_commands_are_scoped(
    api_client: tuple[TestClient, object, str],
) -> None:
    client, engine, admin_token, agent_token, account_id = _provision(api_client)
    headers = _headers(admin_token)

    listed = client.get("/api/v1/agents", headers=headers)
    assert listed.status_code == 200
    assert "agent_token" not in listed.text
    with Session(engine) as session:
        saved_hash = session.scalar(select(Agent.token_hash))
        assert saved_hash is not None
        assert saved_hash != agent_token

    queued = client.post(
        "/api/v1/commands",
        headers=headers,
        json={"account_id": account_id, "operation": "join_room", "payload": {"room": "ZeaZDev"}},
    )
    assert queued.status_code == 201
    assert queued.json()["state"] == "pending"

    poll = client.get("/api/v1/agent/commands/next", headers=_headers(agent_token))
    assert poll.status_code == 200
    command = poll.json()["command"]
    assert command["operation"] == "join_room"
    assert command["payload"] == {"room": "ZeaZDev"}

    wrong_result = client.post(
        f"/api/v1/agent/commands/{command['id']}/result",
        headers=_headers(agent_token),
        json={
            "claim_token": secrets.token_urlsafe(48),
            "state": "failed",
            "code": "execution_failed",
        },
    )
    assert wrong_result.status_code == 409

    result = client.post(
        f"/api/v1/agent/commands/{command['id']}/result",
        headers=_headers(agent_token),
        json={
            "claim_token": command["claim_token"],
            "state": "failed",
            "code": "provider_not_configured",
        },
    )
    assert result.status_code == 204
    replay = client.post(
        f"/api/v1/agent/commands/{command['id']}/result",
        headers=_headers(agent_token),
        json={
            "claim_token": command["claim_token"],
            "state": "failed",
            "code": "provider_not_configured",
        },
    )
    assert replay.status_code == 409

    audit = client.get("/api/v1/audit", headers=headers)
    assert audit.status_code == 200
    assert agent_token not in audit.text
    assert command["claim_token"] not in audit.text
    with Session(engine) as session:
        saved_command = session.get(ControlCommand, UUID(command["id"]))
        assert saved_command is not None
        assert saved_command.claim_token_hash is None
        assert saved_command.state == "failed"


def test_expired_lease_cannot_submit_result_and_can_be_reclaimed(
    api_client: tuple[TestClient, object, str],
) -> None:
    client, engine, admin_token, agent_token, account_id = _provision(api_client)
    queued = client.post(
        "/api/v1/commands",
        headers=_headers(admin_token),
        json={"account_id": account_id, "operation": "launch"},
    )
    command_id = queued.json()["id"]
    agent_headers = _headers(agent_token)
    first = client.get("/api/v1/agent/commands/next", headers=agent_headers).json()["command"]

    with Session(engine) as session:
        command = session.get(ControlCommand, UUID(command_id))
        assert command is not None
        command.claim_expires_at = utcnow() - timedelta(seconds=1)
        session.commit()

    stale = client.post(
        f"/api/v1/agent/commands/{command_id}/result",
        headers=agent_headers,
        json={
            "claim_token": first["claim_token"],
            "state": "failed",
            "code": "execution_failed",
        },
    )
    assert stale.status_code == 409

    second = client.get("/api/v1/agent/commands/next", headers=agent_headers).json()["command"]
    assert second["id"] == command_id
    assert second["claim_token"] != first["claim_token"]


def test_purchase_and_unrecognized_operations_are_rejected(
    api_client: tuple[TestClient, object, str],
) -> None:
    client, _, admin_token, _, account_id = _provision(api_client)
    headers = _headers(admin_token)
    purchase = client.post(
        "/api/v1/commands",
        headers=headers,
        json={"account_id": account_id, "operation": "purchase", "payload": {"item_id": 7}},
    )
    assert purchase.status_code == 422

    extra_room_data = client.post(
        "/api/v1/commands",
        headers=headers,
        json={
            "account_id": account_id,
            "operation": "join_room",
            "payload": {"room": "ZeaZDev", "password": "ignored"},
        },
    )
    assert extra_room_data.status_code == 422


def test_revoked_agent_cannot_heartbeat_or_poll(api_client: tuple[TestClient, object, str]) -> None:
    client, _, admin_token, agent_token, _ = _provision(api_client)
    agent_id = client.get("/api/v1/agents", headers=_headers(admin_token)).json()[0]["id"]
    revoked = client.post(f"/api/v1/agents/{agent_id}/revoke", headers=_headers(admin_token))
    assert revoked.status_code == 200
    assert (
        client.post(
            "/api/v1/agent/heartbeat",
            headers=_headers(agent_token),
            json={"state": "running"},
        ).status_code
        == 401
    )


def test_account_agent_assignment_is_one_to_one_and_cancels_pending_commands(
    api_client: tuple[TestClient, object, str],
) -> None:
    client, _, admin_token, _, account_id = _provision(api_client)
    headers = _headers(admin_token)
    first_agent_id = next(
        item["id"]
        for item in client.get("/api/v1/agents", headers=headers).json()
        if item["name"] == "agent-01"
    )
    second_agent = client.post("/api/v1/agents", headers=headers, json={"name": "agent-02"}).json()
    other_account = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"nickname": "second-account", "agent_id": second_agent["id"]},
    )
    assert other_account.status_code == 201

    second_agent_conflict = client.patch(
        f"/api/v1/accounts/{account_id}/agent",
        headers=headers,
        json={"agent_id": second_agent["id"]},
    )
    assert second_agent_conflict.status_code == 409

    queued = client.post(
        "/api/v1/commands",
        headers=headers,
        json={"account_id": account_id, "operation": "stop"},
    )
    assert queued.status_code == 201
    reassigned = client.patch(
        f"/api/v1/accounts/{account_id}/agent",
        headers=headers,
        json={"agent_id": None},
    )
    assert reassigned.status_code == 200
    assert reassigned.json()["agent_id"] is None

    commands = client.get("/api/v1/commands", headers=headers).json()
    assert commands[0]["state"] == "canceled"
    assert first_agent_id != second_agent["id"]


def test_revoking_agent_cancels_claimed_command_and_invalidates_lease(
    api_client: tuple[TestClient, object, str],
) -> None:
    client, engine, admin_token, agent_token, account_id = _provision(api_client)
    headers = _headers(admin_token)
    queued = client.post(
        "/api/v1/commands",
        headers=headers,
        json={"account_id": account_id, "operation": "launch"},
    )
    assert queued.status_code == 201
    command_id = queued.json()["id"]

    claimed = client.get("/api/v1/agent/commands/next", headers=_headers(agent_token))
    assert claimed.status_code == 200
    assert claimed.json()["command"]["id"] == command_id

    agent_id = client.get("/api/v1/agents", headers=headers).json()[0]["id"]
    revoked = client.post(f"/api/v1/agents/{agent_id}/revoke", headers=headers)
    assert revoked.status_code == 200

    with Session(engine) as session:
        command = session.get(ControlCommand, UUID(command_id))
        assert command is not None
        assert command.state == "canceled"
        assert command.claim_token_hash is None
        assert command.claim_expires_at is None
        assert command.finished_at is not None


def test_expired_lease_cleanup_is_scoped_to_polling_agent(
    api_client: tuple[TestClient, object, str],
) -> None:
    client, engine, admin_token, first_token, _ = _provision(api_client)
    headers = _headers(admin_token)

    created = client.post(
        "/api/v1/agents",
        headers=headers,
        json={"name": "agent-02"},
    )
    assert created.status_code == 201
    second = created.json()
    account = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"nickname": "second-account", "agent_id": second["id"]},
    )
    assert account.status_code == 201

    queued = client.post(
        "/api/v1/commands",
        headers=headers,
        json={"account_id": account.json()["id"], "operation": "launch"},
    )
    assert queued.status_code == 201
    command_id = queued.json()["id"]

    claimed = client.get(
        "/api/v1/agent/commands/next",
        headers=_headers(second["agent_token"]),
    )
    assert claimed.status_code == 200
    assert claimed.json()["command"]["id"] == command_id

    with Session(engine) as session:
        command = session.get(ControlCommand, UUID(command_id))
        assert command is not None
        command.claim_attempts = 3
        command.claim_expires_at = utcnow() - timedelta(seconds=1)
        session.commit()

    unrelated_poll = client.get(
        "/api/v1/agent/commands/next",
        headers=_headers(first_token),
    )
    assert unrelated_poll.status_code == 200
    assert unrelated_poll.json()["command"] is None

    with Session(engine) as session:
        command = session.get(ControlCommand, UUID(command_id))
        assert command is not None
        assert command.state == "claimed"
        assert command.claim_token_hash is not None

    owner_poll = client.get(
        "/api/v1/agent/commands/next",
        headers=_headers(second["agent_token"]),
    )
    assert owner_poll.status_code == 200
    assert owner_poll.json()["command"] is None

    with Session(engine) as session:
        command = session.get(ControlCommand, UUID(command_id))
        assert command is not None
        assert command.state == "failed"
        assert command.result_code == "lease_expired"
        assert command.claim_token_hash is None
        assert command.claim_expires_at is None
