"""Tk desktop interface for an assigned ZChat agent's internal chat."""

from __future__ import annotations

import queue
import tkinter as tk
from collections import deque
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Any

from camfrog_control_server.transport import validate_server_url

from .session import AgentChatWorker, WorkerEvent

DEFAULT_SERVER_URL = "https://zchat.zeaz.dev"


class AgentChatWindow:
    MAX_VISIBLE_ENTRIES = 500

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("ZChat Agent Chat")
        self.root.geometry("760x600")
        self.root.minsize(560, 420)
        self.worker: AgentChatWorker | None = None
        self._entries: deque[str] = deque(maxlen=self.MAX_VISIBLE_ENTRIES)
        self._closing = False

        self.server_url = tk.StringVar(value=DEFAULT_SERVER_URL)
        self.agent_token = tk.StringVar()
        self.status = tk.StringVar(value="Disconnected")
        self.assignment = tk.StringVar(value="No account assigned")

        self._build_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.after(100, self._drain_events)

    def _build_widgets(self) -> None:
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        connection = ttk.LabelFrame(container, text="Control Server", padding=10)
        connection.pack(fill=tk.X)
        connection.columnconfigure(1, weight=1)

        ttk.Label(connection, text="Server URL").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 8)
        )
        self.server_entry = ttk.Entry(connection, textvariable=self.server_url)
        self.server_entry.grid(row=0, column=1, sticky=tk.EW, pady=3)

        ttk.Label(connection, text="Agent token").grid(
            row=1, column=0, sticky=tk.W, padx=(0, 8)
        )
        self.token_entry = ttk.Entry(
            connection, textvariable=self.agent_token, show="*"
        )
        self.token_entry.grid(row=1, column=1, sticky=tk.EW, pady=3)

        self.connect_button = ttk.Button(
            connection, text="Connect", command=self._connect
        )
        self.connect_button.grid(row=0, column=2, rowspan=2, padx=(10, 0), sticky=tk.NS)

        status_row = ttk.Frame(container)
        status_row.pack(fill=tk.X, pady=(8, 8))
        ttk.Label(status_row, textvariable=self.status).pack(side=tk.LEFT)
        ttk.Label(status_row, textvariable=self.assignment).pack(side=tk.RIGHT)

        transcript_frame = ttk.LabelFrame(container, text="Conversation", padding=6)
        transcript_frame.pack(fill=tk.BOTH, expand=True)
        transcript_frame.rowconfigure(0, weight=1)
        transcript_frame.columnconfigure(0, weight=1)
        self.transcript = tk.Text(
            transcript_frame,
            wrap=tk.WORD,
            state=tk.DISABLED,
            undo=False,
            height=18,
            padx=8,
            pady=8,
        )
        scrollbar = ttk.Scrollbar(
            transcript_frame, orient=tk.VERTICAL, command=self.transcript.yview
        )
        self.transcript.configure(yscrollcommand=scrollbar.set)
        self.transcript.grid(row=0, column=0, sticky=tk.NSEW)
        scrollbar.grid(row=0, column=1, sticky=tk.NS)

        composer = ttk.Frame(container)
        composer.pack(fill=tk.X, pady=(8, 0))
        composer.columnconfigure(0, weight=1)
        self.message_input = tk.Text(composer, height=3, wrap=tk.WORD, undo=False)
        self.message_input.grid(row=0, column=0, sticky=tk.EW)
        self.message_input.bind("<Control-Return>", self._send_event)
        self.send_button = ttk.Button(composer, text="Send", command=self._send)
        self.send_button.grid(row=0, column=1, sticky=tk.NS, padx=(8, 0))
        ttk.Label(
            container,
            text="Messages and the token stay in memory only. Ctrl+Enter sends a message.",
        ).pack(anchor=tk.W, pady=(6, 0))
        self._set_chat_enabled(False)

    def _connect(self) -> None:
        if self.worker is not None and self.worker.is_alive:
            self.worker.stop()
            self.connect_button.configure(state=tk.DISABLED)
            self.status.set("Disconnecting…")
            return

        try:
            server_url = validate_server_url(self.server_url.get())
        except ValueError as exc:
            messagebox.showerror("Invalid server URL", str(exc), parent=self.root)
            return
        token = self.agent_token.get()
        if not token:
            messagebox.showerror(
                "Agent token required",
                "Enter the one-time-issued agent token.",
                parent=self.root,
            )
            return

        self.worker = AgentChatWorker(server_url, token)
        self.agent_token.set("")
        self._set_connection_fields_enabled(False)
        self.connect_button.configure(text="Disconnect", state=tk.NORMAL)
        self.status.set("Connecting…")
        self.worker.start()

    def _send_event(self, _event: tk.Event[Any]) -> str:
        self._send()
        return "break"

    def _send(self) -> None:
        if self.worker is None or not self.worker.is_alive:
            return
        body = self.message_input.get("1.0", "end-1c")
        try:
            message_id = self.worker.submit_message(body)
        except ValueError as exc:
            messagebox.showerror("Invalid message", str(exc), parent=self.root)
            return
        self.message_input.delete("1.0", tk.END)
        self._append_entry("You", body)
        self._append_entry("Status", f"Sending message {message_id[:8]}…")

    def _drain_events(self) -> None:
        if self._closing:
            return
        worker = self.worker
        if worker is not None:
            while True:
                try:
                    event = worker.events.get_nowait()
                except queue.Empty:
                    break
                self._handle_event(worker, event)
        self.root.after(100, self._drain_events)

    def _handle_event(self, worker: AgentChatWorker, event: WorkerEvent) -> None:
        data = event.data
        if event.kind == "connected":
            self.status.set("Connected; checking account assignment…")
        elif event.kind == "assignment":
            account_id = data["account_id"]
            if account_id is None:
                self.assignment.set("No account assigned")
                self.status.set("Connected; assign an account to this agent")
                self._set_chat_enabled(False)
            else:
                self.assignment.set(f"Account: {account_id}")
                self.status.set("Connected")
                self._set_chat_enabled(True)
        elif event.kind == "incoming":
            message = data["message"]
            self._append_entry("Operator", message["body"])
            worker.accept_incoming(message["id"], message["claim_token"])
        elif event.kind == "sent":
            self._append_entry(
                "Status",
                f"Message {data['message_id'][:8]} accepted by the control server",
            )
        elif event.kind == "send_failed":
            self._append_entry(
                "Status", f"Message {data['message_id'][:8]} was rejected by the server"
            )
        elif event.kind == "connection_error":
            self.status.set(
                f"Connection issue; retrying in {data['retry_seconds']:.1f}s"
            )
        elif event.kind == "auth_required":
            self.status.set(
                "Token rejected or revoked; reconnect with a newly issued token"
            )
            self._append_entry("Status", "Authentication is no longer valid")
        elif event.kind == "ack_failed":
            self._append_entry(
                "Status", f"Could not acknowledge message {data['message_id'][:8]}"
            )
        elif event.kind == "error":
            self.status.set(data["message"])
            self._append_entry("Status", data["message"])
        elif event.kind == "stopped":
            self._set_chat_enabled(False)
            self._set_connection_fields_enabled(True)
            self.connect_button.configure(text="Connect", state=tk.NORMAL)
            if self.status.get() not in {
                "Token rejected or revoked; reconnect with a newly issued token",
            }:
                self.status.set("Disconnected")
            if self.worker is worker:
                self.worker = None

    def _append_entry(self, speaker: str, body: str) -> None:
        timestamp = datetime.now().astimezone().strftime("%H:%M:%S")
        self._entries.append(f"[{timestamp}] {speaker}:\n{body}")
        self.transcript.configure(state=tk.NORMAL)
        self.transcript.delete("1.0", tk.END)
        self.transcript.insert(tk.END, "\n\n".join(self._entries))
        self.transcript.see(tk.END)
        self.transcript.configure(state=tk.DISABLED)

    def _set_chat_enabled(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        self.message_input.configure(state=state)
        self.send_button.configure(state=state)

    def _set_connection_fields_enabled(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        self.server_entry.configure(state=state)
        self.token_entry.configure(state=state)

    def _close(self) -> None:
        if self.worker is not None and self.worker.is_alive:
            self.worker.stop()
        self._closing = True
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    AgentChatWindow(root)
    root.mainloop()
