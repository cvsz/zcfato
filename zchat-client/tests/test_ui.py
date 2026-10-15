from __future__ import annotations

import tkinter as tk

from zchat_client.ui import AgentChatWindow


def test_window_starts_with_server_default_and_without_saved_credentials() -> None:
    root = tk.Tk()
    try:
        window = AgentChatWindow(root)

        assert window.server_url.get() == "https://zchat.zeaz.dev"
        assert window.agent_token.get() == ""
        assert window.token_entry.cget("show") == "*"
        assert str(window.message_input.cget("state")) == tk.DISABLED
        assert str(window.send_button.cget("state")) == tk.DISABLED
    finally:
        root.destroy()
