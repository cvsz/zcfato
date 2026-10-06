"""Guarded UI Automation for LINE's profile status editor on Windows."""
from __future__ import annotations

import logging
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
import os

from config_store import validate_status_text


STATUS_LABELS = (
    "status message",
    "ข้อความสถานะ",
    "ステータスメッセージ",
    "상태 메시지",
    "状态消息",
    "狀態消息",
    "狀態訊息",
    "mensaje de estado",
    "message de statut",
    "statusmeldung",
    "mensagem de status",
    "thông điệp trạng thái",
    "pesan status",
)
SAVE_LABELS = {
    "save", "บันทึก", "保存", "儲存", "저장", "enregistrer",
    "guardar", "speichern", "salvar", "lưu", "simpan",
}
OPEN_LABELS = {
    "open", "เปิด", "ouvrir", "öffnen", "abrir", "apri", "열기", "打开", "開啟",
}
NAME_LABELS = {
    "name", "display name", "profile name", "your name", "ชื่อ", "ชื่อโปรไฟล์",
    "名前", "表示名", "프로필 이름", "이름", "姓名", "暱稱", "昵称",
    "nome", "nombre", "nom", "anzeigename", "nome de exibição",
}
PROFILE_CONTEXT_LABELS = {
    "profile", "my profile", "profile settings", "profile information", "edit profile",
    "edit your profile", "edit profile settings", "personal profile",
    "โปรไฟล์", "プロフィール", "프로필", "个人资料", "個人資料", "個人檔案",
}


class AutomationError(RuntimeError):
    """A safe automatic status update could not be completed."""


@dataclass(frozen=True)
class StatusChangeResult:
    entered: bool
    save_clicked: bool
    detail: str = ""
    verified: bool = False


def _compact_name(value):
    return "".join(char.casefold() for char in str(value or "") if char.isalnum())


def is_status_name(value):
    compact = _compact_name(value)
    return any(_compact_name(label) in compact for label in STATUS_LABELS)


def has_status_context(names):
    return any(is_status_name(name) for name in names)


def is_save_name(value):
    return _compact_name(value) in {_compact_name(label) for label in SAVE_LABELS}


def is_open_name(value):
    return _compact_name(value) in {_compact_name(label) for label in OPEN_LABELS}


def is_profile_name_field(value):
    return _compact_name(value) in {_compact_name(label) for label in NAME_LABELS}


def is_profile_name_context(names):
    """Require both a name field label and a nearby profile-section label."""
    normalized = [_compact_name(name) for name in names]
    name_labels = {_compact_name(label) for label in NAME_LABELS}
    has_name = any(value in name_labels for value in normalized)
    profile_labels = {_compact_name(label) for label in PROFILE_CONTEXT_LABELS}
    has_profile = any(value in profile_labels for value in normalized)
    return has_name and has_profile


def accessible_context_names(element_info, max_depth=3, max_siblings=40):
    """Collect focused control, ancestor, and nearby label names for validation."""
    names = []
    current = element_info
    for _ in range(max_depth):
        if current is None:
            break
        try:
            name = current.name
            if name:
                names.append(name)
        except Exception:
            pass
        try:
            parent = current.parent
        except Exception:
            parent = None
        if parent is None:
            break
        try:
            parent_name = parent.name
            if parent_name:
                names.append(parent_name)
        except Exception:
            pass
        # Labels commonly share a group with their editor. Do not search the
        # whole Settings page: another field could otherwise inherit a distant
        # "Status message" label and pass the safety check.
        if _ < 1:
            try:
                for sibling in parent.children()[:max_siblings]:
                    try:
                        sibling_name = sibling.name
                        if sibling_name:
                            names.append(sibling_name)
                    except Exception:
                        continue
            except Exception:
                pass
        current = parent
    return names


def process_for_window(hwnd):
    """Return (pid, executable path) only when hwnd belongs to LINE.exe."""
    if not hwnd:
        return None
    import win32api
    import win32con
    import win32gui
    import win32process

    if not win32gui.IsWindow(hwnd):
        return None
    _thread_id, pid = win32process.GetWindowThreadProcessId(hwnd)
    if not pid:
        return None
    access = win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ
    try:
        handle = win32api.OpenProcess(access, False, pid)
        try:
            executable = win32process.GetModuleFileNameEx(handle, 0)
        finally:
            win32api.CloseHandle(handle)
    except Exception:
        return None
    if Path(executable).name.casefold() != "line.exe":
        return None
    return pid, executable


def _find_save_button(target):
    matches = []
    for button in target.descendants(control_type="Button"):
        try:
            candidates = (button.element_info.name, button.window_text())
            if any(is_save_name(value) for value in candidates):
                matches.append(button)
        except Exception:
            continue
    if len(matches) != 1:
        raise AutomationError(
            "Could not identify exactly one Save button in this LINE window. "
            "No text was changed; use Copy and update the profile manually."
        )
    return matches[0]


