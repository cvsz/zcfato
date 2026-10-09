"""Tests for the Camfrog private-chat window manager."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import camfrog_auto as ca  # noqa: E402
import camfrog_private_chat_gui as p  # noqa: E402


def test_private_config_stays_beside_executable(tmp_path, monkeypatch):
    monkeypatch.setattr(ca, "BASE", tmp_path)
    assert p.private_config_path("private-chat-config.json") == (
        tmp_path / "private-chat-config.json").resolve()
    with pytest.raises(ValueError):
        p.private_config_path("../outside.json")


def test_private_config_disables_all_bots(tmp_path, monkeypatch):
    monkeypatch.setattr(ca, "BASE", tmp_path)
    config = p.load_private_config(tmp_path / "private-chat-config.json")
    assert config["status"]["enabled"] is False
    assert config["autoreply"]["enabled"] is False
    assert config["autoreply_im"]["enabled"] is False


_DISPLAY_ROOT = None


def _display():
    global _DISPLAY_ROOT
    try:
        import tkinter
        _DISPLAY_ROOT = tkinter.Tk()
        _DISPLAY_ROOT.withdraw()
        return True
    except Exception:
        return False


def _buttons(manager):
    from tkinter import ttk
    found = []

    def walk(widget):
        for child in widget.winfo_children():
            if isinstance(child, ttk.Button):
                found.append(str(child.cget("text")))
            walk(child)

    walk(manager.root)
    return found


@pytest.fixture()
def live_tk_root():
    """A fresh real Tk window per test with a guaranteed live default root.

    Sharing one probe root across tests is fragile: any destroy (here or in
    another module) leaves later StringVar() calls with no default root.
    """
    import tkinter

    root = tkinter.Tk()
    root.withdraw()
    tkinter._default_root = root
    try:
        yield root
    finally:
        try:
            root.destroy()
        except Exception:
            pass


@pytest.mark.skipif(not _display(), reason="needs tkinter + display")
def test_private_chat_has_discover_button(tmp_path, monkeypatch, live_tk_root):
    monkeypatch.setattr(ca, "BASE", tmp_path)
    manager = p.PrivateChatManager(tmp_path / "private-chat-config.json")
    try:
        manager.root.withdraw()
        manager.root.update()
        assert "Discover controls" in _buttons(manager)
    finally:
        manager.root.destroy()


@pytest.mark.skipif(not _display(), reason="needs tkinter + display")
def test_private_chat_discover_reports_output_path(tmp_path, monkeypatch, live_tk_root):
    monkeypatch.setattr(ca, "BASE", tmp_path)

    def fake_discover(_config):
        print("wrote /tmp/x/controls.txt. Copy selectors into config.")
        return 0

    monkeypatch.setattr(ca, "cmd_discover", fake_discover)
    manager = p.PrivateChatManager(tmp_path / "private-chat-config.json")
    try:
        manager.root.withdraw()
        manager.discover()
        assert "controls.txt" in manager.status.get()
    finally:
        manager.root.destroy()


@pytest.mark.skipif(not _display(), reason="needs tkinter + display")
def test_private_chat_discover_reports_failure_in_status(tmp_path, monkeypatch, live_tk_root):
    monkeypatch.setattr(ca, "BASE", tmp_path)

    def fake_discover(_config):
        raise RuntimeError("Camfrog window not found")

    monkeypatch.setattr(ca, "cmd_discover", fake_discover)
    manager = p.PrivateChatManager(tmp_path / "private-chat-config.json")
    try:
        manager.root.withdraw()
        manager.discover()
        assert manager.status.get().startswith("Could not discover controls:")
    finally:
        manager.root.destroy()
