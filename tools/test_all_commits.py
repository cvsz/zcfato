import win32gui, win32con
import time

dialog_hwnd = 5179944  # parent of CComboBoxTS
top_hwnd = 4983918     # top-level Camfrog window
combo_hwnd = 2689430   # CComboBoxTS 1436
edit_hwnd = 6359698    # Edit 1001

import sys
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))
from status_changer_gui import get_window, find, load_cfg, write_text, read_text

cfg = load_cfg("dist/status-changer/status-data/marquee-status-runtime.json")
win = get_window(cfg)
ctrl = find(win, cfg["status"]["edit"])

methods = [
    ("WM_COMMAND IDOK to parent dialog", lambda: win32gui.SendMessage(dialog_hwnd, win32con.WM_COMMAND, 1, 0)),
    ("WM_COMMAND IDOK to top dialog", lambda: win32gui.SendMessage(top_hwnd, win32con.WM_COMMAND, 1, 0)),
    ("WM_COMMAND CBN_SELENDOK to dialog", lambda: win32gui.SendMessage(dialog_hwnd, win32con.WM_COMMAND, (9 << 16) | 1436, combo_hwnd)),
    ("WM_COMMAND CBN_SELCHANGE to dialog", lambda: win32gui.SendMessage(dialog_hwnd, win32con.WM_COMMAND, (1 << 16) | 1436, combo_hwnd)),
]

for name, fn in methods:
    print(f"\n--- Testing method: {name} ---")
    status_str = f"Status_{int(time.time()) % 1000}"
    write_text(ctrl, status_str)
    print("Wrote text:", status_str)
    fn()
    time.sleep(0.5)
    print("Read back:", repr(read_text(ctrl)))
