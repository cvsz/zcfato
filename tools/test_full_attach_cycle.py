import sys, time, ctypes
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))
from status_changer_gui import get_window, find, load_cfg, write_text, read_text
import win32process

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

cfg = load_cfg("dist/status-changer/status-data/marquee-status-runtime.json")
win = get_window(cfg)
ctrl = find(win, cfg["status"]["edit"])

text_to_set = "SilentAttachSuccess"
print(f"Setting text: {text_to_set!r}")
write_text(ctrl, text_to_set)
print("After write_text:", repr(read_text(ctrl)))

# Now commit using attach thread input
target_tid, target_pid = win32process.GetWindowThreadProcessId(ctrl.handle)
current_tid = kernel32.GetCurrentThreadId()

parent = getattr(getattr(ctrl, "element_info", None), "parent", None)
combo_handle = getattr(parent, "handle", 0) or ctrl.handle

print(f"Target TID: {target_tid}, Combo HWND: {combo_handle}")

# Attach thread input
user32.AttachThreadInput(current_tid, target_tid, True)
try:
    user32.SetFocus(ctrl.handle)
    # Post Enter to combo
    user32.PostMessageW(combo_handle, 0x0100, 0x0D, 0x001C0001)
    user32.PostMessageW(combo_handle, 0x0101, 0x0D, 0xC01C0001)
finally:
    user32.AttachThreadInput(current_tid, target_tid, False)

time.sleep(0.5)
print("Done. Read back:", repr(read_text(ctrl)))
