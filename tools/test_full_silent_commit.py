import sys, time, os, ctypes
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))
from status_changer_gui import get_window, find, load_cfg, write_text, read_text

cfg = load_cfg("dist/status-changer/status-data/marquee-status-runtime.json")
win = get_window(cfg)
ctrl = find(win, cfg["status"]["edit"])

parent = getattr(getattr(ctrl, "element_info", None), "parent", None)
combo_handle = getattr(parent, "handle", 0)

status_message = "Hello Silent Background"
print(f"Setting status: {status_message!r}")

# Write text in background
write_text(ctrl, status_message)
print("Text set:", repr(read_text(ctrl)))

# Silent enter
saved_sounds = {}
if os.name == "nt":
    import winreg
    base_reg = r"AppEvents\Schemes\Apps\.Default"
    for sub in (".Default", "SystemAsterisk", "SystemExclamation", "SystemNotification"):
        try:
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, f"{base_reg}\\{sub}\\.Current", 0, winreg.KEY_READ | winreg.KEY_WRITE)
            val, vtype = winreg.QueryValueEx(k, "")
            saved_sounds[sub] = (val, vtype)
            winreg.SetValueEx(k, "", 0, vtype, "")
            winreg.CloseKey(k)
        except Exception:
            pass

u = ctypes.windll.user32
try:
    lparam_down = 0x001C0001
    lparam_up = 0xC01C0001
    u.PostMessageW(combo_handle, 0x0100, 0x0D, lparam_down)
    u.PostMessageW(combo_handle, 0x0101, 0x0D, lparam_up)
    time.sleep(0.05)
finally:
    if saved_sounds:
        import winreg
        base_reg = r"AppEvents\Schemes\Apps\.Default"
        for sub, (val, vtype) in saved_sounds.items():
            try:
                k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, f"{base_reg}\\{sub}\\.Current", 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(k, "", 0, vtype, val)
                winreg.CloseKey(k)
            except Exception:
                pass

time.sleep(0.5)
print("Verification complete. Read back:", repr(read_text(ctrl)))
