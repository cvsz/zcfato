import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))
from status_changer_gui import get_window, find, load_cfg, commit

cfg = load_cfg("dist/status-changer/status-data/marquee-status-runtime.json")
win = get_window(cfg)
ctrl = find(win, cfg["status"]["edit"])
st = cfg["status"]
sf = cfg["safety"]

print("Calling commit with text 'TestStatus'...")
ok = commit(win, ctrl, "TestStatus", dry=False,
            require_fg=sf["require_foreground"],
            apply_btn=None,
            restore=sf["restore_previous_window"],
            background_enter_target=st.get("background_enter_target", "combo"),
            background_if_not_foreground=True)
print("commit returned:", ok)
