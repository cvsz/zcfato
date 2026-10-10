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


def test_pool_text_roundtrip(tmp_path):
    path = tmp_path / "pool.txt"
    text = "hello\nworld\n"
    assert wsg.save_pool_text(path, text) == len(text)
    assert wsg.load_pool_text(path) == text


def test_pool_text_unicode_roundtrip(tmp_path):
    path = tmp_path / "pool.txt"
    text = "สวัสดี\nhello\n"
    wsg.save_pool_text(path, text)
    assert wsg.load_pool_text(path) == text


def test_load_pool_text_missing_file(tmp_path):
    with pytest.raises(OSError):
        wsg.load_pool_text(tmp_path / "missing.txt")


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
    manager.cookie_paste_var.set("cf_session=abc123")
    manager.use_pasted_cookie()
    manager.login_session()
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

    monkeypatch.setattr(wsg, "fetch_profile", lambda *a: _signed_in_page())
    posted = []
    monkeypatch.setattr(wsg, "perform_update",
                        lambda *a, **k: posted.append((a, k)) or (True, "status updated."))
    manager.cookie_paste_var.set("cf_session=abc123")
    manager.use_pasted_cookie()
    manager.pool_box.delete("1.0", "end")
    manager.pool_box.insert("1.0", "hello world")
    manager.live.set(True)
    manager.start()
    for _ in range(100):
        manager.root.update()
        if posted:
            break
        import time
        time.sleep(0.05)
    assert posted, "rotation never started after chained login"
    assert manager.session_ready is True
    manager.stop()
    assert manager.session_ready is False
