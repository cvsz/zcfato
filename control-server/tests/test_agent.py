from __future__ import annotations

import pytest

from camfrog_control_server.adapters import (
    CloudBotRpcAdapter,
    build_cloud_bot_status_request,
    parse_cloud_bot_status_response,
)
from camfrog_control_server.agent import (
    ControlPlaneClient,
    NoCamfrogProvider,
    poll_once,
    validate_server_url,
)


def test_remote_agent_requires_https() -> None:
    assert validate_server_url("https://profiles.camfrog.com/") == "https://profiles.camfrog.com"
    assert validate_server_url("http://127.0.0.1:8000") == "http://127.0.0.1:8000"
    with pytest.raises(ValueError, match="HTTPS"):
        validate_server_url("http://profiles.camfrog.com")


def test_server_url_rejects_embedded_credentials_and_fragments() -> None:
    with pytest.raises(ValueError):
        validate_server_url("https://operator@profiles.camfrog.com")
    with pytest.raises(ValueError):
        validate_server_url("https://profiles.camfrog.com/path#fragment")


def test_provider_fails_closed_until_configured() -> None:
    provider = NoCamfrogProvider()
    assert provider.execute({"operation": "launch"}) == (
        "failed",
        "provider_not_configured",
    )
    assert provider.process_state() == "unknown"


def test_poll_once_includes_account_client_state_in_heartbeat() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, dict | None]] = []

        def request(self, method: str, path: str, body: dict | None = None) -> dict | None:
            self.calls.append((method, path, body))
            return {"command": None} if path == "/agent/commands/next" else None

    client = FakeClient()
    assert poll_once(client, NoCamfrogProvider()) is False
    assert client.calls[0] == (
        "POST",
        "/agent/heartbeat",
        {"state": "running", "client_process_state": "unknown"},
    )


def test_poll_once_acknowledges_messages_only_after_provider_acceptance() -> None:
    message = {
        "id": "3a16ee61-7e66-4bf4-bf83-b2a8ed4939b5",
        "claim_token": "a" * 43,
    }

    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, dict | None]] = []

        def request(self, method: str, path: str, body: dict | None = None):
            self.calls.append((method, path, body))
            if path == "/agent/commands/next":
                return {"command": None}
            if path == "/agent/messages/next":
                return {"message": message}
            return None

        def poll_chat_message(self):
            return self.request("GET", "/agent/messages/next")["message"]

        def acknowledge_chat_message(self, message_id: str, claim_token: str) -> None:
            self.request(
                "POST",
                f"/agent/messages/{message_id}/ack",
                {"claim_token": claim_token},
            )

    class AcceptingProvider(NoCamfrogProvider):
        def receive_chat_message(self, _message: dict) -> bool:
            return True

    client = FakeClient()
    assert poll_once(client, AcceptingProvider()) is True
    assert client.calls[-1] == (
        "POST",
        f"/agent/messages/{message['id']}/ack",
        {"claim_token": message["claim_token"]},
    )

    class RejectingProvider(NoCamfrogProvider):
        def receive_chat_message(self, _message: dict) -> bool:
            return False

    rejected_client = FakeClient()
    assert poll_once(rejected_client, RejectingProvider()) is False
    assert not any(path.endswith("/ack") for _, path, _ in rejected_client.calls)


def test_control_plane_client_exposes_idempotent_chat_transport() -> None:
    client = ControlPlaneClient("https://control.example", "agent-token")
    calls: list[tuple[str, str, dict | None]] = []
    claimed = {
        "id": "3a16ee61-7e66-4bf4-bf83-b2a8ed4939b5",
        "account_id": "f6f17f92-ae7a-4c65-94d3-8376f08c909e",
        "client_message_id": "ce5dbd3a-c6d7-46fa-963f-5350a9fc0c70",
        "body": "Operator message",
        "claim_token": "a" * 43,
        "claim_expires_at": "2026-10-15T10:00:00Z",
    }

    def fake_request(method: str, path: str, body: dict | None = None):
        calls.append((method, path, body))
        if path == "/agent/messages/next":
            return {"message": claimed}
        return {"state": "received"}

    client.request = fake_request
    submitted = client.submit_chat_message(
        claimed["account_id"], claimed["client_message_id"], "Agent message"
    )
    polled = client.poll_chat_message()
    client.acknowledge_chat_message(claimed["id"], claimed["claim_token"])

    assert submitted == {"state": "received"}
    assert polled == claimed
    assert calls == [
        (
            "POST",
            "/agent/messages",
            {
                "account_id": claimed["account_id"],
                "client_message_id": claimed["client_message_id"],
                "body": "Agent message",
            },
        ),
        ("GET", "/agent/messages/next", None),
        (
            "POST",
            f"/agent/messages/{claimed['id']}/ack",
            {"claim_token": claimed["claim_token"]},
        ),
    ]

    with pytest.raises(ValueError, match="UUIDs"):
        client.submit_chat_message("invalid", claimed["client_message_id"], "message")
    with pytest.raises(ValueError, match="token"):
        client.acknowledge_chat_message(claimed["id"], "short")


def test_cloud_bot_rpc_adapter_uses_observed_request_and_reason_precedence() -> None:
    sent: list[tuple[str, dict]] = []

    def transport(path: str, body: dict) -> dict:
        sent.append((path, body))
        return {"result": {"uptime": 12, "status": "paused", "reason": "working"}}

    adapter = CloudBotRpcAdapter(transport)
    assert build_cloud_bot_status_request(3) == {"id": 3, "method": "status", "params": []}
    assert adapter.status()["state"] == "online"
    assert sent == [("/bot/ajax/", {"id": 1, "method": "status", "params": []})]
    assert parse_cloud_bot_status_response({"status": "not-a-known-state"})["state"] == "unknown"
