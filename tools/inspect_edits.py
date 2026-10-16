import win32gui

for hwnd in [5966932, 6359698, 12258236, 2689430]:
    if win32gui.IsWindow(hwnd):
        txt = win32gui.GetWindowText(hwnd)
        cls = win32gui.GetClassName(hwnd)
        cid = win32gui.GetDlgCtrlID(hwnd)
        rect = win32gui.GetWindowRect(hwnd)
        print(f"hwnd={hwnd} id={cid} cls={cls} rect={rect} text={txt!r}")
