import json
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from config_store import (
    ConfigError,
    default_config,
    load_config,
    save_config,
    validate_config,
    validate_status_text,
)
from line_automation import (
    accessible_context_names,
    check_line_window,
    has_status_context,
    has_status_context_broad,
    is_profile_name_context,
    is_save_name,
    is_status_name,
    is_status_name_broad,
    process_for_window,
)
from line_tray import LineTrayIcon
from schedule_engine import due_schedules, mark_schedule_fired
from windows_features import startup_command, validate_profile_image


class StatusTextTests(unittest.TestCase):
    def test_keeps_unicode_and_spaces_exact(self):
        text = " สวัสดี 👋 你好 "
        self.assertEqual(validate_status_text(text), text)

    def test_rejects_blank_multiline_and_controls(self):
        for text in ("", " \t ", "one\ntwo", "status\x00bad"):
            with self.subTest(text=repr(text)), self.assertRaises(ValueError):
                validate_status_text(text)

    def test_rejects_unpaired_surrogate(self):
        with self.assertRaises(ValueError):
            validate_status_text("bad\ud800")


class ConfigStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "line_config.json"

    def tearDown(self):
        self.temp.cleanup()

    def test_missing_file_is_initialized(self):
        data = load_config(self.path)
        self.assertEqual(data, default_config())
        self.assertTrue(self.path.is_file())
        self.assertEqual(load_config(self.path), data)

    def test_reads_legacy_config_and_adds_schema_on_save(self):
        self.path.write_text(json.dumps({"last_text": "ไทย", "messages": ["ok"]}),
                             encoding="utf-8")
        data = load_config(self.path)
        self.assertEqual(data["last_text"], "ไทย")
        save_config(self.path, data)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["schema_version"], 2)
        self.assertEqual(load_config(self.path)["schedule"]["items"], [])

    def test_round_trips_unicode_and_preserves_unknown_keys(self):
        data = default_config()
        data["last_text"] = "ภาษาไทย 👋"
        data["messages"] = ["中文", "日本語", "emoji 🧑‍💻"]
        data["custom"] = {"kept": True}
        save_config(self.path, data)
        loaded = load_config(self.path)
        self.assertEqual(loaded["last_text"], data["last_text"])
        self.assertEqual(loaded["messages"], data["messages"])
        self.assertEqual(loaded["custom"], {"kept": True})

    def test_rejects_malformed_config_without_replacing_it(self):
        original = "{ invalid json"
        self.path.write_text(original, encoding="utf-8")
        with self.assertRaises(ConfigError):
            load_config(self.path)
        self.assertEqual(self.path.read_text(encoding="utf-8"), original)

    def test_rejects_wrong_schema_and_invalid_saved_messages(self):
        with self.assertRaises(ConfigError):
            validate_config({"schema_version": 99})
        with self.assertRaises(ConfigError):
            validate_config({"messages": [""]})
        with self.assertRaises(ConfigError):
            validate_config({"last_text": 1})

    def test_interval_schedule_ignores_irrelevant_weekly_fields(self):
        config = default_config()
        config["schedule"]["items"] = [{
            "id": "interval", "mode": "interval", "interval_minutes": 30,
            "text": "Hi", "time": {"not": "a time"}, "days": [1, "bad"],
        }]
        normalized = validate_config(config)
        item = normalized["schedule"]["items"][0]
        self.assertEqual(item["time"], "")
        self.assertEqual(item["days"], [])

    def test_legacy_tray_setting_is_removed(self):
        self.assertNotIn("tray_on_close", validate_config({"tray_on_close": False}))

    def test_atomic_save_failure_keeps_original_and_cleans_temp_file(self):
        self.path.write_text('{"existing": true}\n', encoding="utf-8")
        with mock.patch("config_store.os.replace", side_effect=OSError("simulated")):
            with self.assertRaises(OSError):
                save_config(self.path, default_config())
        self.assertEqual(self.path.read_text(encoding="utf-8"), '{"existing": true}\n')
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])


