"""Polling reference agent with an opt-in official-client provider."""

from __future__ import annotations

import argparse
import getpass
import random
import sys
import time
from typing import Any

from .transport import (
    AgentTransportError,
    ControlPlaneClient,
)
from .transport import (
    validate_server_url as validate_server_url,
)
from .windows_client import WindowsCamfrogClientProvider


class NoCamfrogProvider:
    """Fail closed when no local official-client provider has been configured."""

    def execute(self, _command: dict[str, Any]) -> tuple[str, str]:
        return "failed", "provider_not_configured"

    def process_state(self) -> str:
        return "unknown"


def poll_once(client: ControlPlaneClient, provider: Any) -> bool:
    process_state = getattr(provider, "process_state", None)
    heartbeat: dict[str, str] = {"state": "running"}
    if callable(process_state):
        heartbeat["client_process_state"] = process_state()
    client.request("POST", "/agent/heartbeat", heartbeat)
    response = client.request("GET", "/agent/commands/next")
    command = (response or {}).get("command")
    did_work = False
    if command is not None:
        state, code = provider.execute(command)
        client.request(
            "POST",
            f"/agent/commands/{command['id']}/result",
            {"claim_token": command["claim_token"], "state": state, "code": code},
        )
        did_work = True

    receive_chat_message = getattr(provider, "receive_chat_message", None)
    if callable(receive_chat_message):
        message = client.poll_chat_message()
        if message is not None:
            try:
                delivered = receive_chat_message(message)
            except Exception as exc:
                # Leave the lease unacknowledged so the server can retry without logging content.
                print(f"Chat delivery failed ({type(exc).__name__}); the lease will expire.")
            else:
                if delivered is True:
                    client.acknowledge_chat_message(message["id"], message["claim_token"])
                    did_work = True
    return did_work


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
