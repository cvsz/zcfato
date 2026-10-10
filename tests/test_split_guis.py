"""Self-containment + behavior tests for the per-feature GUI modules.

Each module must stand alone: no imports of sibling project modules, its own
engine copy, and its own profile/mode pinning.
"""
import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "config.example.json"

MODULES = {
    "room_control_gui": ("room", None),
    "im_autoreply_gui": ("im_reply", None),
    "camfrog_music_gui": ("music", None),
    "status_random_gui": ("status", "random"),
    "status_marquee_gui": ("status", "marquee"),
    "chat_im_private_gui": (None, None),
    "web_status_gui": (None, None),
}


def load(name):
    return __import__(name)


@pytest.mark.parametrize("name", sorted(MODULES))
def test_module_has_no_project_imports(name):
    src = (ROOT / f"{name}.py").read_text(encoding="utf-8")
    banned = ("import camfrog_auto", "import camfrog_gui", "import camfrog_status_gui",
              "import camfrog_private_chat_gui", "import room_control_gui",
              "import im_autoreply_gui", "import camfrog_music_gui",
              "import status_random_gui", "import status_marquee_gui",
              "import chat_im_private_gui", "import web_status_gui",
              "from tools", "import tools", "import clipboard_support",
              "from clipboard_support")
    for bad in banned:
        assert bad not in src, f"{name}: {bad}"


def test_profiles_and_modes_are_pinned():
    assert load("room_control_gui").APP_PROFILE == "room"
    assert load("im_autoreply_gui").APP_PROFILE == "im_reply"
    assert load("camfrog_music_gui").APP_PROFILE == "music"
    assert load("status_random_gui").STATUS_MODE == "random"
    assert load("status_marquee_gui").STATUS_MODE == "marquee"
    assert load("status_random_gui").runtime_config(
        load("status_random_gui").DEFAULTS)["status"]["random"] is True
    assert load("status_marquee_gui").runtime_config(
        load("status_marquee_gui").DEFAULTS)["status"]["marquee"]["enabled"] is True


def test_room_and_im_profiles_disable_other_features():
    room = load("room_control_gui")
    im = load("im_autoreply_gui")
    cfg = copy.deepcopy(room.DEFAULTS)
    cfg["status"]["enabled"] = True
    cfg["autoreply_im"]["enabled"] = True
    out = room.apply_app_profile(copy.deepcopy(cfg))
    assert out["status"]["enabled"] is False and out["autoreply_im"]["enabled"] is False
    out_im = im.apply_app_profile(copy.deepcopy(cfg))
    assert out_im["status"]["enabled"] is False and out_im["autoreply"]["enabled"] is False


def test_music_profile_disables_status_and_im():
    music = load("camfrog_music_gui")
    cfg = copy.deepcopy(music.DEFAULTS)
    cfg["status"]["enabled"] = True
    cfg["autoreply_im"]["enabled"] = True
    out = music.apply_app_profile(copy.deepcopy(cfg))
    assert out["status"]["enabled"] is False
    assert out["autoreply_im"]["enabled"] is False
    assert out["autoreply"]["enabled"] is True


@pytest.mark.parametrize("name,cmd", [
    ("room_control_gui", "check"),
    ("im_autoreply_gui", "check"),
    ("camfrog_music_gui", "check"),
])
def test_cli_passthrough_validates_example_config(name, cmd, capsys):
    mod = load(name)
    assert mod.main([cmd, "--config", str(EXAMPLE)]) == 0
    assert "config OK" in capsys.readouterr().out


@pytest.mark.parametrize("name", ["status_random_gui", "status_marquee_gui"])
def test_status_modules_carry_a_working_engine_cli(name, capsys):
    mod = load(name)
    assert mod.cli_main(["check", "--config", str(EXAMPLE)]) == 0
    assert "config OK" in capsys.readouterr().out


def test_status_modules_reject_other_modes_commands(capsys):
    assert load("status_random_gui").cli_main(["marquee", "x"]) == 2


def test_chat_im_private_engine_copy():
    mod = load("chat_im_private_gui")
    cfg = copy.deepcopy(mod.DEFAULTS)
    cfg["status"]["messages"] = ["a long enough status line"]
    errs, _ = mod.validate(cfg)
    assert errs == []
    assert mod.private_config_path(EXAMPLE).name == "config.example.json"


def test_web_status_merged_module():
    mod = load("web_status_gui")
    assert mod.wants_gui([]) is True
    assert mod.wants_gui(["check"]) is False
    pool = mod.parse_pool("line one\nline two\n")
    assert pool == ["line one", "line two"]


def test_entry_points_import_their_module():
    import importlib
    for entry, module in (
            ("room_control_entry", "room_control_gui"),
            ("im_autoreply_entry", "im_autoreply_gui"),
            ("status_random_entry", "status_random_gui"),
            ("status_marquee_entry", "status_marquee_gui"),
            ("chat_im_private_entry", "chat_im_private_gui"),
            ("music_dj_entry", "camfrog_music_gui"),
            ("web_status_entry", "web_status_gui")):
        mod = importlib.import_module(entry)
        assert importlib.import_module(module) is not None
        assert hasattr(mod, "main") or module is not None


from conftest import has_display, tk_root  # noqa: E402


