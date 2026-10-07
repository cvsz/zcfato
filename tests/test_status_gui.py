"""Tk-free behavior tests for the compact Camfrog status changer."""
import ctypes
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import camfrog_status_gui as gui  # noqa: E402


def test_status_changer_has_ten_slots_and_saves_only_visible_slots():
    assert gui.STATUS_SLOTS == 10
    entries = [f"status {i}" for i in range(1, 11)]
    entries[1] = "ไทย || English"
    entries[3] = "  "
    messages = gui.messages_from_slots(entries)
    assert len(messages) == 9
    assert messages[0] == "status 1"
    assert messages[1] == {"th": "ไทย", "en": "English"}
    assert messages[-1] == "status 10"


def test_status_changer_parses_one_language_without_losing_it():
    assert gui.messages_from_slots([" ไทย || ", " || English "]) == ["ไทย", "English"]


def test_runtime_config_disables_autoreply_and_sets_background_mode():
    base_cfg = {
        "autoreply": {"enabled": True},
        "autoreply_im": {"enabled": True},
        "stats": {"file": "stats.json"},
        "log": {"file": "log.txt"},
        "safety": {"require_foreground": True},
    }
    rt = gui.runtime_config(base_cfg)
    assert rt["autoreply"]["enabled"] is False
    assert rt["autoreply_im"]["enabled"] is False
    assert rt["safety"]["require_foreground"] is False
    assert rt["stats"]["file"] == "camfrog_status_changer_stats.json"
    assert rt["log"]["file"] == "camfrog_status_changer.log"
    # Ensure original config is not mutated
    assert base_cfg["autoreply"]["enabled"] is True
    assert base_cfg["safety"]["require_foreground"] is True


def test_text_to_message_and_message_to_text():
    assert gui.text_to_message("hello") == "hello"
    assert gui.text_to_message("  ") is None
    assert gui.text_to_message("th || en") == {"th": "th", "en": "en"}
    assert gui.text_to_message("th || ") == "th"
    assert gui.text_to_message(" || en") == "en"

    assert gui.message_to_text({"th": "th", "en": "en"}) == "th || en"
    assert gui.message_to_text("plain") == "plain"


@pytest.mark.skipif(os.name != "nt", reason="Windows mutex test")
def test_single_instance_guard_first_acquire_succeeds(monkeypatch):
    """First acquire() succeeds when mutex doesn't exist."""
    mock_kernel32 = type("K32", (), {
        "CreateMutexW": lambda *a, **k: 1,
        "CloseHandle": lambda *a: None,
    })()
    mock_kernel32.CreateMutexW.argtypes = ()
    mock_kernel32.CreateMutexW.restype = ctypes.c_void_p
    mock_kernel32.CloseHandle.argtypes = ()
    mock_kernel32.CloseHandle.restype = ctypes.c_int
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: mock_kernel32)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 0)

    guard = gui.SingleInstanceGuard("TestMutexFirst")
    assert guard.acquire() is True
    guard.release()


@pytest.mark.skipif(os.name != "nt", reason="Windows mutex test")
def test_single_instance_guard_blocks_second_instance(monkeypatch):
    """Second acquire() returns False when ERROR_ALREADY_EXISTS."""
    mock_kernel32 = type("K32", (), {
        "CreateMutexW": lambda *a, **k: 1,
        "CloseHandle": lambda *a: None,
    })()
    mock_kernel32.CreateMutexW.argtypes = ()
    mock_kernel32.CreateMutexW.restype = ctypes.c_void_p
    mock_kernel32.CloseHandle.argtypes = ()
    mock_kernel32.CloseHandle.restype = ctypes.c_int
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: mock_kernel32)
    errors = [0, 183]
    monkeypatch.setattr(ctypes, "get_last_error", lambda: errors.pop(0))

    guard = gui.SingleInstanceGuard("TestMutexSecond")
    assert guard.acquire() is True
    assert guard.acquire() is False
    guard.release()


def test_single_instance_guard_non_windows_always_succeeds(monkeypatch):
    """On non-Windows, acquire() always returns True."""
    monkeypatch.setattr(os, "name", "posix")

    guard = gui.SingleInstanceGuard("TestMutexLinux")
    assert guard.acquire() is True
    guard.release()