class AccessibilityGuardTests(unittest.TestCase):
    def test_status_context_requires_status_message_label(self):
        self.assertTrue(is_status_name("Status message"))
        self.assertTrue(is_status_name("ข้อความสถานะ"))
        self.assertTrue(has_status_context(["Profile", "Status message"]))
        self.assertFalse(has_status_context(["Search", "Write a message"]))

    def test_status_label_is_scoped_to_nearby_field_group(self):
        class Node:
            def __init__(self, name, children=()):
                self.name = name
                self._children = list(children)
                self.parent = None
                for child in self._children:
                    child.parent = self

            def children(self):
                return self._children

        status_label = Node("Status message")
        status_edit = Node("")
        status_group = Node("", [status_label, status_edit])
        name_label = Node("Name")
        name_edit = Node("")
        name_group = Node("", [name_label, name_edit])
        Node("Profile", [status_group, name_group])

        self.assertTrue(has_status_context(accessible_context_names(status_edit)))
        self.assertFalse(has_status_context(accessible_context_names(name_edit)))

    def test_save_button_match_is_exact(self):
        self.assertTrue(is_save_name("Save"))
        self.assertTrue(is_save_name("บันทึก"))
        self.assertFalse(is_save_name("Save draft"))
        self.assertFalse(is_save_name("Save messages"))

    def test_profile_name_match_is_exact(self):
        from line_automation import is_profile_name_field
        self.assertTrue(is_profile_name_field("Display name"))
        self.assertTrue(is_profile_name_field("ชื่อโปรไฟล์"))
        self.assertFalse(is_profile_name_field("Username and password"))

    def test_profile_name_requires_profile_section_context(self):
        self.assertTrue(is_profile_name_context(["Name", "Profile"]))
        self.assertTrue(is_profile_name_context(["Display name", "Edit profile settings"]))
        self.assertFalse(is_profile_name_context(["Name", "Search"]))
        self.assertFalse(is_profile_name_context(["Name", "Search profile"]))
        self.assertFalse(is_profile_name_context(["Username and password", "Profile"]))

    def test_save_click_is_not_misreported_when_readback_raises(self):
        from line_automation import set_profile_status

        editor = SimpleNamespace(set_edit_text=mock.Mock(), get_value=mock.Mock(return_value="hello"))
        save_button = SimpleNamespace(is_enabled=mock.Mock(return_value=True),
                                      is_visible=mock.Mock(return_value=True),
                                      invoke=mock.Mock())
        with (
            mock.patch.dict("sys.modules", {"pywinauto": mock.Mock()}),
            mock.patch("line_automation._focused_profile_editor", return_value=editor),
            mock.patch("line_automation._find_save_button", return_value=save_button),
            mock.patch("line_automation._verify_profile_value", side_effect=OSError("UIA offline")),
            mock.patch("line_automation.logging.exception"),
        ):
            result = set_profile_status(1, 2, "hello")
        self.assertTrue(result.entered)
        self.assertTrue(result.save_clicked)
        self.assertFalse(result.verified)
        save_button.invoke.assert_called_once_with()

    def test_localized_field_names(self):
        for label in ("Status message", "Mensaje de estado", "Message de statut",
                      "Statusmeldung", "Mensagem de status", "ข้อความสถานะ"):
            with self.subTest(label=label):
                self.assertTrue(is_status_name(label))

    def test_broad_labels_catch_bare_status_wording(self):
        # Bare labels match the broad pass but strict stays scoped.
        self.assertTrue(is_status_name_broad("สถานะ"))
        self.assertTrue(is_status_name_broad("Status"))
        self.assertTrue(is_status_name_broad("ข้อความสถานะ"))
        self.assertFalse(is_status_name("สถานะ"))
        self.assertFalse(is_status_name_broad(""))
        self.assertFalse(is_status_name_broad(None))
        # Broad context still requires the status word nearby.
        self.assertTrue(has_status_context_broad(["Profile", "สถานะ"]))
        self.assertFalse(has_status_context_broad(["Search", "Write a message"]))

    def test_check_line_window_distinguishes_closed_changed_and_foreign(self):
        from line_automation import AutomationError
        gui = types.ModuleType("win32gui")
        gui.IsWindow = mock.Mock(return_value=False)
        with mock.patch.dict(sys.modules, {"win32gui": gui}):
            with self.assertRaisesRegex(AutomationError, "was closed"):
                check_line_window(1234, 9001)
        # Valid LINE window passes without raising.
        api = types.ModuleType("win32api")
        api.OpenProcess = mock.Mock(return_value="h")
        api.CloseHandle = mock.Mock()
        con = types.ModuleType("win32con")
        con.PROCESS_QUERY_INFORMATION = 0x0400
        con.PROCESS_VM_READ = 0x0010
        gui2 = types.ModuleType("win32gui")
        gui2.IsWindow = mock.Mock(return_value=True)
        process = types.ModuleType("win32process")
        process.GetWindowThreadProcessId = mock.Mock(return_value=(42, 9001))
        process.GetModuleFileNameEx = mock.Mock(return_value="C:/Apps/LINE/LINE.exe")
        with mock.patch.dict(sys.modules, {
            "win32api": api, "win32con": con, "win32gui": gui2,
            "win32process": process,
        }):
            check_line_window(1234, 9001)  # must not raise
        # Same hwnd but different pid -> "changed" error.
        with mock.patch.dict(sys.modules, {
            "win32api": api, "win32con": con, "win32gui": gui2,
            "win32process": process,
        }):
            with self.assertRaisesRegex(AutomationError, "changed"):
                check_line_window(1234, 1111)

    def test_process_for_window_imports_win32process_and_checks_executable(self):
        api = types.ModuleType("win32api")
        api.OpenProcess = mock.Mock(return_value="process-handle")
        api.CloseHandle = mock.Mock()
        con = types.ModuleType("win32con")
        con.PROCESS_QUERY_INFORMATION = 0x0400
        con.PROCESS_VM_READ = 0x0010
        gui = types.ModuleType("win32gui")
        gui.IsWindow = mock.Mock(return_value=True)
        process = types.ModuleType("win32process")
        process.GetWindowThreadProcessId = mock.Mock(return_value=(42, 9001))
        process.GetModuleFileNameEx = mock.Mock(return_value="C:/Apps/LINE/LINE.exe")
        with mock.patch.dict(sys.modules, {
            "win32api": api, "win32con": con, "win32gui": gui,
            "win32process": process,
        }):
            self.assertEqual(process_for_window(1234), (9001, "C:/Apps/LINE/LINE.exe"))
        api.CloseHandle.assert_called_once_with("process-handle")

    def test_process_for_window_rejects_other_executable(self):
        api = types.ModuleType("win32api")
        api.OpenProcess = mock.Mock(return_value="process-handle")
        api.CloseHandle = mock.Mock()
        con = types.ModuleType("win32con")
        con.PROCESS_QUERY_INFORMATION = 0x0400
        con.PROCESS_VM_READ = 0x0010
        gui = types.ModuleType("win32gui")
        gui.IsWindow = mock.Mock(return_value=True)
        process = types.ModuleType("win32process")
        process.GetWindowThreadProcessId = mock.Mock(return_value=(42, 9001))
        process.GetModuleFileNameEx = mock.Mock(return_value="C:/Apps/not-line.exe")
        with mock.patch.dict(sys.modules, {
            "win32api": api, "win32con": con, "win32gui": gui,
            "win32process": process,
        }):
            self.assertIsNone(process_for_window(1234))
        api.CloseHandle.assert_called_once_with("process-handle")


