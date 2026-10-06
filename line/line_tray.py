"""Native Windows notification-area icon for the standalone LINE status GUI."""
import logging
import os
from pathlib import Path
import sys


class LineTrayIcon:
    WM_TRAY = 0x8000 + 61
    ID_SHOW = 2001
    ID_EXIT = 2002
    ID_HOTKEY_SHOW = 2003

    def __init__(self, root, on_show, on_exit, icon_path=None):
        self.root = root
        self.on_show = on_show
        self.on_exit = on_exit
        self.icon_path = Path(icon_path) if icon_path else None
        self.active = False
        self.error = None
        self.hwnd = None
        self.icon = None
        self._owns_icon = False
        self._class_atom = None
        self._taskbar_created = 0
        self._show_requested = False
        self._exit_requested = False
        self._menu_requested = False
        self._restart_requested = False
        self._hotkey_requested = False
        self.hotkey_registered = False
        if os.name != "nt":
            self.error = "System tray is available only on Windows."
            return
        try:
            import win32con
            import win32gui

            self.win32con = win32con
            self.win32gui = win32gui
            self.hinstance = win32gui.GetModuleHandle(None)
            self.class_name = f"LineStatusTray_{os.getpid()}_{id(self):x}"
            self._taskbar_created = win32gui.RegisterWindowMessage("TaskbarCreated")
            wc = win32gui.WNDCLASS()
            wc.hInstance = self.hinstance
            wc.lpszClassName = self.class_name
            wc.lpfnWndProc = self._window_proc
            self._class_atom = win32gui.RegisterClass(wc)
            self.hwnd = win32gui.CreateWindowEx(
                0, self.class_name, "LINE Status Changer tray host", 0,
                0, 0, 0, 0, 0, 0, self.hinstance, None,
            )
            self.icon = self._load_icon()
            self._add_icon()
            self.active = True
            self.root.after(100, self._pump)
        except Exception as exc:
            self.error = str(exc)
            logging.exception("Could not create LINE Status Changer tray icon")
            self.shutdown()

    def _add_icon(self):
        gui = self.win32gui
        flags = gui.NIF_ICON | gui.NIF_MESSAGE | gui.NIF_TIP
        data = (self.hwnd, 1, flags, self.WM_TRAY, self.icon, "LINE Status Changer")
        try:
            # The pywin32 wrapper returns None on success; failure is raised as
            # win32gui.error. Do not treat a normal None return as rejection.
            result = gui.Shell_NotifyIcon(gui.NIM_ADD, data)
            if result is not None and not result:
                raise RuntimeError("Shell_NotifyIcon returned failure")
        except Exception as exc:
            raise RuntimeError("Windows rejected the system tray icon") from exc

    def _load_icon(self):
        gui, con = self.win32gui, self.win32con
        paths = []
        if self.icon_path:
            paths.append(self.icon_path)
        frozen_dir = getattr(sys, "_MEIPASS", None)
        if frozen_dir:
            paths.append(Path(frozen_dir) / "app.ico")
        paths.append(Path(sys.executable).resolve().parent / "app.ico")
        for path in paths:
            try:
                if path.is_file():
                    icon = gui.LoadImage(
                        0, str(path), con.IMAGE_ICON, 0, 0,
                        con.LR_LOADFROMFILE | con.LR_DEFAULTSIZE,
                    )
                    if icon:
                        self._owns_icon = True
                        return icon
            except Exception:
                pass
        return gui.LoadIcon(0, con.IDI_APPLICATION)

    def _window_proc(self, hwnd, message, wparam, lparam):
        gui, con = self.win32gui, self.win32con
        try:
            if self._taskbar_created and message == self._taskbar_created:
                self._restart_requested = True
                return 0
            if message == self.WM_TRAY:
                if lparam in (con.WM_LBUTTONUP, con.WM_LBUTTONDBLCLK):
                    self._show_requested = True
                elif lparam == con.WM_RBUTTONUP:
                    self._menu_requested = True
                return 0
            if message == con.WM_COMMAND:
                command = wparam & 0xFFFF
                if command == self.ID_SHOW:
                    self._show_requested = True
                elif command == self.ID_EXIT:
                    self._exit_requested = True
                return 0
            if message == con.WM_HOTKEY and wparam == self.ID_HOTKEY_SHOW:
                self._hotkey_requested = True
                return 0
            return gui.DefWindowProc(hwnd, message, wparam, lparam)
        except Exception:
            logging.exception("LINE tray window callback failed")
            return 0

    def _show_menu(self):
        gui, con = self.win32gui, self.win32con
        menu = gui.CreatePopupMenu()
        try:
            gui.AppendMenu(menu, con.MF_STRING, self.ID_SHOW, "Show LINE Status Changer")
            # Pywin32 requires a string argument even for MF_SEPARATOR.
            gui.AppendMenu(menu, con.MF_SEPARATOR, 0, "")
            gui.AppendMenu(menu, con.MF_STRING, self.ID_EXIT, "Exit")
            x, y = gui.GetCursorPos()
            gui.SetForegroundWindow(self.hwnd)
            gui.TrackPopupMenu(menu, con.TPM_RIGHTBUTTON, x, y, 0, self.hwnd, None)
            gui.PostMessage(self.hwnd, con.WM_NULL, 0, 0)
        finally:
            gui.DestroyMenu(menu)

    def set_show_hotkey(self, enabled):
        """Register Ctrl+Alt+L to show the app; never binds a status write."""
        if not self.active:
            return False
        if self.hotkey_registered:
            try:
                self.win32gui.UnregisterHotKey(self.hwnd, self.ID_HOTKEY_SHOW)
            finally:
                self.hotkey_registered = False
        if not enabled:
            return True
        con = self.win32con
        modifiers = con.MOD_CONTROL | con.MOD_ALT | getattr(con, "MOD_NOREPEAT", 0x4000)
        self.win32gui.RegisterHotKey(self.hwnd, self.ID_HOTKEY_SHOW, modifiers, ord("L"))
        self.hotkey_registered = True
        return True

    def notify(self, title, message):
        """Request a short Windows tray balloon notification."""
        if not self.active:
            return False
        gui, con = self.win32gui, self.win32con
        flags = con.NIF_INFO | con.NIF_ICON | con.NIF_TIP
        data = (
            self.hwnd, 1, flags, self.WM_TRAY, self.icon, "LINE Status Changer",
            0, 0, str(message)[:255], 8000, str(title)[:63], con.NIIF_INFO,
        )
        try:
            result = gui.Shell_NotifyIcon(gui.NIM_MODIFY, data)
            return result is None or bool(result)
        except Exception:
            logging.exception("Could not show LINE tray notification")
            return False

    def _pump(self):
        if not self.active:
            return
        try:
            self.win32gui.PumpWaitingMessages()
            if self._restart_requested:
                self._restart_requested = False
                self._add_icon()
            if self._menu_requested:
                self._menu_requested = False
                self._show_menu()
            if self._exit_requested:
                self._exit_requested = False
                self.on_exit()
                return
            show_requested = self._show_requested or self._hotkey_requested
            self._show_requested = False
            self._hotkey_requested = False
            if show_requested:
                self.on_show()
        except Exception as exc:
            self.error = str(exc)
            logging.exception("LINE tray message pump failed")
            self.shutdown()
            try:
                # Never leave the app inaccessible after its tray host fails.
                self.on_show()
            except Exception:
                logging.exception("Could not restore LINE GUI after tray failure")
            return
        if self.active:
            try:
                self.root.after(100, self._pump)
            except Exception:
                self.shutdown()

    def shutdown(self):
        if not self.active and not self.hwnd:
            return
        gui = getattr(self, "win32gui", None)
        if gui:
            try:
                if self.hwnd and self.hotkey_registered:
                    gui.UnregisterHotKey(self.hwnd, self.ID_HOTKEY_SHOW)
            except Exception:
                pass
            try:
                if self.hwnd:
                    gui.Shell_NotifyIcon(gui.NIM_DELETE, (self.hwnd, 1))
            except Exception:
                pass
            try:
                if self.hwnd:
                    gui.DestroyWindow(self.hwnd)
            except Exception:
                pass
            try:
                if self._class_atom:
                    gui.UnregisterClass(self.class_name, self.hinstance)
            except Exception:
                pass
            try:
                if self._owns_icon and self.icon:
                    gui.DestroyIcon(self.icon)
            except Exception:
                pass
        self.active = False
        self.hwnd = None
        self.icon = None
        self._owns_icon = False
        self._class_atom = None
        self.hotkey_registered = False
