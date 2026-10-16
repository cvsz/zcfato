import sys
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))
from status_changer_gui import get_window, find, load_cfg, write_text, read_text

cfg = load_cfg("dist/status-changer/status-data/marquee-status-runtime.json")
win = get_window(cfg)
ctrl = find(win, cfg["status"]["edit"])
print("found ctrl:", ctrl)
print("before write_text:", repr(read_text(ctrl)))
res = write_text(ctrl, "TestStatusUIA")
print("write_text result:", res)
print("after write_text:", repr(read_text(ctrl)))
