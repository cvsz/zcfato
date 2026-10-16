import win32gui, win32con
import time

parent_dialog = 4983918 # #32770
combo_hwnd = 2689430   # CComboBoxTS 1436
edit_hwnd = 6359698    # Edit 1001

# Let's see what happens when we set text
WM_SETTEXT = 0x000C
text = "SilentStatusTest"
win32gui.SendMessage(edit_hwnd, WM_SETTEXT, 0, text)
print("Text set. Current edit text:", repr(win32gui.GetWindowText(edit_hwnd)))

# Test method 1: Does sending WM_COMMAND CBN_SELENDOK commit it?
# CBN_SELENDOK = 9
# wParam = (9 << 16) | 1436
wparam = (9 << 16) | 1436
print("Sending WM_COMMAND CBN_SELENDOK...")
win32gui.SendMessage(parent_dialog, win32con.WM_COMMAND, wparam, combo_hwnd)
time.sleep(1)
print("After CBN_SELENDOK, edit text:", repr(win32gui.GetWindowText(edit_hwnd)))
