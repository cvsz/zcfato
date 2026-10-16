import ctypes
import time
import win32process
import win32gui

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

combo_hwnd = 2689430   # CComboBoxTS 1436
edit_hwnd = 6359698    # Edit 1001

# Let's see thread IDs
target_tid, target_pid = win32process.GetWindowThreadProcessId(combo_hwnd)
current_tid = kernel32.GetCurrentThreadId()

print(f"Target TID: {target_tid}, PID: {target_pid}, Current TID: {current_tid}")

# Test if AttachThreadInput allows clean Enter
print("Attaching thread input...")
attached = user32.AttachThreadInput(current_tid, target_tid, True)
print("Attached:", attached)

try:
    # Check focus
    old_focus = user32.GetFocus()
    print("Old focus:", old_focus)
    
    # Set focus to edit or combo within attached threads
    user32.SetFocus(edit_hwnd)
    print("New focus:", user32.GetFocus())
    
    # Post Enter or Send Enter
    print("Sending Enter...")
    user32.PostMessageW(combo_hwnd, 0x0100, 0x0D, 0x001C0001)
    user32.PostMessageW(combo_hwnd, 0x0101, 0x0D, 0xC01C0001)
    time.sleep(0.1)
finally:
    user32.AttachThreadInput(current_tid, target_tid, False)
    print("Detached.")
