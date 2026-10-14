"""Small, credential-free adapter seams for Camfrog data and Cloud Bot status."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol


class AdapterNotConfigured(RuntimeError):
    """Raised when a live Camfrog integration has no authorized local provider."""


class CamfrogProfileAdapter(Protocol):
    """A Windows-side adapter supplies sanitized snapshots; the server never logs in."""

    def snapshot(self, account_id: str) -> dict[str, Any]: ...

    def update_status(self, account_id: str, status_text: str) -> None: ...


class UnconfiguredProfileAdapter:
    def snapshot(self, _account_id: str) -> dict[str, Any]:
        raise AdapterNotConfigured("Profile provider is not configured.")

    def update_status(self, _account_id: str, _status_text: str) -> None:
        raise AdapterNotConfigured("Profile update provider is not configured.")


CLOUD_BOT_STATUS_MAP = {
    "init": "starting",
    "init plugins": "starting",
    "init network": "starting",
    "cs disconnected": "disconnected",
    "disconnected": "disconnected",
    "timed out": "disconnected",
    "auth on cs": "authenticating",
    "cs connected": "authenticated",
    "session closed by room": "room_session_closed",
    "waiting userlist": "joining_room",
    "working": "online",
    "paused": "paused",
    "invalid key": "invalid_room_key",
    "bot not allowed": "bot_not_allowed",
    "room does not exist": "room_not_found",
}


def cloud_bot_state(reason: str | None, status: str | None) -> str:
    """Normalize the source-reported state, honoring reason before status."""
    raw = (reason or status or "").strip().casefold()
    return CLOUD_BOT_STATUS_MAP.get(raw, "unknown")


def build_cloud_bot_status_request(request_id: int = 1) -> dict[str, Any]:
    if request_id < 1:
        raise ValueError("Cloud Bot request id must be positive.")
    return {"id": request_id, "method": "status", "params": []}


def parse_cloud_bot_status_response(response: Any) -> dict[str, Any]:
    """Parse known status fields while leaving the unverified envelope fail-closed."""
    if not isinstance(response, dict):
        raise ValueError("Cloud Bot response must be a JSON object.")
    candidate = response.get("result", response)
    if not isinstance(candidate, dict):
        raise ValueError("Cloud Bot response result must be a JSON object.")
    raw_status = candidate.get("status")
    reason = candidate.get("reason")
    uptime = candidate.get("uptime")
    if raw_status is not None and not isinstance(raw_status, str):
        raise ValueError("Cloud Bot status must be text.")
    if reason is not None and not isinstance(reason, str):
        raise ValueError("Cloud Bot reason must be text.")
    if uptime is not None and (
        not isinstance(uptime, int) or isinstance(uptime, bool) or uptime < 0
    ):
        raise ValueError("Cloud Bot uptime must be a non-negative integer.")
    return {
        "state": cloud_bot_state(reason, raw_status),
        "raw_status": raw_status[:80] if raw_status else None,
        "reason": reason[:160] if reason else None,
        "uptime_seconds": uptime,
    }


class CloudBotRpcAdapter:
    """Build and parse the observed RPC shape; caller supplies an authorized transport."""

    def __init__(self, post_json: Callable[[str, dict[str, Any]], Any]) -> None:
        self._post_json = post_json
        self._request_id = 0

    def status(self) -> dict[str, Any]:
        self._request_id += 1
        request = build_cloud_bot_status_request(self._request_id)
        response = self._post_json("/bot/ajax/", request)
        return parse_cloud_bot_status_response(response)
