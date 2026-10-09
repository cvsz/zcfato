"""Tk-free tests for the web status GUI routing (no display needed)."""
import sys
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
