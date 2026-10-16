import ctypes, time
user32 = ctypes.windll.user32

edit_hwnd = 6359698  # Edit

print("Testing PostMessageW to Edit...")
user32.PostMessageW(edit_hwnd, 0x0100, 0x0D, 0)
user32.PostMessageW(edit_hwnd, 0x0101, 0x0D, 0)
print("Posted to edit.")
