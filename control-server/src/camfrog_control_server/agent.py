"""Polling reference agent with an opt-in official-client provider."""

from __future__ import annotations

import argparse
import getpass
import json
import random
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .windows_client import WindowsCamfrogClientProvider


class AgentTransportError(RuntimeError):
    """A sanitized error from the control-plane transport."""


@dataclass(frozen=True, slots=True)
class ClaimedCommand:
    id: str
    claim_token: str


class NoCamfrogProvider:
    """Fail closed when no local official-client provider has been configured."""

    def execute(self, _command: dict[str, Any]) -> tuple[str, str]:
        return "failed", "provider_not_configured"

    def process_state(self) -> str:
        return "unknown"


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
        return None


def validate_server_url(server_url: str) -> str:
    parsed = urlsplit(server_url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise ValueError("Server URL must be an absolute HTTP(S) URL.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Server URL cannot include credentials, query, or fragment.")
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and parsed.hostname.lower() not in local_hosts:
        raise ValueError("HTTPS is required except for loopback development URLs.")
    return server_url.rstrip("/")


class ControlPlaneClient:
    def __init__(self, server_url: str, agent_token: str, *, timeout: float = 10.0) -> None:
        self.base_url = validate_server_url(server_url) + "/api/v1"
        if not agent_token or len(agent_token) > 256:
            raise ValueError("A valid one-time-issued agent token is required.")
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
            # Do not include response bodies: they may contain server diagnostics or echoed input.
            raise AgentTransportError(f"Control plane returned HTTP {exc.code}.") from None
        except (URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            message = f"Control-plane request failed ({type(exc).__name__})."
            raise AgentTransportError(message) from None


def poll_once(client: ControlPlaneClient, provider: Any) -> bool:
    process_state = getattr(provider, "process_state", None)
    heartbeat: dict[str, str] = {"state": "running"}
    if callable(process_state):
        heartbeat["client_process_state"] = process_state()
    client.request("POST", "/agent/heartbeat", heartbeat)
    response = client.request("GET", "/agent/commands/next")
    command = (response or {}).get("command")
    if command is None:
        return False

    state, code = provider.execute(command)
    client.request(
        "POST",
        f"/agent/commands/{command['id']}/result",
        {"claim_token": command["claim_token"], "state": state, "code": code},
    )
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the reference control-plane polling agent.")
    parser.add_argument(
        "--server-url",
        required=True,
        help="HTTPS origin of the running control plane (HTTP is limited to loopback)",
    )
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--once", action="store_true", help="Send one heartbeat and poll once.")
    parser.add_argument(
        "--client-executable",
        help="Opt-in absolute path to the installed official Camfrog .exe (Windows only).",
    )
    args = parser.parse_args()
    if not 1.0 <= args.poll_seconds <= 60.0:
        parser.error("--poll-seconds must be between 1 and 60.")

    try:
        token = getpass.getpass("Agent token (kept in memory only): ")
        client = ControlPlaneClient(args.server_url, token)
    except ValueError as exc:
        parser.error(str(exc))

    try:
        if args.client_executable:
            provider = WindowsCamfrogClientProvider(
                args.client_executable, platform_name=sys.platform
            )
        else:
            provider = NoCamfrogProvider()
    except ValueError as exc:
        parser.error(str(exc))
    failures = 0
    try:
        while True:
            try:
                poll_once(client, provider)
                failures = 0
                delay = args.poll_seconds
            except AgentTransportError as exc:
                # Never print request headers, tokens, or response bodies.
                print(f"Agent transport: {exc}")
                failures += 1
                delay = min(60.0, args.poll_seconds * (2 ** min(failures - 1, 6)))
            if args.once:
                return
            time.sleep(random.uniform(delay * 0.8, delay * 1.2))
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
