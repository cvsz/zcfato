"""Tk-free behavior tests for the compact Camfrog status changer."""
import sys
from pathlib import Path

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