def _focused_profile_editor(hwnd, pid, field_match, field_label, activate=True,
                            activation_delay=0.3):
    """Return a UIA editor only after validating the active LINE window and field label."""
    import win32con
    import win32gui
    from pywinauto.controls.uiawrapper import UIAWrapper
    from pywinauto.uia_defines import IUIA
    from pywinauto.uia_element_info import UIAElementInfo

    process = process_for_window(hwnd)
    if not process or process[0] != pid:
        raise AutomationError("The selected LINE window changed or closed.")
    if activate:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(activation_delay)
        if win32gui.GetForegroundWindow() != hwnd:
            raise AutomationError("The verified LINE window is not foreground; no profile field was changed.")
        raw = IUIA().get_focused_element()
        if raw is None:
            raise AutomationError("LINE did not expose the focused control to Windows UI Automation.")
        editor = UIAWrapper(UIAElementInfo(raw))
    else:
        from pywinauto import Desktop
        target = Desktop(backend="uia").window(handle=hwnd)
        matches = []
        for ctrl in target.descendants(control_type="Edit"):
            try:
                if any(field_match(name) for name in accessible_context_names(ctrl.element_info)):
                    matches.append(ctrl)
            except Exception:
                continue
        if len(matches) != 1:
            raise AutomationError(f"Could not identify exactly one {field_label} editor. found {len(matches)}")
        editor = matches[0]
    info = editor.element_info
    if info.control_type != "Edit":
        raise AutomationError(f"The control is not LINE's {field_label} editor.")
    try:
        focus_pid = info.process_id
        top_level = editor.top_level_parent().element_info.handle
    except Exception as exc:
        raise AutomationError("Could not verify which LINE control has focus.") from exc
    if focus_pid != pid or top_level != hwnd:
        raise AutomationError("The field is not in the selected LINE window.")
    if activate and not any(field_match(name) for name in accessible_context_names(info)):
        raise AutomationError(
            f"Windows could not confirm this is LINE's {field_label} field. No text was changed."
        )
    try:
        if not editor.is_editable():
            raise AutomationError(f"LINE's {field_label} field is read-only.")
    except AutomationError:
        raise
    except Exception as exc:
        raise AutomationError(f"Could not verify LINE's {field_label} field is editable.") from exc
    return editor


def _verify_profile_value(hwnd, pid, expected, timeout=5.0):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            current = read_profile_status(hwnd, pid)
            if current == expected:
                return True, ""
        except Exception as exc:
            logging.debug("LINE status verification is still pending: %s", exc)
            last_error = exc
        time.sleep(0.3)
    if last_error:
        return False, str(last_error)
    return False, "LINE did not expose the saved status text for verification."


def set_profile_status(hwnd, pid, text, activation_delay=0.3, activate=False):
    """Set and save only when UIA proves focus is LINE's Status message editor."""
    validate_status_text(text)
    from pywinauto import Desktop
    editor = _focused_profile_editor(
        hwnd, pid, is_status_name, "Status message", activate, activation_delay
    )
    target = Desktop(backend="uia").window(handle=hwnd)
    save_button = _find_save_button(target)
    try:
        editor.set_edit_text(text)
        if editor.get_value() != text:
            raise AutomationError(
                "LINE did not accept the full status text. Save was not clicked; review the field."
            )
    except AutomationError:
        raise
    except Exception as exc:
        raise AutomationError(
            "LINE's Status message field could not be updated through UI Automation. "
            "No clipboard contents were changed. Use Copy and paste manually."
        ) from exc

    try:
        if not save_button.is_enabled() or not save_button.is_visible():
            return StatusChangeResult(
                entered=True, save_clicked=False,
                detail="Text entered, but LINE's Save button is unavailable; click Save manually.",
            )
        save_button.invoke()
    except Exception as exc:
        return StatusChangeResult(
            entered=True, save_clicked=False,
            detail=f"Text entered, but Save could not be clicked; click Save manually ({exc}).",
        )
    # Separate the click result from read-back verification. A UIA failure after
    # invoke() must not be reported as though Save was never clicked.
    try:
        verified, detail = _verify_profile_value(hwnd, pid, text)
    except Exception as exc:
        logging.exception("Could not verify the saved LINE status")
        verified, detail = False, str(exc)
    return StatusChangeResult(entered=True, save_clicked=True, detail=detail,
                              verified=verified)