try:
    import tkinter as _tkinter
    _HAS_TK = True
except ImportError:
    _HAS_TK = False


@unittest.skipUnless(_HAS_TK, "Tkinter is not installed in this Python environment")
class GuiCloseBehaviorTests(unittest.TestCase):
    def test_close_hides_in_tray_when_tray_is_available(self):
        from line_status_gui import build_app

        app_type = build_app()
        app = object.__new__(app_type)
        app.tray = SimpleNamespace(active=True)
        app.root = mock.Mock()
        app.hide_to_tray()
        app.root.withdraw.assert_called_once_with()
        app.root.iconify.assert_not_called()

    def test_exit_stops_tray_host_and_destroys_root(self):
        from line_status_gui import build_app

        app_type = build_app()
        app = object.__new__(app_type)
        app.busy = False
        app.save_job = None
        app.root = mock.Mock()
        app.tray = SimpleNamespace(shutdown=mock.Mock())
        app.save_last_text = mock.Mock()
        app.exit()
        app.save_last_text.assert_called_once_with()
        app.tray.shutdown.assert_called_once_with()
        app.root.destroy.assert_called_once_with()

    def test_startup_registry_change_rolls_back_if_config_save_fails(self):
        from line_status_gui import build_app

        app_type = build_app()
        app = object.__new__(app_type)
        app.startup_var = SimpleNamespace(get=lambda: True, set=mock.Mock())
        app.config = {"start_with_windows": False}
        app.config_path = Path("line_config.json")
        app.persist_config = mock.Mock(side_effect=OSError("disk full"))
        app.note = mock.Mock()
        with (
            mock.patch("line_status_gui.set_startup") as set_startup,
            mock.patch("line_status_gui.logging.exception"),
        ):
            app.toggle_startup()
        self.assertEqual([call.args[0] for call in set_startup.call_args_list], [True, False])
        self.assertFalse(app.config["start_with_windows"])
        app.startup_var.set.assert_called_once_with(False)

    def test_hotkey_registration_rolls_back_if_config_save_fails(self):
        from line_status_gui import build_app

        app_type = build_app()
        app = object.__new__(app_type)
        app.hotkey_var = SimpleNamespace(get=lambda: True, set=mock.Mock())
        app.config = {"show_hotkey": False}
        app.tray = SimpleNamespace(set_show_hotkey=mock.Mock(return_value=True))
        app.persist_config = mock.Mock(side_effect=OSError("disk full"))
        app.note = mock.Mock()
        with mock.patch("line_status_gui.logging.exception"):
            app.toggle_hotkey()
        self.assertEqual([call.args[0] for call in app.tray.set_show_hotkey.call_args_list],
                         [True, False])
        self.assertFalse(app.config["show_hotkey"])
        app.hotkey_var.set.assert_called_once_with(False)


