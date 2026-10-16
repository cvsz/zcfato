import win32gui
import win32con

def callback(hwnd, extra):
    title = win32gui.GetWindowText(hwnd)
    if "Camfrog" in title:
        cls = win32gui.GetClassName(hwnd)
        print(f"Window: hwnd={hwnd} title={title!r} class={cls}")
        def child_cb(c_hwnd, extra2):
            cid = win32gui.GetDlgCtrlID(c_hwnd)
            ccls = win32gui.GetClassName(c_hwnd)
            ctxt = win32gui.GetWindowText(c_hwnd)
            if cid in (1001, 1436) or "combo" in ccls.lower() or "edit" in ccls.lower():
                parent = win32gui.GetParent(c_hwnd)
                pcls = win32gui.GetClassName(parent) if parent else ""
                print(f"  Child: hwnd={c_hwnd} id={cid} class={ccls!r} parent={parent}({pcls}) text={ctxt!r}")
        win32gui.EnumChildWindows(hwnd, child_cb, None)

win32gui.EnumWindows(callback, None)
