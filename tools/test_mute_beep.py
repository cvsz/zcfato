import winreg
import ctypes
import time

user32 = ctypes.windll.user32

# Read current value
key_path = r"AppEvents\Schemes\Apps\.Default\.Default\.Current"
k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ | winreg.KEY_WRITE)
orig_val, orig_type = winreg.QueryValueEx(k, "")
print("Original value:", repr(orig_val))

try:
    # Temporarily set to empty string
    winreg.SetValueEx(k, "", 0, orig_type, "")
    print("Set to empty string.")
    
    # Test MessageBeep(0)
    print("Calling MessageBeep(0)...")
    user32.MessageBeep(0)
    time.sleep(0.5)
    print("MessageBeep(0) called without sound!")
finally:
    # Restore original value
    winreg.SetValueEx(k, "", 0, orig_type, orig_val)
    print("Restored original value:", repr(orig_val))