class TrayBehaviorTests(unittest.TestCase):
    def test_context_menu_uses_valid_separator_text(self):
        tray = object.__new__(LineTrayIcon)
        tray.ID_SHOW = 2001
        tray.ID_EXIT = 2002
        tray.hwnd = 101
        tray.win32con = SimpleNamespace(
            MF_STRING=0,
            MF_SEPARATOR=0x800,
            TPM_RIGHTBUTTON=2,
            WM_NULL=0,
        )
        tray.win32gui = SimpleNamespace(
            CreatePopupMenu=mock.Mock(return_value=500),
            AppendMenu=mock.Mock(),
            GetCursorPos=mock.Mock(return_value=(10, 20)),
            SetForegroundWindow=mock.Mock(),
            TrackPopupMenu=mock.Mock(),
            PostMessage=mock.Mock(),
            DestroyMenu=mock.Mock(),
        )
        tray._show_menu()
        tray.win32gui.AppendMenu.assert_any_call(500, tray.win32con.MF_SEPARATOR, 0, "")
        tray.win32gui.TrackPopupMenu.assert_called_once()
        tray.win32gui.DestroyMenu.assert_called_once_with(500)

    def test_pywin32_none_return_is_success(self):
        tray = object.__new__(LineTrayIcon)
        tray.win32gui = SimpleNamespace(
            NIF_ICON=2,
            NIF_MESSAGE=1,
            NIF_TIP=4,
            NIM_ADD=0,
            Shell_NotifyIcon=mock.Mock(return_value=None),
        )
        tray.hwnd = 101
        tray.icon = 202
        tray.WM_TRAY = 32829
        tray._add_icon()
        tray.win32gui.Shell_NotifyIcon.assert_called_once()

    def test_tray_registration_exception_is_reported(self):
        tray = object.__new__(LineTrayIcon)
        tray.win32gui = SimpleNamespace(
            NIF_ICON=2,
            NIF_MESSAGE=1,
            NIF_TIP=4,
            NIM_ADD=0,
            Shell_NotifyIcon=mock.Mock(side_effect=OSError("shell unavailable")),
        )
        tray.hwnd = 101
        tray.icon = 202
        tray.WM_TRAY = 32829
        with self.assertRaisesRegex(RuntimeError, "rejected the system tray icon"):
            tray._add_icon()

    def test_tray_registration_false_result_is_reported(self):
        tray = object.__new__(LineTrayIcon)
        tray.win32gui = SimpleNamespace(
            NIF_ICON=2,
            NIF_MESSAGE=1,
            NIF_TIP=4,
            NIM_ADD=0,
            Shell_NotifyIcon=mock.Mock(return_value=False),
        )
        tray.hwnd = 101
        tray.icon = 202
        tray.WM_TRAY = 32829
        with self.assertRaisesRegex(RuntimeError, "rejected the system tray icon"):
            tray._add_icon()

    def test_tray_retry_succeeds_on_second_attempt(self):
        tray = object.__new__(LineTrayIcon)
        tray._add_icon = mock.Mock(side_effect=[RuntimeError("busy"), None])
        with mock.patch("line_tray.time.sleep") as sleep:
            tray._add_icon_with_retry(attempts=3, delay=0.5)
        self.assertEqual(tray._add_icon.call_count, 2)
        sleep.assert_called_once_with(0.5)

    def test_tray_retry_raises_after_all_attempts_fail(self):
        tray = object.__new__(LineTrayIcon)
        tray._add_icon = mock.Mock(side_effect=RuntimeError("busy"))
        with mock.patch("line_tray.time.sleep"):
            with self.assertRaisesRegex(RuntimeError, "rejected the system tray icon"):
                tray._add_icon_with_retry(attempts=3, delay=0.1)
        self.assertEqual(tray._add_icon.call_count, 3)

    def test_window_callback_defers_tk_restore_until_message_pump_returns(self):
        tray = object.__new__(LineTrayIcon)
        tray.root = mock.Mock()
        tray.win32gui = SimpleNamespace(DefWindowProc=mock.Mock(return_value=0))
        tray.win32con = SimpleNamespace(
            WM_LBUTTONUP=0x0202,
            WM_LBUTTONDBLCLK=0x0203,
            WM_RBUTTONUP=0x0205,
            WM_COMMAND=0x0111,
        )
        tray._taskbar_created = 0
        tray._show_requested = False
        tray._exit_requested = False
        tray._menu_requested = False
        tray._restart_requested = False
        self.assertEqual(tray._window_proc(1, tray.WM_TRAY, 1, 0x0202), 0)
        self.assertTrue(tray._show_requested)
        tray.root.after.assert_not_called()

    def test_hotkey_message_requests_restore(self):
        tray = object.__new__(LineTrayIcon)
        tray.root = mock.Mock()
        tray.win32gui = SimpleNamespace(DefWindowProc=mock.Mock(return_value=0))
        tray.win32con = SimpleNamespace(WM_HOTKEY=0x0312, WM_COMMAND=0x0111)
        tray._taskbar_created = 0
        tray._show_requested = False
        tray._hotkey_requested = False
        tray._exit_requested = False
        tray._menu_requested = False
        tray._restart_requested = False
        self.assertEqual(tray._window_proc(1, 0x0312, tray.ID_HOTKEY_SHOW, 0), 0)
        self.assertTrue(tray._hotkey_requested)


