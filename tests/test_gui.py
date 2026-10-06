"""GUI tests: the Tk-free logic always runs; the Tk smoke test needs tkinter + a display."""
import copy
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import camfrog_auto as ca  # noqa: E402
import camfrog_gui as g  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _iso(tmp_path, monkeypatch):
    monkeypatch.setattr(ca, "BASE", tmp_path)
    ca.LANG = "en"
    yield
    ca.LANG = "en"


def test_messages_roundtrip():
    msgs = [{"th": "สวัสดี", "en": "Hello"}, "Plain", "only thai || "]
    back = g.text_to_msgs(g.msgs_to_text(msgs))
    assert back[0] == msgs[0] and back[1] == "Plain" and back[2] == "only thai"
    assert g.text_to_msgs("\n  \n || \n") == []


def test_selector_roundtrip():
    sel = {"control_type": "Edit", "auto_id": "1002", "index": 1}
    assert g.strs_to_sel(g.sel_to_strs(sel)) == sel
    assert g.strs_to_sel({}, allow_empty=True) is None
    assert g.strs_to_sel({}) == {}
    assert g.strs_to_sel({"class_name": "X"})["index"] == 0
    with pytest.raises(ValueError):
        g.strs_to_sel({"auto_id": "1", "index": "abc"})


def test_reply_fields_roundtrip():
    spec = {"th": ["a", "b"], "en": "c"}
    assert g.fields_to_reply(*g.reply_to_fields(spec)) == spec
    assert g.fields_to_reply("", "", "hi") == "hi"
    assert g.fields_to_reply("ไทย", "", "") == {"th": "ไทย", "en": "ไทย"}
    assert g.fields_to_reply("", "", "  \n") is None


def test_model_saves_valid_and_blocks_invalid(tmp_path):
    m = g.ConfigModel(tmp_path / "config.json")
    cfg = m.load()                                  # created via init when missing
    assert (tmp_path / "config.json").exists()
    bad = copy.deepcopy(cfg)
    bad["poll_seconds"] = 0
    errs, _ = m.save(bad)
    assert errs and json.loads((tmp_path / "config.json").read_text("utf-8"))["poll_seconds"] != 0
    live = copy.deepcopy(cfg)
    live["dry_run"] = False                         # no nickname -> refused
    assert m.save(live)[0]
    live["autoreply"]["own_nickname"] = "me"
    live["autoreply"]["history"] = {"control_type": "Edit", "auto_id": "7", "index": 0}
    live["autoreply"]["input"] = {"control_type": "Edit", "auto_id": "8", "index": 0}
    live["status"]["edit"] = {"control_type": "Edit", "auto_id": "9", "index": 0}
    assert m.save(live)[0] == []
    assert json.loads((tmp_path / "config.json").read_text("utf-8"))["dry_run"] is False


def test_im_config_uses_own_nickname_and_required_allowlist():
    cfg = ca.load_cfg(ROOT / "config.json")
    cfg["autoreply"]["own_nickname"] = "CamfrogNoom"
    cfg["autoreply_im"]["enabled"] = True
    cfg["autoreply_im"]["only_nicknames"] = ["zdevz"]
    assert not g.ConfigModel.check(cfg)[0]
    cfg["autoreply_im"]["only_nicknames"] = []
    assert any("only_nicknames" in error for error in g.ConfigModel.check(cfg)[0])


def test_autosave_live_confirmation_gate():
    assert not g.autosave_needs_confirmation({"dry_run": True}, True)
    assert not g.autosave_needs_confirmation({"dry_run": False}, False)
    assert g.autosave_needs_confirmation({"dry_run": False}, True)


def test_empty_selector_rejected():
    cfg = ca.load_cfg(ROOT / "config.json")
    cfg["autoreply"]["input"] = {"index": 0}
    errs, _ = ca.validate(cfg)
    assert any("no criteria" in e for e in errs)


def test_explain_matches_cli_engine():
    cfg = ca.load_cfg(ROOT / "config.json")
    out = g.explain(cfg, "Bob", "hello there")
    assert "rule #2" in out and "language" in out
    assert "SKIPPED" in g.explain(cfg, "Bob", "see https://x.y")
    assert "no rule" in g.explain(cfg, "Bob", "zzzz")


def test_explain_matches_im_engine():
    cfg = ca.load_cfg(ROOT / "config.json")
    cfg["autoreply"]["own_nickname"] = "CamfrogNoom"
    cfg["autoreply_im"]["only_nicknames"] = ["zdevz"]
    cfg["autoreply_im"]["enabled"] = True
    assert "rule #1" in g.explain(cfg, "zdevz", "hello", im=True)
    assert "SKIPPED" in g.explain(cfg, "someone-else", "hello", im=True)


