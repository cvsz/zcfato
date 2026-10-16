import ctypes
import time
import win32gui

user32 = ctypes.windll.user32
combo_hwnd = 2689430   # CComboBoxTS 1436
edit_hwnd = 6359698    # Edit 1001

print("Test 1: PostMessage to combo_hwnd with 0x0100, 0x0D, 0")
user32.PostMessageW(combo_hwnd, 0x0100, 0x0D, 0)
user32.PostMessageW(combo_hwnd, 0x0101, 0x0D, 0)
time.sleep(1)

print("Test 2: PostMessage to edit_hwnd with 0x0100, 0x0D, 0")
user32.PostMessageW(edit_hwnd, 0x0100, 0x0D, 0)
user32.PostMessageW(edit_hwnd, 0x0101, 0x0D, 0)
time.sleep(1)