def set_profile_display_name(hwnd, pid, text, activation_delay=0.3, activate=False):
    """Change LINE's profile name only when its specifically labeled editor is focused."""
    if not isinstance(text, str) or not text.strip() or len(text) > 100:
        raise AutomationError("Display name must contain 1–100 characters.")
    if any(unicodedata.category(char) == "Cc" for char in text):
        raise AutomationError("Display name must be a single line without control characters.")
    try:
        text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise AutomationError("Display name contains invalid Unicode.") from exc
    from pywinauto import Desktop

    editor = _focused_profile_editor(
        hwnd, pid, is_profile_name_context, "profile name", activate, activation_delay
    )
    target = Desktop(backend="uia").window(handle=hwnd)
    save_button = _find_save_button(target)
    try:
        editor.set_edit_text(text)
        if editor.get_value() != text:
            raise AutomationError("LINE did not accept the full display name; Save was not clicked.")
        if not save_button.is_enabled() or not save_button.is_visible():
            return StatusChangeResult(True, False, "Text entered; click Save manually.")
        save_button.invoke()
        return StatusChangeResult(True, True, "Save clicked; verify your LINE profile name.")
    except AutomationError:
        raise
    except Exception as exc:
        raise AutomationError("Could not update the confirmed profile name field.") from exc


def _element_value(element):
    values = []
    try:
        value = element.get_value()
        if value:
            values.append(value)
    except Exception:
        pass
    try:
        value = element.window_text()
        if value:
            values.append(value)
    except Exception:
        pass
    try:
        value = element.element_info.name
        if value:
            values.append(value)
    except Exception:
        pass
    # Remove duplicate exposure of the same UIA value while retaining exact text.
    return list(dict.fromkeys(str(value) for value in values if str(value).strip()))


def read_profile_status(hwnd, pid):
    """Read one unambiguous status value beside its UIA label in the LINE window."""
    process = process_for_window(hwnd)
    if not process or process[0] != pid:
        raise AutomationError("The selected LINE window changed or closed.")
    from pywinauto import Desktop

    target = Desktop(backend="uia").window(handle=hwnd)
    groups = []
    try:
        controls = target.descendants()
    except Exception as exc:
        raise AutomationError("Could not inspect LINE profile controls.") from exc
    for control in controls:
        try:
            label = control.element_info.name
            if not is_status_name(label):
                continue
            parent = control.element_info.parent
            if parent is None:
                continue
            siblings = parent.children()
            candidates = []
            for sibling in siblings:
                try:
                    if sibling == control:
                        continue
                    kind = sibling.control_type()
                    if kind not in ("Edit", "Text", "Document"):
                        continue
                    vals = _element_value(sibling)
                    if vals:
                        # Value controls are preferred over a duplicate accessible name.
                        candidates.append((0 if kind == "Edit" else 1, vals[0]))
                except Exception:
                    continue
            if candidates:
                candidates.sort(key=lambda item: item[0])
                best_kind = candidates[0][0]
                best = list(dict.fromkeys(value for kind, value in candidates if kind == best_kind))
                groups.extend(best)
        except Exception:
            continue
    values = list(dict.fromkeys(value for value in groups if value))
    if len(values) != 1:
        raise AutomationError(
            "Could not read one unambiguous Status message value from this LINE profile view."
        )
    return values[0]


def select_image_in_open_dialog(hwnd, pid, image_path):
    """Choose a file only in one native Open dialog owned by the verified LINE process."""
    process = process_for_window(hwnd)
    if not process or process[0] != pid:
        raise AutomationError("The selected LINE window changed or closed.")
    path = Path(image_path).resolve(strict=True)
    if not path.is_file():
        raise AutomationError("The selected image file no longer exists.")
    from pywinauto import Desktop

    matches = []
    for window in Desktop(backend="uia").windows():
        try:
            info = window.element_info
            if info.process_id != pid:
                continue
            buttons = [button for button in window.descendants(control_type="Button")
                       if is_open_name(button.element_info.name)]
            edits = window.descendants(control_type="Edit")
            filename_edits = [edit for edit in edits
                              if str(getattr(edit.element_info, "automation_id", "")) == "1148"
                              or "file name" in (edit.element_info.name or "").casefold()
                              or "ชื่อไฟล์" in (edit.element_info.name or "")]
            if (info.handle != hwnd and (info.class_name == "#32770" or buttons)
                    and len(buttons) == 1 and len(filename_edits) == 1):
                matches.append((window, filename_edits[0], buttons[0]))
        except Exception:
            continue
    if len(matches) != 1:
        raise AutomationError(
            "Open LINE's native photo/cover file picker first. The helper could not verify "
            "exactly one LINE-owned file picker, so it did not select a file."
        )
    dialog, filename_edit, open_button = matches[0]
    try:
        if not open_button.is_enabled() or not open_button.is_visible():
            raise AutomationError("LINE's Open button is unavailable.")
        filename_edit.set_edit_text(str(path))
        entered = _element_value(filename_edit)
        if not any(os.path.normcase(value) == os.path.normcase(str(path)) for value in entered):
            raise AutomationError("LINE's file picker did not accept the selected path.")
        open_button.invoke()
        return True
    except AutomationError:
        raise
    except Exception as exc:
        raise AutomationError("Could not select the image in LINE's verified file picker.") from exc
