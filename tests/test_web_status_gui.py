"""Tk-free tests for the web status GUI routing (no display needed)."""
import sys

import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import web_status_gui as wsg  # noqa: E402


def test_no_args_means_gui():
    assert wsg.wants_gui([]) is True


def test_any_args_mean_cli():
    assert wsg.wants_gui(["--login", "Seaza", "--status", "hi"]) is False
    assert wsg.wants_gui(["--how-to-capture"]) is False


@pytest.mark.parametrize("raw, expected", [
    ("20", 20.0),
    ("20.0", 20.0),
    ("5", 5.0),
    ("1", 5.0),      # clamped to the minimum
    ("500", 120.0),  # clamped to the maximum
    (20, 20.0),
])
def test_parse_timeout_accepts_and_clamps(raw, expected):
    assert wsg.parse_timeout(raw) == expected


@pytest.mark.parametrize("bad", ["", "abc", "nan", "inf", None])
def test_parse_timeout_rejects_garbage(bad):
    with pytest.raises(ValueError):
        wsg.parse_timeout(bad)


def test_cli_passthrough_calls_tool(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(wsg, "cli_main", lambda argv: calls.append(list(argv)) or 0)
    assert wsg.main(["--login", "Seaza", "--status", "hi"]) == 0
    assert calls == [["--login", "Seaza", "--status", "hi"]]
    capsys.readouterr()


def test_windowed_exe_routes_cli_to_dialog(monkeypatch):
    import sys

    calls = []
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(wsg, "run_cli_headless", lambda argv: calls.append(list(argv)) or 0)
    assert wsg.main(["--login", "Seaza", "--status", "hi"]) == 0
    assert calls == [["--login", "Seaza", "--status", "hi"]]


def test_windowed_cli_result_shown_not_silent(monkeypatch):
    shown = []
    monkeypatch.setattr(wsg, "cli_main", lambda argv: print("plan-output") or 0)
    code = wsg.run_cli_headless(
        ["--login", "Seaza", "--status", "hi"], show=lambda t, m: shown.append((t, m)))
    assert code == 0
    assert shown and "plan-output" in shown[0][1]


def test_windowed_exe_never_silent_on_error(monkeypatch):
    import sys

    shown = []

    def boom(argv):
        raise RuntimeError("boom")

    monkeypatch.setattr(wsg, "cli_main", boom)
    code = wsg.run_cli_headless(["--login"], show=lambda t, m: shown.append((t, m)))
    assert code == 2
    assert shown and "boom" in shown[0][1]

    def bail(argv):
        print("usage-text", file=sys.stderr)
        raise SystemExit(2)

    monkeypatch.setattr(wsg, "cli_main", bail)
    code = wsg.run_cli_headless(["--login"], show=lambda t, m: shown.append((t, m)))
    assert code == 2
    assert "usage-text" in shown[-1][1]


from conftest import has_display, tk_root  # noqa: E402




@pytest.mark.skipif(not has_display(), reason="needs tkinter + display")
def test_pasted_cookie_is_the_session_source(tmp_path, monkeypatch):
    """The Browser-login paste feeds probe and rotation instead of a file."""
    import tkinter

    monkeypatch.setattr(wsg, "BASE", tmp_path)
    root = tk_root()
    root.deiconify()
    monkeypatch.setattr(tkinter, "Tk", lambda: root)
    manager = wsg.WebStatusManager()
    manager.root.update()

    manager.cookie_paste_var.set("nonsense")
    manager.use_pasted_cookie()
    assert "devtools" in manager.paste_state.cget("text")
    assert manager.cookie_paste == ""

    manager.cookie_paste_var.set("PHPSESSID=abc1234567890123")
    manager.use_pasted_cookie()
    assert manager.cookie_paste == "PHPSESSID=abc1234567890123"
    jar = manager._session_jar()
    assert [c.name for c in jar] == ["PHPSESSID"]

    opened = []
    monkeypatch.setattr("webbrowser.open",
                        lambda url: opened.append(url) or True)
    manager.open_login_page()
    assert opened == [wsg.LOGIN_PAGE_URL]
    assert "capture PHPSESSID" in manager.paste_state.cget("text")


class _Value:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _Label:
    def __init__(self):
        self.options = {}

    def configure(self, **options):
        self.options.update(options)


class _Root:
    def __init__(self):
        self.scheduled = []

    def after(self, *args):
        self.scheduled.append(args)
        return "rotation-id"


def _bare_manager(cookie_text="", cookie_paste="", live=True):
    manager = object.__new__(wsg.WebStatusManager)
    manager.login = _Value("Seaza")
    manager.timeout = _Value("20")
    manager.interval = _Value("30")
    manager.cookie_paste_var = _Value(cookie_text)
    manager.cookie_paste = cookie_paste
    manager._cookie_from_browser = False
    manager.session_ready = False
    manager.live = _Value(live)
    manager.note = _Value()
    manager.paste_state = _Label()
    manager.switching = False
    manager.rotate_job = None
    manager.chrome_mode = False
    manager._start_generation = 0
    manager.marquee_mode = _Value(False)
    manager.infinity_loop = _Value(True)
    manager.root = object()
    manager.pool_vars = [_Value("hello")] + [_Value("") for _ in range(9)]
    manager._fields = lambda: ("Seaza", ["hello"])
    return manager


def test_login_session_verifies_php_sessid_from_entry_without_use_step():
    manager = _bare_manager("PHPSESSID=abc1234567890123")
    verified = []
    manager._verify_session = lambda *args: verified.append(args)

    manager.login_session()

    assert manager.cookie_paste == "PHPSESSID=abc1234567890123"
    assert len(verified) == 1
    assert verified[0][:2] == ("Seaza", 20.0)


def test_login_session_rejects_empty_php_sessid_and_discards_old_session():
    manager = _bare_manager("PHPSESSID=", "PHPSESSID=old1234567890123")
    manager.session_ready = True
    manager._verify_session = lambda *args: pytest.fail("must not verify an empty cookie")

    manager.login_session()

    assert manager.cookie_paste == ""
    assert manager.session_ready is False
    assert "PHPSESSID" in manager.note.get()


def test_clearing_manually_pasted_cookie_discards_cached_session():
    cookie = "PHPSESSID=abc1234567890123"
    manager = _bare_manager(cookie, cookie)
    manager.session_ready = True
    manager.cookie_paste_var.set("")

    with pytest.raises(ValueError, match="PHPSESSID"):
        manager._sync_pasted_cookie()

    assert manager.cookie_paste == ""
    assert manager.session_ready is False


def test_browser_captured_cookie_remains_available_with_empty_entry():
    cookie = "PHPSESSID=abc1234567890123"
    manager = _bare_manager("", cookie)
    manager._verify_session = lambda *args: None

    manager._browser_login_done(cookie)

    assert manager._sync_pasted_cookie() == cookie
    assert manager.cookie_paste == cookie
    assert manager._cookie_from_browser is True


def test_manually_entered_browser_cookie_is_cleared_with_its_entry():
    cookie = "PHPSESSID=abc1234567890123"
    manager = _bare_manager("", cookie)
    manager._cookie_from_browser = True
    manager.cookie_paste_var.set(cookie)

    assert manager._sync_pasted_cookie() == cookie
    assert manager._cookie_from_browser is False
    manager.cookie_paste_var.set("")

    with pytest.raises(ValueError, match="PHPSESSID"):
        manager._sync_pasted_cookie()

    assert manager.cookie_paste == ""


def test_start_verifies_latest_php_sessid_and_continues_to_rotation(monkeypatch, tmp_path):
    import sys
    import types

    tkinter = types.ModuleType("tkinter")
    tkinter.messagebox = types.SimpleNamespace(askyesno=lambda *a, **k: True)
    monkeypatch.setitem(sys.modules, "tkinter", tkinter)
    monkeypatch.setattr(wsg, "BASE", tmp_path)
    manager = _bare_manager("PHPSESSID=new1234567890123", "PHPSESSID=old1234567890123")
    verified = []
    rotations = []

    def verify(login, timeout, on_done):
        verified.append((login, timeout, manager.cookie_paste))
        on_done()

    manager._verify_session = verify
    manager._cycle = lambda *args: rotations.append(args)

    manager.start()

    assert verified == [("Seaza", 20.0, "PHPSESSID=new1234567890123")]
    assert manager.session_ready is True
    assert manager.switching is True
    assert rotations and rotations[0][0:2] == ("Seaza", ["hello"])


def test_stop_cancels_pending_live_start_callback(monkeypatch, tmp_path):
    import types

    tkinter = types.ModuleType("tkinter")
    tkinter.messagebox = types.SimpleNamespace(askyesno=lambda *a, **k: True)
    monkeypatch.setitem(sys.modules, "tkinter", tkinter)
    monkeypatch.setattr(wsg, "BASE", tmp_path)
    manager = _bare_manager("PHPSESSID=abc1234567890123")
    manager._save_web_texts = lambda notify=False: True
    callbacks = []
    rotations = []
    manager._verify_session = lambda login, timeout, on_done: callbacks.append(on_done)
    manager._cycle = lambda *args: rotations.append(args)

    manager.start()
    assert len(callbacks) == 1
    manager.stop()
    callbacks[0]()

    assert manager.switching is False
    assert manager.session_ready is False
    assert rotations == []


def test_stale_login_callback_does_not_consume_new_pending_start(monkeypatch, tmp_path):
    import types

    tkinter = types.ModuleType("tkinter")
    tkinter.messagebox = types.SimpleNamespace(askyesno=lambda *a, **k: True)
    monkeypatch.setitem(sys.modules, "tkinter", tkinter)
    monkeypatch.setattr(wsg, "BASE", tmp_path)
    manager = _bare_manager("PHPSESSID=abc1234567890123")
    manager._save_web_texts = lambda notify=False: True
    callbacks = []
    rotations = []
    manager._verify_session = lambda login, timeout, on_done: callbacks.append(on_done)
    manager._cycle = lambda *args: rotations.append(args)

    manager.start()
    manager.stop()
    manager.start()
    assert len(callbacks) == 2

    callbacks[0]()

    assert manager.switching is False
    assert manager._pending is not None
    assert rotations == []

    callbacks[1]()
    assert manager.switching is True
    assert len(rotations) == 1


def test_start_without_session_reports_guidance_instead_of_crashing(monkeypatch, tmp_path):
    manager = _bare_manager(cookie_text="", cookie_paste="")
    monkeypatch.setattr(wsg, "BASE", tmp_path)
    manager._verify_session = lambda *args: pytest.fail("must not verify without a cookie")

    manager.start()

    assert "PHPSESSID" in manager.note.get()


def test_live_cycle_calls_perform_update_with_supported_arguments(monkeypatch, tmp_path):
    monkeypatch.setattr(wsg, "BASE", tmp_path)
    manager = _bare_manager(cookie_paste="PHPSESSID=abc1234567890123")
    manager.switching = True
    manager.root = _Root()
    manager._session_jar = lambda: object()

    def run_bg(fn, force=False, on_done=None, on_error=None):
        fn()
        if on_done:
            on_done()

    manager._run_bg = run_bg
    calls = []

    def perform_update(opener, status, timeout, confirm=False):
        calls.append((status, timeout, confirm))
        return True, "status acknowledged"

    monkeypatch.setattr(wsg, "perform_update", perform_update)
    monkeypatch.setattr(wsg.urllib.request, "build_opener", lambda *args: object())

    manager._cycle("Seaza", ["hello"], 30, 20.0, True, 0)

    assert calls == [("hello", 20.0, True)]


def test_web_status_marquee_scrolls_each_message_and_settles_on_full_text():
    text = "This is a long web status message that should scroll."

    frames = wsg.web_status_frames(text, enabled=True)

    assert len(frames) > 1
    assert frames[-1] == text
    assert len(frames) <= wsg.WEB_MARQUEE_MAX_FRAMES + 1
    assert wsg.web_status_frames("short", enabled=True) == ["short"]
    assert wsg.web_status_frames(text, enabled=False) == [text]


def test_web_status_marquee_sends_one_slot_then_advances_to_next(monkeypatch, tmp_path):
    assert wsg.WEB_MARQUEE_STEP_SECONDS == 5
    monkeypatch.setattr(wsg, "BASE", tmp_path)
    manager = _bare_manager(cookie_paste="PHPSESSID=abc1234567890123")
    manager.pool_vars = [_Value("This is a long web status message that should scroll."),
                         _Value("next slot")] + [_Value("") for _ in range(8)]
    manager.marquee_mode = _Value(True)
    manager.switching = True
    manager._start_generation = 7
    manager.root = _Root()
    manager._session_jar = lambda: object()
    sent = []
    monkeypatch.setattr(wsg.urllib.request, "build_opener", lambda *args: object())
    monkeypatch.setattr(wsg, "perform_update",
                        lambda opener, status, timeout, confirm=False:
                        sent.append(status) or (True, "status acknowledged"))

    def run_bg(fn, force=False, on_done=None, on_error=None):
        try:
            fn()
        except Exception:
            if on_error:
                on_error()
        else:
            if on_done:
                on_done()

    manager._run_bg = run_bg
    manager._cycle("Seaza", [value.get() for value in manager.pool_vars if value.get()],
                   30, 20.0, True, 0)

    frames = wsg.web_status_frames(
        "This is a long web status message that should scroll.", enabled=True)
    assert sent == [frames[0]]
    assert manager.root.scheduled[0][0] == wsg.WEB_MARQUEE_STEP_SECONDS * 1000

    for _ in range(len(frames) - 1):
        delay, callback, *args = manager.root.scheduled.pop(0)
        assert delay == wsg.WEB_MARQUEE_STEP_SECONDS * 1000
        callback(*args)

    assert sent == frames
    next_delay, _callback, *next_args = manager.root.scheduled[0]
    assert next_delay == wsg.WEB_MARQUEE_STEP_SECONDS * 1000
    assert next_args[-3] == 1


def test_web_status_infinity_loop_wraps_from_last_populated_slot_to_first(monkeypatch,
                                                                          tmp_path):
    monkeypatch.setattr(wsg, "BASE", tmp_path)
    manager = _bare_manager(cookie_paste="PHPSESSID=abc1234567890123", live=False)
    manager.pool_vars = [_Value("first slot")] + [_Value("") for _ in range(8)] + [
        _Value("last slot")]
    manager.marquee_mode = _Value(True)
    manager.infinity_loop = _Value(True)
    manager.switching = True
    manager.root = _Root()

    def run_bg(fn, force=False, on_done=None, on_error=None):
        fn()
        if on_done:
            on_done()

    manager._run_bg = run_bg

    manager._cycle("Seaza", ["first slot", "last slot"], 30, 20.0, False, 1)

    scheduled = manager.root.scheduled[0]
    assert scheduled[0] == wsg.WEB_MARQUEE_STEP_SECONDS * 1000
    assert scheduled[-3] == 0


def test_web_status_marquee_without_infinity_stops_after_last_slot(monkeypatch, tmp_path):
    monkeypatch.setattr(wsg, "BASE", tmp_path)
    manager = _bare_manager(cookie_paste="PHPSESSID=abc1234567890123", live=False)
    manager.pool_vars = [_Value("first slot"), _Value("last slot")] + [
        _Value("") for _ in range(8)]
    manager.marquee_mode = _Value(True)
    manager.infinity_loop = _Value(False)
    manager.switching = True
    manager.root = _Root()

    def run_bg(fn, force=False, on_done=None, on_error=None):
        fn()
        if on_done:
            on_done()

    manager._run_bg = run_bg

    manager._cycle("Seaza", ["first slot", "last slot"], 30, 20.0, False, 1)

    assert manager.root.scheduled == []
    assert manager.switching is False


def test_failed_live_marquee_update_stops_without_scheduling_another_frame(
        monkeypatch, tmp_path):
    monkeypatch.setattr(wsg, "BASE", tmp_path)
    manager = _bare_manager(cookie_paste="PHPSESSID=abc1234567890123")
    manager.marquee_mode = _Value(True)
    manager.switching = True
    manager.root = _Root()
    manager._session_jar = lambda: object()
    monkeypatch.setattr(wsg.urllib.request, "build_opener", lambda *args: object())
    monkeypatch.setattr(wsg, "perform_update",
                        lambda *args, **kwargs: (False, "server refused"))

    def run_bg(fn, force=False, on_done=None, on_error=None):
        try:
            fn()
        except Exception:
            if on_error:
                on_error()
        else:
            if on_done:
                on_done()

    manager._run_bg = run_bg

    manager._cycle("Seaza", ["hello"], 30, 20.0, True, 0)

    assert manager.switching is False
    assert manager.root.scheduled == []
    log = (tmp_path / "web_status.log").read_text(encoding="utf-8")
    assert "Live status update failed" in log
    assert "server refused" not in log


def test_web_status_log_persists_only_allowlisted_activity(tmp_path):
    path = tmp_path / "web_status.log"

    entry = wsg.append_web_status_log("session_verification_succeeded", path)

    assert "Session verification succeeded" in entry
    assert "PHPSESSID" not in entry
    assert "abc123" not in entry
    assert wsg.load_web_status_log(path) == [entry]
    with pytest.raises(ValueError, match="unknown activity"):
        wsg.append_web_status_log("PHPSESSID=abc123", path)


def test_web_status_log_rotates_and_limits_gui_history(tmp_path, monkeypatch):
    path = tmp_path / "web_status.log"
    monkeypatch.setattr(wsg, "WEB_STATUS_LOG_MAX_BYTES", 1)

    first = wsg.append_web_status_log("session_verification_succeeded", path)
    second = wsg.append_web_status_log("dry_run_rotation_started", path)

    assert first != second
    assert path.read_text(encoding="utf-8").strip() == second
    assert (tmp_path / "web_status.log.1").read_text(encoding="utf-8").strip() == first
    monkeypatch.setattr(wsg, "WEB_STATUS_LOG_GUI_LINES", 1)
    assert wsg.load_web_status_log(path) == [second]


def test_web_text_database_persists_ten_status_lines(tmp_path):
    path = tmp_path / "webtext.db"
    lines = ["first", "", "third"] + ["line {0}".format(i) for i in range(4, 11)]

    assert wsg.load_web_text_lines(path) == [""] * 10
    assert wsg.save_web_text_lines(lines, path) == 10
    assert wsg.load_web_text_lines(path) == lines


def test_web_text_database_load_falls_back_without_overwriting_corrupt_file(tmp_path):
    path = tmp_path / "webtext.db"
    path.write_bytes(b"not a sqlite database")
    original = path.read_bytes()

    lines, warning = wsg.load_web_text_slots(path)

    assert lines == [""] * 10
    assert "webtext.db" in warning
    assert path.read_bytes() == original


@pytest.mark.skipif(not has_display(), reason="needs tkinter + display")
def test_corrupt_web_text_database_does_not_prevent_gui_open(tmp_path, monkeypatch):
    import tkinter

    monkeypatch.setattr(wsg, "BASE", tmp_path)
    path = tmp_path / "webtext.db"
    path.write_bytes(b"not a sqlite database")
    original = path.read_bytes()
    root = tk_root()
    root.deiconify()
    monkeypatch.setattr(tkinter, "Tk", lambda: root)

    manager = wsg.WebStatusManager()
    manager.root.update()

    assert len(manager.pool_entries) == 10
    assert "Could not load webtext.db" in manager.note.get()
    assert path.read_bytes() == original
    manager.stop()


def _signed_in_page():
    return ("<title>Camfrog - profile</title>"
            "<div class=\"nav-user-logged\">var _user_id = '1'; var nick = 'Seaza';")


@pytest.mark.skipif(not has_display(), reason="needs tkinter + display")
def test_login_arms_automation(tmp_path, monkeypatch):
    """The single Login button verifies the session and arms automation."""
    import tkinter

    monkeypatch.setattr(wsg, "BASE", tmp_path)
    root = tk_root()
    root.deiconify()
    monkeypatch.setattr(tkinter, "Tk", lambda: root)
    manager = wsg.WebStatusManager()
    manager.root.update()
    assert getattr(manager, "session_ready", False) is False

    monkeypatch.setattr(wsg, "fetch_profile", lambda *a: _signed_in_page())
    manager.cookie_paste_var.set("PHPSESSID=abc1234567890123")
    assert manager.btn_login.cget("text") == "Login"
    manager.btn_login.invoke()
    for _ in range(50):
        manager.root.update()
        if getattr(manager, "session_ready", False):
            break
        import time
        time.sleep(0.05)
    assert manager.session_ready is True
    assert "armed" in manager.paste_state.cget("text")
    manager.stop()


@pytest.mark.skipif(not has_display(), reason="needs tkinter + display")
def test_login_refuses_logged_out_session(tmp_path, monkeypatch):
    """A bad cookie leaves automation disarmed with the reason shown."""
    import tkinter

    monkeypatch.setattr(wsg, "BASE", tmp_path)
    root = tk_root()
    root.deiconify()
    monkeypatch.setattr(tkinter, "Tk", lambda: root)
    manager = wsg.WebStatusManager()
    manager.root.update()

    monkeypatch.setattr(wsg, "fetch_profile",
                        lambda *a: "<title>Camfrog - Login Page</title>nav-btn-sign-on")
    manager.cookie_paste_var.set("cf_session=stale")
    manager.use_pasted_cookie()
    manager.login_session()
    for _ in range(50):
        manager.root.update()
        import time
        time.sleep(0.05)
    assert getattr(manager, "session_ready", False) is False
    assert "NOT signed in" in manager.note.get()
    manager.stop()


@pytest.mark.skipif(not has_display(), reason="needs tkinter + display")
def test_start_chains_login_then_rotation(tmp_path, monkeypatch):
    """One Start press verifies the session, confirms, then rotates."""
    import tkinter

    monkeypatch.setattr(wsg, "BASE", tmp_path)
    monkeypatch.delenv("CAMFROG_USER", raising=False)
    monkeypatch.delenv("CAMFROG_PASSWORD", raising=False)
    monkeypatch.setattr("tkinter.messagebox.askyesno", lambda *a, **k: True)
    root = tk_root()
    root.deiconify()
    monkeypatch.setattr(tkinter, "Tk", lambda: root)
    manager = wsg.WebStatusManager()
    manager.root.update()
    assert len(manager.pool_entries) == 10

    monkeypatch.setattr(wsg, "fetch_profile", lambda *a: _signed_in_page())
    posted = []

    def fake_perform_update(opener, status, timeout, confirm=False):
        posted.append((status, timeout, confirm))
        return True, "status updated."

    monkeypatch.setattr(wsg, "perform_update", fake_perform_update)
    manager.cookie_paste_var.set("PHPSESSID=abc1234567890123")
    manager.pool_vars[0].set("hello world")
    manager.pool_vars[9].set("last line")
    manager.btn_save_web_text.invoke()
    assert wsg.load_web_text_lines(tmp_path / "webtext.db")[0] == "hello world"
    manager.live.set(True)
    manager.btn_start.invoke()
    for _ in range(100):
        manager.root.update()
        if posted:
            break
        import time
        time.sleep(0.05)
    assert posted, "rotation never started after chained login"
    assert posted[0] == ("hello world", 20.0, True)
    assert wsg.load_web_text_lines(tmp_path / "webtext.db")[9] == "last line"
    assert manager.session_ready is True
    manager.stop()
    assert manager.session_ready is False
