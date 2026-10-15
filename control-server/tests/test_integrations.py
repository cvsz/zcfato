from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from camfrog_control_server.models import AccountRuntimeSnapshot, utcnow


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _account_and_agent(client: TestClient, admin_token: str) -> tuple[dict, dict]:
    headers = _headers(admin_token)
    agent = client.post("/api/v1/agents", headers=headers, json={"name": "agent-integration"})
    assert agent.status_code == 201
    account = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"nickname": "integration-user", "agent_id": agent.json()["id"]},
    )
    assert account.status_code == 201
    account_data = account.json()
    return {**agent.json(), "agent_token": account_data["agent_token"]}, account_data


def test_dashboard_is_served_with_security_headers(
    api_client: tuple[TestClient, object, str],
) -> None:
    client, _, _ = api_client
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "ZChat Control" in response.text
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    script = client.get("/dashboard/assets/dashboard.js")
    assert script.status_code == 200
    assert "textContent" in script.text


def test_agent_snapshot_populates_profile_friends_and_presence(
    api_client: tuple[TestClient, object, str],
) -> None:
    client, _, admin_token = api_client
    agent, account = _account_and_agent(client, admin_token)
    observed_at = datetime.now(UTC).isoformat()
    uploaded = client.put(
        "/api/v1/agent/accounts/snapshot",
        headers=_headers(agent["agent_token"]),
        json={
            "account_id": account["id"],
            "observed_at": observed_at,
            "profile": {
                "nickname_color": "green",
                "client_presence": "online",
                "subscription_type": "pro",
                "xp_count": 250,
                "summary": {
                    "balance": {"coins": 350, "points": 12},
                    "reward_program": {"engine": "internal", "enabled": True, "balance": 4},
                    "gift_count": 2,
                    "friend_counts": {"all": 4, "online": 1, "added": 1},
                    "have_room": True,
                    "notifications_count": 3,
                },
            },
            "auth": {
                "nav_user_logged": True,
                "login_form_visible": False,
                "external_data_type": "profile",
                "csrf_present": True,
                "observed_at": observed_at,
            },
            "friends": [
                {"nickname": "FriendOne", "presence": "away"},
                {"nickname": "FriendTwo", "presence": "offline"},
            ],
        },
    )
    assert uploaded.status_code == 204

    headers = _headers(admin_token)
    profile = client.get(f"/api/v1/accounts/{account['id']}/profile", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["client_presence"] == "online"
    assert profile.json()["subscription_type"] == "pro"
    assert profile.json()["auth_state"] == "authenticated"
    assert profile.json()["summary"]["balance"]["coins"] == 350
    all_friends = client.get(f"/api/v1/accounts/{account['id']}/friends", headers=headers)
    online_friends = client.get(
        f"/api/v1/accounts/{account['id']}/friends?online_only=true", headers=headers
    )
    assert len(all_friends.json()) == 2
    assert [item["nickname"] for item in online_friends.json()] == ["FriendOne"]
    presence = client.get("/api/v1/presence/integration-user", headers=headers)
    assert presence.json()["state"] == "online"

    other_agent = client.post(
        "/api/v1/agents", headers=headers, json={"name": "other-account-agent"}
    ).json()
    other_account = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"nickname": "other-account", "agent_id": other_agent["id"]},
    )
    assert other_account.status_code == 201
    forbidden = client.put(
        "/api/v1/agent/accounts/snapshot",
        headers=_headers(other_account.json()["agent_token"]),
        json={
            "account_id": account["id"],
            "profile": {"client_presence": "offline"},
            "friends": [],
        },
    )
    assert forbidden.status_code == 404


def test_auth_detector_handles_public_and_unrecognized_pages(
    api_client: tuple[TestClient, object, str],
) -> None:
    client, _, admin_token = api_client
    agent, account = _account_and_agent(client, admin_token)
    headers = _headers(agent["agent_token"])
    public = client.put(
        "/api/v1/agent/accounts/snapshot",
        headers=headers,
        json={
            "account_id": account["id"],
            "profile": {},
            "auth": {"external_data_type": "public", "csrf_present": False},
        },
    )
    assert public.status_code == 204
    state = client.get(
        f"/api/v1/accounts/{account['id']}/auth-state", headers=_headers(admin_token)
    )
    assert state.json()["state"] == "public"
    assert state.json()["csrf_present"] is False


