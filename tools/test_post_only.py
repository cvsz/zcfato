import ctypes, time
user32 = ctypes.windll.user32

combo_hwnd = 2689430 # CComboBoxTS
edit_hwnd = 6359698  # Edit

print("Testing PostMessageW to CComboBoxTS...")
user32.PostMessageW(combo_hwnd, 0x0100, 0x0D, 0)
user32.PostMessageW(combo_hwnd, 0x0101, 0x0D, 0)
print("Posted.")
