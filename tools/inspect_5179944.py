import win32gui

def child_cb(hwnd, extra):
    cid = win32gui.GetDlgCtrlID(hwnd)
    cls = win32gui.GetClassName(hwnd)
    txt = win32gui.GetWindowText(hwnd)
    rect = win32gui.GetWindowRect(hwnd)
    print(f"hwnd={hwnd} id={cid} cls={cls!r} rect={rect} txt={txt!r}")

print("Children of 5179944:")
win32gui.EnumChildWindows(5179944, child_cb, None)
