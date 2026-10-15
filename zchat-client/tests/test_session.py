from __future__ import annotations

import queue
import time

import pytest
from zchat_client.session import AgentChatWorker, WorkerEvent

from camfrog_control_server.transport import AgentTransportError


def _wait_for_event(worker: AgentChatWorker, kind: str, timeout: float = 2.0) -> WorkerEvent:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            event = worker.events.get(timeout=0.05)
        except queue.Empty:
            continue
        if event.kind == kind:
            return event
    raise AssertionError(f"Timed out waiting for event: {kind}")


def test_incoming_message_is_acknowledged_only_after_ui_acceptance() -> None:
    message = {
        "id": "3a16ee61-7e66-4bf4-bf83-b2a8ed4939b5",
        "account_id": "f6f17f92-ae7a-4c65-94d3-8376f08c909e",
        "client_message_id": "ce5dbd3a-c6d7-46fa-963f-5350a9fc0c70",
        "body": "Operator message",
        "claim_token": "a" * 43,
    }
    acknowledged: list[tuple[str, str]] = []

    class FakeClient:
        def __init__(self, _server_url: str, _token: str) -> None:
            self.first_poll = True

        def heartbeat(self) -> dict:
            return {"account_id": message["account_id"]}

        def poll_chat_message(self) -> dict | None:
            if self.first_poll:
                self.first_poll = False
                return message
            return None

        def acknowledge_chat_message(self, message_id: str, claim_token: str) -> None:
            acknowledged.append((message_id, claim_token))

        def submit_chat_message(self, *_args) -> dict:
            raise AssertionError("No outgoing message was queued")

    worker = AgentChatWorker(
        "https://control.example",
        "agent-token",
        client_factory=FakeClient,
        poll_interval=0.2,
        heartbeat_interval=1,
    )
    worker.start()

    incoming = _wait_for_event(worker, "incoming")
    assert incoming.data["message"]["body"] == "Operator message"
    assert acknowledged == []

    worker.accept_incoming(message["id"], message["claim_token"])
    _wait_for_event(worker, "acknowledged")
    assert acknowledged == [(message["id"], message["claim_token"])]
    worker.stop()
    worker.join(timeout=1)


def test_stopped_session_cannot_restart_after_its_token_is_cleared() -> None:
    class FakeClient:
        def __init__(self, _server_url: str, _token: str) -> None:
            pass

        def heartbeat(self) -> dict:
            return {"account_id": None}

    worker = AgentChatWorker(
        "https://control.example",
        "agent-token",
        client_factory=FakeClient,
        heartbeat_interval=1,
    )
    worker.start()
    _wait_for_event(worker, "assignment")
    worker.stop()
    worker.join(timeout=1)

    with pytest.raises(RuntimeError, match="cannot be restarted"):
        worker.start()


def test_unassigned_agent_does_not_poll_or_send_chat() -> None:
    polled = False

    class FakeClient:
        def __init__(self, _server_url: str, _token: str) -> None:
            pass

        def heartbeat(self) -> dict:
            return {"account_id": None}

        def poll_chat_message(self) -> None:
            nonlocal polled
            polled = True

        def acknowledge_chat_message(self, *_args) -> None:
            raise AssertionError("No incoming message was queued")

        def submit_chat_message(self, *_args) -> dict:
            raise AssertionError("An unassigned agent cannot send chat")

    worker = AgentChatWorker(
        "https://control.example",
        "agent-token",
        client_factory=FakeClient,
        heartbeat_interval=1,
    )
    worker.start()

    assignment = _wait_for_event(worker, "assignment")
    assert assignment.data["account_id"] is None
    assert not polled
    worker.stop()
    worker.join(timeout=1)


def test_terminal_server_error_stops_without_retrying() -> None:
    heartbeat_calls = 0

    class FakeClient:
        def __init__(self, _server_url: str, _token: str) -> None:
            pass

        def heartbeat(self) -> dict:
            nonlocal heartbeat_calls
            heartbeat_calls += 1
            raise AgentTransportError("Not found", status_code=404)

    worker = AgentChatWorker(
        "https://control.example",
        "agent-token",
        client_factory=FakeClient,
        retry_base=0.01,
    )
    worker.start()

    error = _wait_for_event(worker, "error")
    worker.join(timeout=1)

    assert error.data["message"] == "Control server rejected the request (HTTP 404)."
    assert heartbeat_calls == 1
    assert not worker.is_alive


def test_outgoing_retry_reuses_the_same_idempotency_key() -> None:
    account_id = "f6f17f92-ae7a-4c65-94d3-8376f08c909e"
    submitted_ids: list[str] = []

    class FakeClient:
        def __init__(self, _server_url: str, _token: str) -> None:
            self.failed_once = False

        def heartbeat(self) -> dict:
            return {"account_id": account_id}

        def submit_chat_message(self, _account_id: str, message_id: str, _body: str) -> dict:
            submitted_ids.append(message_id)
            if not self.failed_once:
                self.failed_once = True
                raise AgentTransportError("temporary network failure")
            return {"id": "ef8a3056-60d8-42f5-b3d9-a11d2a2f62bf"}

        def poll_chat_message(self) -> None:
            return None

        def acknowledge_chat_message(self, *_args) -> None:
            raise AssertionError("No incoming message was queued")

    worker = AgentChatWorker(
        "https://control.example",
        "agent-token",
        client_factory=FakeClient,
        poll_interval=0.2,
        heartbeat_interval=1,
        retry_base=0.01,
    )
    worker.start()
    message_id = worker.submit_message("Retry safely")

    delivered = _wait_for_event(worker, "sent")
    assert delivered.data["message_id"] == message_id
    assert submitted_ids[:2] == [message_id, message_id]
    worker.stop()
    worker.join(timeout=1)


def test_client_side_validation_rejects_blank_and_oversized_messages() -> None:
    worker = AgentChatWorker("https://control.example", "agent-token")

    for body in (" \n ", "x" * 4001):
        try:
            worker.submit_message(body)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid body was accepted")


def test_outgoing_queue_is_bounded() -> None:
    worker = AgentChatWorker("https://control.example", "agent-token")
    for index in range(100):
        worker.submit_message(f"Message {index}")

    try:
        worker.submit_message("One too many")
    except ValueError as exc:
        assert "queue is full" in str(exc)
    else:
        raise AssertionError("The outgoing queue accepted more than its configured limit")