class ScheduleTests(unittest.TestCase):
    def test_weekly_schedule_fires_once_inside_grace_window(self):
        now = datetime(2026, 10, 5, 9, 0, 30)  # Monday
        schedule = {"paused": False, "items": [{
            "id": "abc", "mode": "weekly", "enabled": True, "days": [0],
            "time": "09:00", "text": "Good morning",
        }], "last_fired": {}}
        due = due_schedules(schedule, now)
        self.assertEqual(len(due), 1)
        mark_schedule_fired(schedule, due[0][0]["id"], due[0][1])
        self.assertEqual(due_schedules(schedule, now), [])

    def test_weekly_schedule_skips_missed_window_and_pause(self):
        now = datetime(2026, 10, 5, 9, 3)
        item = {"id": "abc", "mode": "weekly", "enabled": True,
                "days": [0], "time": "09:00", "text": "Hi"}
        self.assertEqual(due_schedules({"paused": False, "items": [item], "last_fired": {}}, now), [])
        self.assertEqual(due_schedules({"paused": True, "items": [item], "last_fired": {}}, now), [])

    def test_interval_schedule_respects_elapsed_minutes(self):
        now = datetime(2026, 10, 5, 9, 30)
        item = {"id": "abc", "mode": "interval", "enabled": True,
                "interval_minutes": 30, "text": "Hi"}
        before = {"paused": False, "items": [item],
                  "last_fired": {"abc": (now - timedelta(minutes=29)).isoformat()}}
        after = {"paused": False, "items": [item],
                 "last_fired": {"abc": (now - timedelta(minutes=30)).isoformat()}}
        self.assertEqual(due_schedules(before, now), [])
        self.assertEqual(len(due_schedules(after, now)), 1)

    def test_interval_schedule_accepts_timezone_aware_markers(self):
        now = datetime(2026, 10, 5, 9, 30, tzinfo=timezone.utc)
        item = {"id": "abc", "mode": "interval", "enabled": True,
                "interval_minutes": 30, "text": "Hi"}
        schedule = {
            "paused": False,
            "items": [item],
            "last_fired": {"abc": (now - timedelta(minutes=30)).isoformat()},
        }
        due = due_schedules(schedule, now)
        self.assertEqual(len(due), 1)
        mark_schedule_fired(schedule, "abc", due[0][1])
        self.assertIn("abc", schedule["last_fired"])

    def test_schedule_prunes_aware_and_stale_markers_without_type_error(self):
        now = datetime.now(timezone.utc)
        schedule = {"last_fired": {
            "fresh": now.isoformat(),
            "stale": (now - timedelta(days=15)).isoformat(),
        }}
        mark_schedule_fired(schedule, "fresh", now.isoformat())
        self.assertIn("fresh", schedule["last_fired"])
        self.assertNotIn("stale", schedule["last_fired"])


