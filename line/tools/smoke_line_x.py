"""Windows UI smoke check for the built app's title-bar X and tray Exit."""
import os
from pathlib import Path
import subprocess
import tempfile
import time
import winreg

import win32con
import win32gui
from pywinauto import Desktop, mouse


PROJECT = Path(__file__).resolve().parents[1]
EXE = PROJECT / "dist" / "line-status-changer.exe"
CONFIG = Path(tempfile.gettempdir()) / f"line-x-smoke-{os.getpid()}.json"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "LINEStatusChanger"


def read_startup_entry():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            return winreg.QueryValueEx(key, RUN_VALUE)
    except FileNotFoundError:
        return None


def restore_startup_entry(entry):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if entry is None:
            try:
                winreg.DeleteValue(key, RUN_VALUE)
            except FileNotFoundError:
                pass
        else:
            winreg.SetValueEx(key, RUN_VALUE, 0, entry[1], entry[0])


def main():
    startup_before = read_startup_entry()
    process = subprocess.Popen([str(EXE), "--config", str(CONFIG)])
    host = None
    try:
        window = Desktop(backend="win32").window(title="LINE Status Changer")
        window.wait("exists visible enabled", timeout=30)
        window.set_focus()
        time.sleep(0.2)
        hwnd = window.handle
        _left, top, right, _bottom = win32gui.GetWindowRect(hwnd)
        x, y = right - 18, top + 15
        mouse.click(button="left", coords=(x, y))

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and win32gui.IsWindowVisible(hwnd):
            time.sleep(0.1)
        if win32gui.IsWindowVisible(hwnd):
            raise AssertionError(
                f"Clicking title-bar X at {(x, y)} did not hide the GUI window "
                f"(rect={(right, top)}, iconic={win32gui.IsIconic(hwnd)})"
            )
        if process.poll() is not None:
            raise AssertionError("Clicking X exited the process instead of sending it to tray")

        tray_windows = []

        def collect(hwnd, _extra):
            if win32gui.GetWindowText(hwnd) == "LINE Status Changer tray host":
                tray_windows.append(hwnd)
            return True

        win32gui.EnumWindows(collect, None)
        if not tray_windows:
            raise AssertionError("Tray host was not found after clicking X")
        host = tray_windows[0]
        win32gui.PostMessage(host, win32con.WM_COMMAND, 2002, 0)
        process.wait(timeout=10)
        if process.returncode != 0:
            raise AssertionError(f"Tray Exit returned process code {process.returncode}")
        if read_startup_entry() != startup_before:
            raise AssertionError("Launching with a temporary config changed Windows startup")
        print("PASS: title-bar X hides to tray; tray Exit closes the process cleanly")
    finally:
        if process.poll() is None:
            if host:
                try:
                    win32gui.PostMessage(host, win32con.WM_COMMAND, 2002, 0)
                    process.wait(timeout=3)
                except Exception:
                    pass
            if process.poll() is None:
                # PyInstaller one-file uses a bootloader parent/worker pair;
                # terminate the process tree so a failed test cannot strand
                # the GUI worker in the tray.
                subprocess.run(
                    ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    check=False,
                )
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    subprocess.run(
                        ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        check=False,
                    )
        CONFIG.unlink(missing_ok=True)
        if read_startup_entry() != startup_before:
            restore_startup_entry(startup_before)


if __name__ == "__main__":
    main()