def test_heartbeat_reports_account_process_state_and_stale_reads_as_unknown(
    api_client: tuple[TestClient, object, str],
) -> None:
    client, engine, admin_token = api_client
    agent, account = _account_and_agent(client, admin_token)
    heartbeat = client.post(
        "/api/v1/agent/heartbeat",
        headers=_headers(agent["agent_token"]),
        json={"state": "running", "client_process_state": "running"},
    )
    assert heartbeat.status_code == 200
    assert heartbeat.json()["account_id"] == account["id"]
    assert heartbeat.json()["client_process_state"] == "running"

    headers = _headers(admin_token)
    runtime_path = f"/api/v1/accounts/{account['id']}/runtime"
    current = client.get(runtime_path, headers=headers)
    assert current.status_code == 200
    assert current.json()["process_state"] == "running"
    assert current.json()["room_state"] == "unknown"

    with Session(engine) as session:
        snapshot = session.get(AccountRuntimeSnapshot, UUID(account["id"]))
        assert snapshot is not None
        snapshot.observed_at = utcnow() - timedelta(seconds=45)
        session.commit()

    stale = client.get(runtime_path, headers=headers)
    assert stale.status_code == 200
    assert stale.json()["process_state"] == "unknown"
    assert stale.json()["room_state"] == "unknown"


def test_profile_projection_drops_sensitive_external_data_and_normalizes_friends() -> None:
    from camfrog_control_server.profile_provider import (
        normalize_friend_entries,
        project_external_data,
    )

    projected = project_external_data(
        {
            "type": "profile",
            "nickname": "example-user",
            "nickname_color": "green",
            "client_status": "away",
            "avatar_id": 17,
            "coins_amount": 120,
            "balance": {"points": 6, "coins": 120, "rewards": 3},
            "have_room": True,
            "notifications_count": 2,
            "friends": {"all": 12, "online": 2, "added": 1},
            "gifts": {"items": [1, 2], "xpbacks": []},
            "reward_program": {"engine": "internal", "balance": 3, "status": {"enabled": True}},
            "csrf": "REDACTED-TEST-VALUE",
            "stripe_key": "REDACTED-TEST-VALUE",
        },
        nav_user_logged=True,
    )
    assert projected["auth"]["external_data_type"] == "profile"
    assert projected["auth"]["csrf_present"] is True
    assert projected["profile"]["client_presence"] == "away"
    assert projected["profile"]["summary"]["balance"]["coins"] == 120
    assert projected["profile"]["summary"]["friend_counts"]["all"] == 12
    assert "csrf" not in projected and "stripe_key" not in projected
    assert "REDACTED-TEST-VALUE" not in repr(projected)

    friends = normalize_friend_entries(
        [
            {
                "original_nick": "FriendOne",
                "display_name": "Friend One",
                "client_status": ["online"],
                "avatar_id": 7,
                "alevel_id": 2,
                "gender": 1,
                "avatar_url": "https://example.invalid/avatar.png",
            }
        ]
    )
    assert friends == [
        {
            "nickname": "FriendOne",
            "display_name": "Friend One",
            "presence": "online",
            "nickname_color": None,
            "avatar_id": 7,
            "alevel": 2,
            "gender": 1,
        }
    ]


def test_presence_resolution_expires_stale_data_and_ignores_uncalibrated_image() -> None:
    from camfrog_control_server.presence_provider import PresenceObservation, resolve_presence

    now = datetime.now(UTC)
    stale = resolve_presence(
        [PresenceObservation("online", "profile", now - timedelta(minutes=11))], now=now
    )
    assert stale.state == "unknown"
    uncalibrated = resolve_presence([PresenceObservation("online", "status_image", now)], now=now)
    assert uncalibrated.state == "unknown"


def test_rate_limit_and_secret_redaction() -> None:
    import asyncio

    from camfrog_control_server.observability import redact_sensitive_text
    from camfrog_control_server.rate_limit import SlidingWindowRateLimiter

    limiter = SlidingWindowRateLimiter(window_seconds=10)
    assert asyncio.run(limiter.allow("admin:127.0.0.1", limit=1, now=100))[0] is True
    blocked, retry_after = asyncio.run(limiter.allow("admin:127.0.0.1", limit=1, now=101))
    assert blocked is False
    assert retry_after == 9
    assert asyncio.run(limiter.allow("admin:127.0.0.1", limit=1, now=111))[0] is True

    safe = redact_sensitive_text(
        "Authorization: Bearer secret-value Cookie: PHPSESSID=secret; csrf=another-secret"
    )
    assert "secret-value" not in safe
    assert "PHPSESSID=secret" not in safe
    assert "another-secret" not in safe


def test_cloud_bot_status_maps_reason_before_status(
    api_client: tuple[TestClient, object, str],
) -> None:
    client, _, admin_token = api_client
    agent, _ = _account_and_agent(client, admin_token)
    headers = _headers(admin_token)
    created = client.post(
        "/api/v1/cloud-bots",
        headers=headers,
        json={"name": "cloud-bot-one", "agent_id": agent["id"]},
    )
    assert created.status_code == 201
    bot = created.json()
    report = client.post(
        f"/api/v1/agent/cloud-bots/{bot['id']}/status",
        headers=_headers(agent["agent_token"]),
        json={"raw_status": "paused", "reason": "working", "uptime_seconds": 37},
    )
    assert report.status_code == 201
    assert report.json()["state"] == "online"
    status_read = client.get(f"/api/v1/cloud-bots/{bot['id']}/status", headers=headers)
    assert status_read.json()["state"] == "online"
    assert status_read.json()["raw_status"] == "paused"


