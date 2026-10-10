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
def test_account_setup_stores_encrypted_file(tmp_path, monkeypatch):
    """The setup section encrypts into .env.enc and never shows the password."""
    import tkinter

    monkeypatch.setattr(wsg, "BASE", tmp_path)
    monkeypatch.delenv("CAMFROG_USER", raising=False)
    monkeypatch.delenv("CAMFROG_PASSWORD", raising=False)
    monkeypatch.setattr("tkinter.messagebox.showinfo", lambda *a, **k: None)
    monkeypatch.setattr("tkinter.messagebox.showerror", lambda *a, **k: None)
    root = tk_root()
    root.deiconify()
    monkeypatch.setattr(tkinter, "Tk", lambda: root)
    manager = wsg.WebStatusManager()
    manager.root.update()
    assert "No stored account" in manager.acct_state.cget("text")
    assert manager.acct_pw_entry.cget("show") == "\u2022"  # masked

    calls = []

    def fake_save(user, password):
        calls.append((user, password))
        (tmp_path / ".env.enc").write_text("base64blob\n", encoding="utf-8")
        return True, "saved the encrypted account for {0!r}.".format(user)

    monkeypatch.setattr(wsg, "save_credentials", fake_save)
    manager.acct_user.set("Seaza")
    manager.acct_pw.set("s3cret")
    manager.save_account()
    assert calls == [("Seaza", "s3cret")]
    assert manager.acct_pw.get() == ""  # cleared after saving
    assert ".env.enc" in manager.acct_state.cget("text") or "encrypted" in \
        manager.acct_state.cget("text")
    assert (tmp_path / ".env.enc").read_text() == "base64blob\n"


@pytest.mark.skipif(not has_display(), reason="needs tkinter + display")
def test_live_rotation_uses_the_saved_account(tmp_path, monkeypatch):
    """Live Start needs no cookies when an encrypted account is saved."""
    import tkinter

    monkeypatch.setattr(wsg, "BASE", tmp_path)
    monkeypatch.delenv("CAMFROG_USER", raising=False)
    monkeypatch.delenv("CAMFROG_PASSWORD", raising=False)
    monkeypatch.setattr("tkinter.messagebox.showinfo", lambda *a, **k: None)
    monkeypatch.setattr("tkinter.messagebox.askyesno", lambda *a, **k: True)
    root = tk_root()
    root.deiconify()
    monkeypatch.setattr(tkinter, "Tk", lambda: root)
    manager = wsg.WebStatusManager()
    manager.root.update()

    calls = []

    def fake_live_update(login, password, status, timeout, confirm=False):
        calls.append((login, password, status, confirm))
        return wsg.EXIT_OK, "status updated."

    monkeypatch.setattr(wsg, "live_update", fake_live_update)
    monkeypatch.setenv("CAMFROG_USER", "Seaza")
    monkeypatch.setenv("CAMFROG_PASSWORD", "pw")
    manager.pool_box.delete("1.0", "end")
    manager.pool_box.insert("1.0", "hello world")
    manager.live.set(True)
    manager.start()
    # the worker thread posts the result; give the pump a moment
    for _ in range(50):
        manager.root.update()
        if calls:
            break
        import time
        time.sleep(0.05)
    assert calls and calls[0][0] == "Seaza" and calls[0][2] == "hello world"
    assert calls[0][3] is True  # an armed live start is the confirmation
    manager.stop()


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

    manager.cookie_paste_var.set("cf_session=abc123")
    manager.use_pasted_cookie()
    assert manager.cookie_paste == "cf_session=abc123"
    jar = manager._session_jar()
    assert [c.name for c in jar] == ["cf_session"]

    opened = []
    monkeypatch.setattr("webbrowser.open",
                        lambda url: opened.append(url) or True)
    manager.open_login_page()
    assert opened == [wsg.LOGIN_PAGE_URL]
    assert "copy the profile cookie" in manager.paste_state.cget("text")