@pytest.mark.skipif(not has_display(), reason="needs tkinter + display")
def test_room_gui_smoke(tmp_path, monkeypatch):
    import tkinter
    import room_control_gui as g
    config = json.loads(EXAMPLE.read_text("utf-8"))
    (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setattr(g, "BASE", tmp_path)
    root = tk_root()
    root.deiconify()
    monkeypatch.setattr(tkinter, "Tk", lambda: root)
    app = g.build_app()(tmp_path / "config.json")
    app.root.update()
    assert len(app.nb.tabs()) == 4
    cfg, errs = app.collect()
    assert not errs
    assert hasattr(app, "tree") and not hasattr(app, "im_tree")


@pytest.mark.skipif(not has_display(), reason="needs tkinter + display")
def test_im_gui_smoke(tmp_path, monkeypatch):
    import tkinter
    import im_autoreply_gui as g
    config = json.loads(EXAMPLE.read_text("utf-8"))
    config["autoreply_im"]["only_nicknames"] = ["FriendA"]
    (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setattr(g, "BASE", tmp_path)
    root = tk_root()
    root.deiconify()
    monkeypatch.setattr(tkinter, "Tk", lambda: root)
    app = g.build_app()(tmp_path / "config.json")
    app.root.update()
    assert len(app.nb.tabs()) == 4
    cfg, errs = app.collect()
    assert not errs
    assert hasattr(app, "im_tree") and not hasattr(app, "tree")
    app.tin.set("FriendA")  # a listed nick so the rule engine actually runs
    app.test_im_rule()
    assert "rule" in app.tiout.cget("text")


@pytest.mark.skipif(not has_display(), reason="needs tkinter + display")
@pytest.mark.parametrize("name", ["status_random_gui", "status_marquee_gui"])
def test_status_gui_smoke_single_mode(name, tmp_path, monkeypatch):
    import tkinter
    mod = __import__(name)
    monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
    config = copy.deepcopy(mod.DEFAULTS)
    config["status"]["messages"] = ["first status line here", "second status line"]
    cfg_path = tmp_path / "camfrog-status-config.json"
    mod.write_config(cfg_path, config)
    root = tk_root()
    root.deiconify()
    monkeypatch.setattr(tkinter, "Tk", lambda: root)
    app = mod.build_app()(cfg_path)
    app.root.update()
    assert len(app.tabs.tabs()) == 1  # one mode, no both-modes notebook
    collected = app.collect_config()
    assert collected["status"]["messages"]  # pools seeded, not lost
    assert collected["status"]["random"] is (name == "status_random_gui")
    assert collected["status"]["marquee"]["enabled"] is (name == "status_marquee_gui")


def test_marquee_runner_scrolls_frames_and_rotates_lines(monkeypatch):
    """Live-path regression: scrolled lines advance frame-by-frame then rotate.

    The engine was once suspected of not scrolling; this drives the real
    Runner.do_status with a fake clock and asserts frames move and lines
    rotate 1->2.
    """
    import status_marquee_gui as m

    cfg = copy.deepcopy(m.DEFAULTS)
    cfg["dry_run"] = True
    cfg["status"]["enabled"] = True
    cfg["status"]["messages"] = ["AAA line one here", "BBB line two here"]
    cfg["status"]["interval_seconds"] = 0.3
    cfg["status"]["history"]["enabled"] = False
    cfg["status"]["marquee"].update(enabled=True, scroll=True, width=10, stride=2,
                                    step_seconds=0.3, cycles=1, max_frames=80)
    assert m.validate(cfg)[0] == []
    r = m.Runner(cfg)
    r.status_edit, r.apply_btn, r.win = object(), None, object()
    sent = []
    monkeypatch.setattr(r, "send", lambda ctrl, text, btn=None, win=None:
                        sent.append(text) or True)
    clock = [0.0]
    monkeypatch.setattr(m.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    for _ in range(400):
        clock[0] += 0.1
        r.do_status(clock[0])
    assert len(sent) > 10, "frames never advanced"
    assert len({s[:3] for s in sent}) > 1, "lines never rotated"
    assert r.stats.get("statuses", 0) >= 2


def test_apply_sends_frames_immediately_when_scroll_on(monkeypatch):
    """Apply scrolls at once: ordered frames with step delays between sends."""
    import status_marquee_gui as m

    cfg = copy.deepcopy(m.DEFAULTS)
    cfg["dry_run"] = True
    cfg["status"]["enabled"] = True
    cfg["status"]["max_length"] = 120
    cfg["status"]["marquee"].update(enabled=True, scroll=True, width=10, stride=2,
                                    step_seconds=0.3, cycles=1, max_frames=80)
    monkeypatch.setattr(m, "get_window", lambda config: object())
    monkeypatch.setattr(m, "find", lambda win, spec: object())
    seen, sleeps = [], []
    monkeypatch.setattr(m, "commit", lambda *a: seen.append(a[2]) or True)
    monkeypatch.setattr(m.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(m, "load_cfg", lambda path: cfg)
    assert m.apply_status_scrolling("dummy.json", "status message that scrolls on") == 0
    assert len(seen) > 1, "expected several frames sent in order"
    assert seen == sorted(seen, key=lambda t: seen.index(t)) and len(set(seen)) > 1
    assert sleeps and all(s >= 0.3 for s in sleeps)


def test_apply_falls_back_to_single_shot_when_scroll_off(monkeypatch):
    """Apply with scroll off sends exactly once via the static path."""
    import status_marquee_gui as m

    cfg = copy.deepcopy(m.DEFAULTS)
    cfg["dry_run"] = True
    cfg["status"]["enabled"] = True
    cfg["status"]["marquee"].update(enabled=True, scroll=False)
    monkeypatch.setattr(m, "get_window", lambda config: object())
    monkeypatch.setattr(m, "find", lambda win, spec: object())
    seen = []
    monkeypatch.setattr(m, "commit", lambda *a: seen.append(a[2]) or True)
    monkeypatch.setattr(m, "load_cfg", lambda path: cfg)
    assert m.apply_status_scrolling("dummy.json", "hello") == 0
    assert seen == ["hello"]
