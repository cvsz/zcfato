import sys
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))
from status_changer_gui import get_window, find, load_cfg

cfg = load_cfg("dist/status-changer/status-data/marquee-status-runtime.json")
win = get_window(cfg)
ctrl = find(win, cfg["status"]["edit"])
parent = ctrl.parent()

print("Edit control patterns:")
for pattern_name in ["Value", "Invoke", "Text", "Toggle", "SelectionItem", "ScrollItem"]:
    has_pat = hasattr(ctrl, f"iface_{pattern_name.lower()}") or hasattr(ctrl, f"{pattern_name.lower()}")
    print(f"  {pattern_name}: {has_pat}")

print("Parent CComboBoxTS patterns:")
for pattern_name in ["Value", "Invoke", "Text", "Toggle", "Selection", "ExpandCollapse"]:
    has_pat = hasattr(parent, f"iface_{pattern_name.lower()}") or hasattr(parent, f"{pattern_name.lower()}")
    print(f"  {pattern_name}: {has_pat}")
