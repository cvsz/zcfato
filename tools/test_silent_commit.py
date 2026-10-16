import winreg
import ctypes
import time

user32 = ctypes.windll.user32
REG_PATH = r"AppEvents\Schemes\Apps\.Default\.Default\.Current"

def silent_enter(combo_hwnd):
    # Temporarily mute default beep in registry
    orig_val = None
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ | winreg.KEY_WRITE)
        orig_val, orig_type = winreg.QueryValueEx(k, "")
        winreg.SetValueEx(k, "", 0, orig_type, "")
    except Exception as e:
        print("Reg mute error:", e)

    try:
        # Post Enter to combo
        user32.PostMessageW(combo_hwnd, 0x0100, 0x0D, 0x001C0001)
        user32.PostMessageW(combo_hwnd, 0x0101, 0x0D, 0xC01C0001)
        time.sleep(0.05)
    finally:
        if orig_val is not None:
            try:
                winreg.SetValueEx(k, "", 0, orig_type, orig_val)
                winreg.CloseKey(k)
            except Exception as e:
                print("Reg restore error:", e)

combo_hwnd = 2689430
print("Testing silent_enter...")
silent_enter(combo_hwnd)
print("silent_enter completed successfully!")

# Verify registry is restored
k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
val, _ = winreg.QueryValueEx(k, "")
print("Verified restored value:", repr(val))
