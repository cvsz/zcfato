from __future__ import annotations

import pytest

from camfrog_control_server.adapters import (
    CloudBotRpcAdapter,
    build_cloud_bot_status_request,
    parse_cloud_bot_status_response,
)
from camfrog_control_server.agent import NoCamfrogProvider, poll_once, validate_server_url


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
