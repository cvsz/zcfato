"""Tests for the unified client shell and shared-module Process Monitor page.

The Process Monitor reuses camfrog_windows_runtime 1:1 (same modules as the
standalone executables) in read-only mode. All tests run without a Camfrog
client and without another ZChat executable.
"""

from __future__ import annotations

import tkinter as tk
import tkinter.ttk as ttk

import pytest
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


def test_process_monitor_refresh_without_camfrog_never_raises(
    root, monkeypatch
) -> None:
    from camfrog_windows_runtime import WindowsCamfrogProcessDiscovery

    monkeypatch.setattr(
        WindowsCamfrogProcessDiscovery,
        "discover_processes",
        lambda self: [],
    )

    page = ProcessMonitorPage(root)
    page.refresh()

    assert page.tree.get_children() == ()
    assert page.status_text.get() == PM_TEXT["en"]["status_unavailable"]


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


def test_icon_helper_windows_hosts_and_embedded_frames(root, monkeypatch, tmp_path) -> None:
    """Exercise the Windows branch, including real Tk/Toplevel host types."""
    from zchat_client import ui

    icon = tmp_path / "app.ico"
    icon.write_bytes(b"test-icon")
    top = tk.Toplevel(root)
    calls = []
    try:
        with monkeypatch.context() as m:
            m.setattr(ui.sys, "platform", "win32")
            m.setattr(ui, "_application_icon_path", lambda: icon)
            m.setattr(root, "iconbitmap", lambda path: calls.append(("root", path)))
            m.setattr(top, "iconbitmap", lambda path: calls.append(("top", path)))
            ui._apply_application_icon(root)
            ui._apply_application_icon(top)
            ui._apply_application_icon(ttk.Frame(root))
        assert calls == [("root", str(icon)), ("top", str(icon))]
    finally:
        top.destroy()


def test_unified_shell_applies_icon_to_real_toplevel(root, monkeypatch) -> None:
    from zchat_client import ui

    calls = []
    original = ui._apply_application_icon
    with monkeypatch.context() as m:
        m.setattr(ui, "_apply_application_icon", lambda widget: calls.append(widget))
        shell = UnifiedClientWindow(root)
    assert root in calls
    assert shell.agent_page.root in calls


def test_agent_page_icon_is_skipped_on_embedded_frame(root) -> None:
    """iconbitmap() is toplevel-only; an embedded ttk.Frame must not raise.

    Regression for AttributeError: 'Frame' object has no attribute 'iconbitmap'
    when AgentChatWindow is hosted inside UnifiedClientWindow.
    """
    shell = UnifiedClientWindow(root)
    page = shell.agent_page
    assert isinstance(page.root, (tk.Frame, ttk.Frame))
    # Calling the icon helper directly on the embedded frame must be a no-op,
    # not an AttributeError.
    from zchat_client.ui import _apply_application_icon

    _apply_application_icon(page.root)  # must not raise
    _apply_application_icon(shell.container)  # must not raise
