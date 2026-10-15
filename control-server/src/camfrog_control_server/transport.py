"""Authenticated HTTP transport for the control-plane agent protocol."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID

from pydantic import ValidationError

from .schemas import AgentChatMessage, ChatMessageRead, HeartbeatResponse


class AgentTransportError(RuntimeError):
    """A sanitized error from the control-plane transport."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
        return None


def validate_server_url(server_url: str) -> str:
    if not isinstance(server_url, str) or not server_url.strip():
        raise ValueError("Server URL must be an absolute HTTP(S) URL.")
    try:
        parsed = urlsplit(server_url.strip())
        hostname = parsed.hostname
        if parsed.port == 0:
            raise ValueError("Server URL port cannot be zero.")
    except ValueError as exc:
        raise ValueError("Server URL must include a valid host and port.") from exc
    if parsed.scheme not in {"https", "http"} or not hostname:
        raise ValueError("Server URL must be an absolute HTTP(S) URL.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Server URL cannot include credentials, query, or fragment.")
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and hostname.lower() not in local_hosts:
        raise ValueError("HTTPS is required except for loopback development URLs.")
    return server_url.strip().rstrip("/")


class ControlPlaneClient:
    """Small chat-only HTTP client with a one-time agent token kept in memory."""

    def __init__(self, server_url: str, agent_token: str, *, timeout: float = 10.0) -> None:
        self.base_url = validate_server_url(server_url) + "/api/v1"
        if (
            not isinstance(agent_token, str)
            or not agent_token
            or len(agent_token) > 256
            or not agent_token.isascii()
            or not all(char.isalnum() or char in "-_" for char in agent_token)
        ):
            raise ValueError("A valid one-time-issued agent token is required.")
        if not 0 < timeout <= 120:
            raise ValueError("Request timeout must be between 0 and 120 seconds.")
        self._agent_token = agent_token
        self._timeout = timeout
        self._opener = build_opener(_RejectRedirects())

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        encoded = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=encoded,
            method=method,
            headers={
                "Authorization": f"Bearer {self._agent_token}",
                "Accept": "application/json",
                **({"Content-Type": "application/json"} if encoded is not None else {}),
            },
        )
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                if response.status == 204:
                    return None
                raw = response.read(1_048_577)
                if len(raw) > 1_048_576:
                    raise AgentTransportError("Control-plane response exceeded the size limit.")
                return json.loads(raw.decode("utf-8"))
        except HTTPError as exc:
            # Response bodies may contain server diagnostics or echoed input.
            raise AgentTransportError(
                f"Control plane returned HTTP {exc.code}.", status_code=exc.code
            ) from None
        except (URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AgentTransportError(
                f"Control-plane request failed ({type(exc).__name__})."
            ) from None

    def heartbeat(self) -> dict[str, Any]:
        """Refresh the agent lease and return its current account assignment."""
        response = self.request("POST", "/agent/heartbeat", {"state": "running"})
        try:
            return HeartbeatResponse.model_validate(response).model_dump(mode="json")
        except ValidationError:
            raise AgentTransportError(
                "Control plane returned an invalid heartbeat response."
            ) from None

    def submit_chat_message(
        self, account_id: str, client_message_id: str, body: str
    ) -> dict[str, Any]:
        """Submit a message using a stable idempotency key."""
        try:
            account_id = str(UUID(account_id))
            client_message_id = str(UUID(client_message_id))
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("Account and client message IDs must be UUIDs.") from exc
        response = self.request(
            "POST",
            "/agent/messages",
            {
                "account_id": account_id,
                "client_message_id": client_message_id,
                "body": body,
            },
        )
        try:
            return ChatMessageRead.model_validate(response).model_dump(mode="json")
        except ValidationError:
            raise AgentTransportError(
                "Control plane returned an invalid submitted message."
            ) from None

    def poll_chat_message(self) -> dict[str, Any] | None:
        """Claim one operator message; callers must acknowledge only after delivery."""
        response = self.request("GET", "/agent/messages/next")
        if not isinstance(response, dict) or "message" not in response:
            raise AgentTransportError("Control plane returned an invalid chat response.")
        message = response.get("message")
        if message is None:
            return None
        if not isinstance(message, dict):
            raise AgentTransportError("Control plane returned an invalid chat message.")
        try:
            validated = AgentChatMessage.model_validate(message)
        except ValidationError:
            raise AgentTransportError("Control plane returned an invalid chat message.") from None
        return validated.model_dump(mode="json")

    def acknowledge_chat_message(self, message_id: str, claim_token: str) -> None:
        """Acknowledge a claimed message after the receiving client accepts it."""
        try:
            message_id = str(UUID(message_id))
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("Message ID must be a UUID.") from exc
        if not isinstance(claim_token, str) or not 32 <= len(claim_token) <= 128:
            raise ValueError("A valid message claim token is required.")
        self.request(
            "POST",
            f"/agent/messages/{message_id}/ack",
            {"claim_token": claim_token},
        )
