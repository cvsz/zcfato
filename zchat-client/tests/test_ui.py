from __future__ import annotations

import tkinter as tk

from zchat_client import ui
from zchat_client.ui import AgentChatWindow


def test_window_starts_without_server_or_saved_credentials() -> None:
    root = tk.Tk()
    try:
        window = AgentChatWindow(root)

        assert window.server_url.get() == ""
        assert window.agent_token.get() == ""
        assert window.token_entry.cget("show") == "*"
        assert str(window.message_input.cget("state")) == tk.DISABLED
        assert str(window.send_button.cget("state")) == tk.DISABLED
    finally:
        root.destroy()


def test_connect_rejects_blank_server_url_before_using_token(monkeypatch) -> None:
    root = tk.Tk()
    errors: list[tuple[str, str]] = []
    try:
        window = AgentChatWindow(root)
        window.agent_token.set("unused-agent-token")
        monkeypatch.setattr(
            ui.messagebox,
            "showerror",
            lambda title, message, **_kwargs: errors.append((title, message)),
        )

        window._connect()

        assert window.worker is None
        assert window.agent_token.get() == "unused-agent-token"
        assert errors == [("Invalid server URL", "Server URL must be an absolute HTTP(S) URL.")]
    finally:
        root.destroy()


def test_new_session_clears_account_scoped_conversation_and_draft() -> None:
    root = tk.Tk()
    try:
        window = AgentChatWindow(root)
        window.assignment.set("Account: previous-account")
        window._set_chat_enabled(True)
        window.message_input.insert("1.0", "Draft for previous account")
        window._set_chat_enabled(False)
        window._append_entry("Operator", "Private account message")

        window._clear_conversation()

        assert list(window._entries) == []
        assert window.message_input.get("1.0", "end-1c") == ""
        assert window.assignment.get() == "No account assigned"
        assert window.transcript.get("1.0", "end-1c") == ""
    finally:
        root.destroy()
