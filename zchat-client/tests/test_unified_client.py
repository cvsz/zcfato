"""Tests for the unified client shell and shared-module Process Monitor page.

The Process Monitor reuses camfrog_windows_runtime 1:1 (same modules as the
standalone executables) in read-only mode. All tests run without a Camfrog
client and without another ZChat executable.
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))  # shared modules (camfrog_windows_runtime)

from zchat_client.process_monitor import PM_TEXT, ProcessMonitorPage
from zchat_client.ui import SHELL_TEXT, AgentChatWindow, UnifiedClientWindow


@pytest.fixture()
def root():
    widget = tk.Tk()
    widget.withdraw()
    try:
        yield widget
    finally:
        widget.destroy()


def test_process_monitor_refresh_without_camfrog_never_raises(root) -> None:
    page = ProcessMonitorPage(root)
    page.refresh()  # no Camfrog on CI: must fail closed, not raise
    assert page.tree.get_children() == ()
    assert page.status_text.get() != PM_TEXT["en"]["status_ready"]


def test_process_monitor_language_toggle(root) -> None:
    lang = {"value": "en"}
    page = ProcessMonitorPage(root, get_language=lambda: lang["value"])
    assert page.refresh_button.cget("text") == PM_TEXT["en"]["refresh"]
    lang["value"] = "th"
    page.apply_language()
    assert page.refresh_button.cget("text") == PM_TEXT["th"]["refresh"]
    lang["value"] = "xx-unknown"
    page.apply_language()  # unknown language falls back, never raises
    assert page.refresh_button.cget("text") == PM_TEXT["en"]["refresh"]


def test_shell_hosts_agent_and_monitor_pages(root) -> None:
    shell = UnifiedClientWindow(root)
    assert set(shell.pages) == {"agent", "monitor"}
    assert shell._current == "agent"
    assert isinstance(shell.agent_page, AgentChatWindow)
    assert isinstance(shell.monitor_page, ProcessMonitorPage)
    shell.show_page("monitor")
    assert shell._current == "monitor"
    shell.show_page("no-such-page")  # unknown names fail closed
    assert shell._current == "monitor"


def test_shell_language_toggle_updates_nav_and_pages(root) -> None:
    shell = UnifiedClientWindow(root)
    assert shell.nav_buttons["monitor"].cget("text") == SHELL_TEXT["en"]["nav_monitor"]
    shell.language.set("th")
    root.update()
    assert shell.nav_buttons["monitor"].cget("text") == SHELL_TEXT["th"]["nav_monitor"]
    assert shell.monitor_page.refresh_button.cget("text") == PM_TEXT["th"]["refresh"]
    # Agent page shares the same language variable.
    assert shell.agent_page.language is shell.language


def test_agent_window_still_works_standalone(root) -> None:
    window = AgentChatWindow(root)
    assert window.server_url.get() == ""
    assert window.language.get() == "en"