def test_subscription_lifetime_baseline_returns_after_expired_overlay(
    api_client: tuple[TestClient, object, str],
) -> None:
    client, _, admin_token = api_client
    _, account = _account_and_agent(client, admin_token)
    headers = _headers(admin_token)
    base = client.put(
        f"/api/v1/accounts/{account['id']}/subscription/baseline",
        headers=headers,
        json={
            "base_tier": "pro",
            "base_term": "lifetime",
            "evidence_source": "operator_report",
            "evidence_note": "Legacy serial entitlement reported by the account owner.",
        },
    )
    assert base.status_code == 200
    assert base.json()["effective_tier"] == "pro"
    now = datetime.now(UTC)
    expired = client.post(
        f"/api/v1/accounts/{account['id']}/subscription/overlays",
        headers=headers,
        json={
            "tier": "gold",
            "starts_at": (now - timedelta(days=35)).isoformat(),
            "expires_at": (now - timedelta(days=5)).isoformat(),
            "evidence_source": "manual_entry",
        },
    )
    assert expired.status_code == 201
    subscription = client.get(
        f"/api/v1/accounts/{account['id']}/subscription", headers=headers
    ).json()
    assert subscription["effective_tier"] == "pro"
    assert subscription["effective_source"] == "durable_baseline"

    active_start = now - timedelta(days=1)
    active = client.post(
        f"/api/v1/accounts/{account['id']}/subscription/overlays",
        headers=headers,
        json={
            "tier": "extreme",
            "starts_at": active_start.isoformat(),
            "expires_at": (now + timedelta(days=20)).isoformat(),
            "evidence_source": "official_record",
        },
    )
    assert active.status_code == 201
    current = client.get(f"/api/v1/accounts/{account['id']}/subscription", headers=headers).json()
    assert current["effective_tier"] == "extreme"
    assert current["effective_source"] == "temporary_overlay"

    overlap = client.post(
        f"/api/v1/accounts/{account['id']}/subscription/overlays",
        headers=headers,
        json={
            "tier": "gold",
            "starts_at": (now + timedelta(days=1)).isoformat(),
            "expires_at": (now + timedelta(days=30)).isoformat(),
            "evidence_source": "manual_entry",
        },
    )
    assert overlap.status_code == 409


def test_store_confirmation_is_explicit_and_never_executes_purchase(
    api_client: tuple[TestClient, object, str],
) -> None:
    client, _, admin_token = api_client
    _, account = _account_and_agent(client, admin_token)
    headers = _headers(admin_token)
    item_body = {
        "source_item_id": "gift-example-01",
        "item_type": "gift",
        "name": "Example Gift",
        "currency": "coins",
        "price_minor": 120,
        "available": True,
        "metadata": {"limited": False},
    }
    item = client.post("/api/v1/store/catalog/items", headers=headers, json=item_body)
    assert item.status_code == 201
    rejected = client.post(
        "/api/v1/store/catalog/items",
        headers=headers,
        json={**item_body, "source_item_id": "gift-example-02", "metadata": {"csrf_token": "x"}},
    )
    assert rejected.status_code == 422

    intent = client.post(
        "/api/v1/store/purchase-intents",
        headers=headers,
        json={"account_id": account["id"], "catalog_item_id": item.json()["id"]},
    )
    assert intent.status_code == 201
    intent_id = intent.json()["id"]
    no_confirmation = client.post(
        f"/api/v1/store/purchase-intents/{intent_id}/confirm",
        headers=headers,
        json={
            "confirmed": False,
            "expected_item_name": "Example Gift",
            "expected_currency": "coins",
            "expected_price_minor": 120,
        },
    )
    assert no_confirmation.status_code == 422
    wrong_price = client.post(
        f"/api/v1/store/purchase-intents/{intent_id}/confirm",
        headers=headers,
        json={
            "confirmed": True,
            "expected_item_name": "Example Gift",
            "expected_currency": "coins",
            "expected_price_minor": 121,
        },
    )
    assert wrong_price.status_code == 409
    confirmed = client.post(
        f"/api/v1/store/purchase-intents/{intent_id}/confirm",
        headers=headers,
        json={
            "confirmed": True,
            "expected_item_name": "Example Gift",
            "expected_currency": "coins",
            "expected_price_minor": 120,
        },
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["state"] == "confirmed"
    assert client.get("/api/v1/commands", headers=headers).json() == []
    replay = client.post(
        f"/api/v1/store/purchase-intents/{intent_id}/confirm",
        headers=headers,
        json={
            "confirmed": True,
            "expected_item_name": "Example Gift",
            "expected_currency": "coins",
            "expected_price_minor": 120,
        },
    )
    assert replay.status_code == 409