class FriendlyErrorTests(unittest.TestCase):
    def test_maps_window_errors_to_thai_guidance(self):
        from line_status_gui import friendly_task_error
        self.assertIn("Settings > Profile",
                      friendly_task_error("status", "The selected LINE window was closed."))
        self.assertIn("Settings > Profile",
                      friendly_task_error("read-status", "No LINE window is selected yet."))
        self.assertIn("Settings > Profile",
                      friendly_task_error("status", "The selected window is no longer a LINE.exe window."))
        self.assertIn("Status message",
                      friendly_task_error("status", "Could not identify exactly one Status message editor (found 0 of 5)."))
        self.assertIn("Settings > Profile",
                      friendly_task_error("read-status", "Could not read one unambiguous Status message value."))

    def test_maps_save_and_picker_errors(self):
        from line_status_gui import friendly_task_error
        self.assertIn("Save", friendly_task_error("status", "Could not identify exactly one Save button."))
        self.assertIn("file picker", friendly_task_error("image", "Open LINE's native photo file picker first."))
        self.assertIn("read-status", friendly_task_error("read-status", "mystery failure xyz"))

    def test_handles_empty_error(self):
        from line_status_gui import friendly_task_error
        self.assertIn("status", friendly_task_error("status", ""))
        self.assertIn("status", friendly_task_error("status", None))


class WindowsFeatureTests(unittest.TestCase):
    def test_startup_command_quotes_paths_and_config(self):
        command = startup_command(
            executable=r"C:\Program Files\LINE Status Changer\app.exe",
            config_path=r"D:\User Data\line_config.json", frozen=True,
        )
        self.assertIn('"C:\\Program Files\\LINE Status Changer\\app.exe"', command)
        self.assertIn('"D:\\User Data\\line_config.json"', command)

    def test_profile_image_extension_size_and_existence_guards(self):
        with tempfile.TemporaryDirectory() as temp:
            image = Path(temp) / "profile.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\nimage")
            self.assertEqual(validate_profile_image(image), image.resolve())
            bad = Path(temp) / "notes.txt"
            bad.write_text("text", encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_profile_image(bad)


if __name__ == "__main__":
    unittest.main()
