import sys
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))
from status_changer_gui import get_window, find, load_cfg

cfg = load_cfg("dist/status-changer/status-data/marquee-status-runtime.json")
win = get_window(cfg)
print("win:", win, win.handle)
ctrl = find(win, cfg["status"]["edit"])
print("found ctrl:", ctrl, ctrl.handle)
parent = getattr(getattr(ctrl, "element_info", None), "parent", None)
print("parent:", parent, getattr(parent, "handle", 0), getattr(parent, "class_name", ""))