def test_tail_and_stats(tmp_path):
    f = tmp_path / "a.log"
    f.write_text("\n".join(str(i) for i in range(1000)), encoding="utf-8")
    assert g.tail_text(f, lines=3) == "997\n998\n999"
    assert g.tail_text(tmp_path / "none.log") == ""
    assert g.read_stats(ca.load_cfg(ROOT / "config.json")) == {}


def test_cli_passthrough(capsys):
    assert g.main(["check", "--config", str(ROOT / "config.json")]) == 0
    assert "config OK" in capsys.readouterr().out


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


@pytest.mark.skipif(not _display(), reason="needs tkinter + display")
def test_gui_smoke(tmp_path, monkeypatch):
    (tmp_path / "config.json").write_text((ROOT / "config.json").read_text("utf-8"), encoding="utf-8")
    # Reuse the display probe's Tcl/Tk root. Some Windows Python installs fail
    # to initialize Tcl a second time after creating and destroying the probe.
    import tkinter
    root = _DISPLAY_ROOT
    root.deiconify()
    monkeypatch.setattr(tkinter, "Tk", lambda: root)
    app = g.build_app()(tmp_path / "config.json")
    app.root.update()
    for i in range(len(app.nb.tabs())):
        app.nb.select(i)
        app.root.update()
    cfg, errs = app.collect()
    assert not errs and cfg["status"]["messages"] == app.draft["status"]["messages"]
    assert cfg["autoreply"]["rules"] == app.draft["autoreply"]["rules"]
    assert cfg["autoreply"]["own_nickname"] == "CamfrogNoom"
    assert cfg["autoreply_im"]["only_nicknames"] == ["zdevz"]
    assert hasattr(app, "im_tree") and hasattr(app, "t_im_skips") and hasattr(app, "tiout")
    assert app.t_msgs.bind("<Control-c>") and app.t_msgs.bind("<Control-v>")
    assert app.t_msgs.bind("<Button-3>")
    from tkinter import ttk
    entry = app.im_tester_sender_entry
    notebooks = []
    widget = entry
    while widget is not app.root:
        parent = widget.master
        if isinstance(parent, ttk.Notebook):
            notebooks.append((parent, widget))
        widget = parent
    for notebook, page in reversed(notebooks):
        notebook.select(page)
    app.root.update()
    assert entry.winfo_class() == "TEntry" and entry.instate(["!disabled"])
    entry.delete(0, "end")
    entry.insert(0, "clipboard-roundtrip")
    entry.focus_set()
    entry.icursor(0)
    app.select_all(entry)
    app.root.update()
    assert entry.selection_present()
    event = SimpleNamespace(widget=entry)
    app.clipboard_virtual(event, "<<Copy>>")
    app.root.update()
    # Clipboard may be busy if another app has it; retry a few times
    for _ in range(5):
        try:
            assert app.root.clipboard_get() == "clipboard-roundtrip"
            break
        except Exception:
            time.sleep(0.1)
    else:
        pytest.skip("clipboard busy, skipping copy/paste test")
    entry.delete(0, "end")
    app.clipboard_virtual(event, "<<Paste>>")
    app.root.update()
    assert entry.get() == "clipboard-roundtrip"
    app.tin.set("zdevz")
    im_fields = {path[1] for path, _kind, _var, _label in app.binds if path[0] == "autoreply_im"}
    assert {"enabled", "dry_run", "window_title_regex", "max_windows", "log_kinds", "only_nicknames",
            "prefix", "answer_first_message", "per_sender_cooldown_seconds", "max_per_sender_per_day",
            "global_min_gap_seconds", "max_per_hour", "delay_range_seconds", "max_reply_length",
            "max_incoming_length", "ignore_links"} <= im_fields
    allowlist = next(var for path, _kind, var, _label in app.binds if path == ("autoreply_im", "only_nicknames"))
    allowlist.set("zdevz, smoke")
    app.cancel_autosave()
    app.auto_apply()
    assert json.loads((tmp_path / "config.json").read_text("utf-8"))["autoreply_im"]["only_nicknames"] == ["zdevz", "smoke"]
    allowlist.set("zdevz")
    app.cancel_autosave()
    app.auto_apply()
    app.test_rule()
    app.test_im_rule()
    assert "rule" in app.tiout.cget("text")
    assert "rule" in app.tout.cget("text")
    app.preview_marquee()
    app.rule_move(1)
    app.switch_lang()
    assert ca.LANG == "th"
    app.switch_lang()
    assert ca.LANG == "en"
    assert app.save() is True  # shipped config: selector clash is only a warning in dry-run
    app.tick()
    app.root.destroy()
