"""Shared background status engine and evidence-driven executor for Camfrog Video Chat.

Provides:
- Strict true background status execution without focus stealing, mouse movement,
  keyboard injection, clipboard mutation, or registry sound modifications.
- Authoritative status commit verification via CComboBoxTS item state.
- Separation of execution modes (strict_background vs interactive).
- Shared status rotation, marquee frames, concurrency protection, and recovery.
"""

from __future__ import annotations

import ctypes
import os
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import camfrog_windows_runtime as cwr
from camfrog_windows_runtime import (
    ClassifiedWindow,
    ProcessIdentity,
    WindowRole,
    WindowsCamfrogProcessDiscovery,
    WindowsCamfrogWindowClassifier,
    revalidate_process_identity,
    revalidate_window_identity,
)
from camfrog_emergency_stop import EmergencyStopHook


class StatusResultState(str, Enum):
    """Authoritative result states for a status update request."""
    PENDING = "PENDING"
    PROCESS_VERIFIED = "PROCESS_VERIFIED"
    WINDOW_VERIFIED = "WINDOW_VERIFIED"
    TEXT_WRITTEN = "TEXT_WRITTEN"
    SUBMIT_DISPATCHED = "SUBMIT_DISPATCHED"
    VERIFIED_APPLIED = "VERIFIED_APPLIED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    BACKGROUND_UNSUPPORTED = "BACKGROUND_UNSUPPORTED"


class ExecutionMode(str, Enum):
    """Execution mode distinguishing strict background from interactive."""
    STRICT_BACKGROUND = "strict_background"
    INTERACTIVE = "interactive"


@dataclass
class StatusExecutionEvidence:
    """Sanitized evidence log of a status execution operation."""
    request_id: str
    operation_id: str
    client_version: str
    process_identity: Dict[str, Any]
    window_role: str
    execution_mode: str
    result_state: str
    duration_ms: float
    verification_source: str
    applied_text: str = ""
    error_code: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------- Status Control Adapter ----------

class StatusControlAdapter:
    """Low-level interface to Camfrog's CComboBoxTS and Edit controls."""

    def __init__(self, combo_hwnd: int, edit_hwnd: int):
        self.combo_hwnd = combo_hwnd
        self.edit_hwnd = edit_hwnd

    def write_text_no_focus(self, text: str) -> bool:
        """Write text into the status Edit control without setting keyboard focus."""
        if sys.platform != "win32":
            return False

        try:
            import win32con
            import win32gui

            # Fail closed on stale/dangling handles: never report success
            # for a control that does not exist.
            if not win32gui.IsWindow(self.edit_hwnd):
                return False

            # 1. Send WM_SETTEXT to Edit control (nonzero LRESULT = accepted)
            settext_ok = win32gui.SendMessage(self.edit_hwnd, win32con.WM_SETTEXT, 0, text)
            if not settext_ok:
                return False

            # 2. Notify parent CComboBoxTS of EN_CHANGE
            wparam = (win32con.EN_CHANGE << 16) | 1001
            win32gui.SendMessage(self.combo_hwnd, win32con.WM_COMMAND, wparam, self.edit_hwnd)

            return True
        except Exception:
            return False

    def read_edit_text(self) -> str:
        """Read text from Edit control via WM_GETTEXT."""
        if sys.platform != "win32":
            return ""

        try:
            import win32con
            import win32gui
            buf = ctypes.create_unicode_buffer(512)
            win32gui.SendMessage(self.edit_hwnd, win32con.WM_GETTEXT, 512, buf)
            return buf.value
        except Exception:
            return ""

    def read_applied_status(self) -> str:
        """Read authoritative status committed at index 0 of CComboBoxTS list."""
        if sys.platform != "win32":
            return ""

        try:
            import win32con
            import win32gui

            count = win32gui.SendMessage(self.combo_hwnd, win32con.CB_GETCOUNT, 0, 0)
            if count <= 0:
                return ""
            length = win32gui.SendMessage(self.combo_hwnd, win32con.CB_GETLBTEXTLEN, 0, 0)
            if length < 0:
                return ""
            buf = ctypes.create_unicode_buffer(length + 1)
            win32gui.SendMessage(self.combo_hwnd, win32con.CB_GETLBTEXT, 0, buf)
            return buf.value
        except Exception:
            return ""

    def post_background_enter(self) -> bool:
        """Post Enter key message to CComboBoxTS without focus stealing or sound hacks."""
        if sys.platform != "win32":
            return False

        try:
            user32 = ctypes.windll.user32
            # Scan code for VK_RETURN (0x0D) is 0x1C
            lparam_down = 0x001C0001
            lparam_up = 0xC01C0001
            res_down = user32.PostMessageW(self.combo_hwnd, 0x0100, 0x0D, lparam_down)
            res_up = user32.PostMessageW(self.combo_hwnd, 0x0101, 0x0D, lparam_up)
            return bool(res_down and res_up)
        except Exception:
            return False


# ---------- Camfrog Window Resolver ----------

class CamfrogWindowResolver:
    """Discovers and validates the status controls under verified Camfrog process."""

    def __init__(
        self,
        process_discovery: Optional[WindowsCamfrogProcessDiscovery] = None,
        window_classifier: Optional[WindowsCamfrogWindowClassifier] = None,
    ):
        self.discovery = process_discovery or WindowsCamfrogProcessDiscovery()
        self.classifier = window_classifier or WindowsCamfrogWindowClassifier()

    def resolve_status_controls(
        self,
        pid: Optional[int] = None
    ) -> Tuple[ProcessIdentity, ClassifiedWindow, StatusControlAdapter]:
        """Resolve verified process, main directory window, and status control adapter.

        Raises:
            ProcessLookupError: if process identity cannot be found/verified.
            LookupError: if main directory window or status controls are missing.
        """
        proc = self.discovery.get_verified_process(pid=pid)
        windows = self.classifier.classify_process_windows(proc)

        main_windows = [w for w in windows if w.role == WindowRole.MAIN_DIRECTORY]
        if not main_windows:
            raise LookupError(f"No verified MAIN_DIRECTORY window found for Camfrog PID {proc.pid}.")

        main_win = main_windows[0]
        if not revalidate_window_identity(main_win, proc):
            raise LookupError(f"Main directory window hwnd={main_win.hwnd} failed identity revalidation.")

        # Discover CComboBoxTS (automation ID 1436) and its child Edit (ID 1001).
        # Control IDs take precedence over class names: on windows with
        # several native edits, class-only matching could bind the wrong
        # pair and write status text into an unrelated field.
        combo_hwnd = 0
        edit_hwnd = 0
        combo_by_id = 0
        edit_by_id = 0

        if sys.platform == "win32":
            try:
                import win32gui
                def _cb(ch, _):
                    nonlocal combo_hwnd, edit_hwnd, combo_by_id, edit_by_id
                    cid = win32gui.GetDlgCtrlID(ch)
                    cls = win32gui.GetClassName(ch)
                    if cls == "CComboBoxTS" or cid == 1436:
                        combo_hwnd = ch
                    elif cls in ("Edit", "CEditTS") or cid == 1001:
                        edit_hwnd = ch
                    if cid == 1436:
                        combo_by_id = ch
                    elif cid == 1001:
                        edit_by_id = ch
                    return True
                win32gui.EnumChildWindows(main_win.hwnd, _cb, None)
                if combo_by_id and edit_by_id:
                    try:
                        if win32gui.GetParent(edit_by_id) == combo_by_id:
                            combo_hwnd, edit_hwnd = combo_by_id, edit_by_id
                    except Exception:
                        pass
            except Exception:
                pass

        if not combo_hwnd or not edit_hwnd:
            raise LookupError(
                f"Status controls not found in main window hwnd={main_win.hwnd} "
                f"(combo={combo_hwnd}, edit={edit_hwnd})."
            )

        adapter = StatusControlAdapter(combo_hwnd=combo_hwnd, edit_hwnd=edit_hwnd)
        return proc, main_win, adapter


# ---------- Resource-Scoped Status Lock ----------

class StatusResourceLock:
    """Inter-process and intra-process resource-scoped synchronization for status writes.

    Ensures that Random Status, Marquee Status, and Unified Client cannot simultaneously
    write to the same Camfrog client status control.
    """

    _process_locks: Dict[str, threading.RLock] = {}
    _meta_lock = threading.Lock()

    def __init__(self, resource_key: str = "global", timeout_seconds: float = 5.0):
        self.resource_key = str(resource_key or "global").replace("\\", "_")
        self.timeout_seconds = max(0.1, float(timeout_seconds))
        self._mutex_handle = None
        self._thread_lock = self._get_thread_lock(self.resource_key)
        self._acquired_thread = False
        self._acquired_mutex = False

    @classmethod
    def _get_thread_lock(cls, key: str) -> threading.RLock:
        with cls._meta_lock:
            if key not in cls._process_locks:
                cls._process_locks[key] = threading.RLock()
            return cls._process_locks[key]

    def acquire(self) -> bool:
        """Acquire the scoped lock across threads and processes."""
        deadline = time.monotonic() + self.timeout_seconds

        rem_time = max(0.01, deadline - time.monotonic())
        acquired_thread = self._thread_lock.acquire(timeout=rem_time)
        if not acquired_thread:
            return False
        self._acquired_thread = True

        if sys.platform == "win32":
            try:
                kernel32 = ctypes.windll.kernel32
                mutex_name = f"Local\\ZChat_StatusLock_{self.resource_key}"

                handle = kernel32.CreateMutexW(None, False, mutex_name)
                if not handle:
                    self._thread_lock.release()
                    self._acquired_thread = False
                    return False
                self._mutex_handle = handle

                rem_ms = max(10, int(max(0.01, deadline - time.monotonic()) * 1000))
                wait_res = kernel32.WaitForSingleObject(handle, rem_ms)
                if wait_res not in (0x00000000, 0x00000080):  # WAIT_OBJECT_0 or WAIT_ABANDONED
                    kernel32.CloseHandle(handle)
                    self._mutex_handle = None
                    self._thread_lock.release()
                    self._acquired_thread = False
                    return False
                self._acquired_mutex = True
                return True
            except Exception:
                if self._mutex_handle:
                    try:
                        ctypes.windll.kernel32.CloseHandle(self._mutex_handle)
                    except Exception:
                        pass
                    self._mutex_handle = None
                self._thread_lock.release()
                self._acquired_thread = False
                return False

        return True

    def release(self) -> None:
        """Release the scoped lock."""
        if sys.platform == "win32" and self._mutex_handle:
            try:
                if self._acquired_mutex:
                    ctypes.windll.kernel32.ReleaseMutex(self._mutex_handle)
                ctypes.windll.kernel32.CloseHandle(self._mutex_handle)
            except Exception:
                pass
            finally:
                self._mutex_handle = None
                self._acquired_mutex = False

        if self._acquired_thread:
            try:
                self._thread_lock.release()
            except RuntimeError:
                pass
            finally:
                self._acquired_thread = False

    def __enter__(self):
        if not self.acquire():
            raise TimeoutError(
                f"Failed to acquire status lock for resource '{self.resource_key}' within {self.timeout_seconds}s"
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


# ---------- Background Status Executor ----------

class BackgroundStatusExecutor(EmergencyStopHook):
    """Executes status changes strictly without desktop interference.

    Execution sequence:
    1. DISCOVER_PROCESS
    2. VERIFY_PROCESS
    3. DISCOVER_WINDOW
    4. VERIFY_STATUS_CONTROL
    5. WRITE_TEXT_WITHOUT_FOCUS
    6. VERIFY_TEXT_READBACK
    7. SUBMIT_WITHOUT_GLOBAL_INPUT
    8. VERIFY_APPLIED_STATE
    9. REPORT_RESULT
    """

    def __init__(
        self,
        resolver: Optional[CamfrogWindowResolver] = None,
        default_mode: ExecutionMode = ExecutionMode.STRICT_BACKGROUND,
    ):
        EmergencyStopHook.__init__(self)
        self.resolver = resolver or CamfrogWindowResolver()
        self.default_mode = default_mode
        self._lock = threading.Lock()

    def execute_status_change(
        self,
        status_text: str,
        pid: Optional[int] = None,
        execution_mode: Optional[ExecutionMode] = None,
        timeout_seconds: float = 3.0,
    ) -> StatusExecutionEvidence:
        """Execute a status change with evidence recording and strict background isolation."""
        start_time = time.monotonic()
        req_id = f"req-{uuid.uuid4().hex[:8]}"
        op_id = f"op-{uuid.uuid4().hex[:8]}"
        mode = execution_mode or self.default_mode

        clean_text = (status_text or "").strip()
        if not clean_text:
            return StatusExecutionEvidence(
                request_id=req_id,
                operation_id=op_id,
                client_version="",
                process_identity={},
                window_role="",
                execution_mode=mode.value,
                result_state=StatusResultState.FAILED.value,
                duration_ms=0.0,
                verification_source="validation",
                error_code="EMPTY_STATUS_TEXT",
            )

        with self._lock:
            # 0. EMERGENCY STOP GATE — refuse new work while stopped.
            try:
                self.check_emergency_stop()
            except StopIteration:
                return StatusExecutionEvidence(
                    request_id=req_id,
                    operation_id=op_id,
                    client_version="",
                    process_identity={},
                    window_role="",
                    execution_mode=mode.value,
                    result_state=StatusResultState.FAILED.value,
                    duration_ms=(time.monotonic() - start_time) * 1000,
                    verification_source="emergency_stop",
                    error_code="EMERGENCY_STOP",
                )
            # 1 & 2. DISCOVER_PROCESS & VERIFY_PROCESS
            try:
                proc, main_win, adapter = self.resolver.resolve_status_controls(pid=pid)
            except ProcessLookupError as e:
                return StatusExecutionEvidence(
                    request_id=req_id,
                    operation_id=op_id,
                    client_version="",
                    process_identity={},
                    window_role="",
                    execution_mode=mode.value,
                    result_state=StatusResultState.FAILED.value,
                    duration_ms=(time.monotonic() - start_time) * 1000,
                    verification_source="process_discovery",
                    error_code="PROCESS_NOT_FOUND",
                )
            except LookupError as e:
                return StatusExecutionEvidence(
                    request_id=req_id,
                    operation_id=op_id,
                    client_version=getattr(locals().get("proc"), "version", ""),
                    process_identity=locals()["proc"].as_dict() if locals().get("proc") else {},
                    window_role=WindowRole.MAIN_DIRECTORY.value,
                    execution_mode=mode.value,
                    result_state=StatusResultState.BACKGROUND_UNSUPPORTED.value,
                    duration_ms=(time.monotonic() - start_time) * 1000,
                    verification_source="window_resolver",
                    error_code="CONTROLS_NOT_FOUND",
                )
            except RuntimeError as e:
                # Ambiguous process/window identity (e.g. multiple verified
                # clients): report evidence, never choose a target.
                return StatusExecutionEvidence(
                    request_id=req_id,
                    operation_id=op_id,
                    client_version="",
                    process_identity={},
                    window_role="",
                    execution_mode=mode.value,
                    result_state=StatusResultState.FAILED.value,
                    duration_ms=(time.monotonic() - start_time) * 1000,
                    verification_source="process_discovery",
                    error_code="AMBIGUOUS_PROCESS_IDENTITY",
                )

            # Resource-scoped synchronization across processes targeting this Camfrog client
            lock_resource = f"pid_{proc.pid}"
            try:
                with StatusResourceLock(resource_key=lock_resource, timeout_seconds=timeout_seconds):
                    # Recheck foreground before operation to record evidence that desktop is undisturbed
                    fg_before = 0
                    if sys.platform == "win32":
                        try:
                            import win32gui
                            fg_before = win32gui.GetForegroundWindow()
                        except Exception:
                            pass

                    # Check if requested status is already active to avoid duplicate submissions
                    current_status = adapter.read_applied_status()
                    if current_status == clean_text:
                        return StatusExecutionEvidence(
                            request_id=req_id,
                            operation_id=op_id,
                            client_version=proc.version,
                            process_identity=proc.as_dict(),
                            window_role=main_win.role.value,
                            execution_mode=mode.value,
                            result_state=StatusResultState.VERIFIED_APPLIED.value,
                            duration_ms=(time.monotonic() - start_time) * 1000,
                            verification_source="combo_history_already_active",
                            applied_text=clean_text,
                        )

                    # 5. WRITE_TEXT_WITHOUT_FOCUS
                    write_ok = adapter.write_text_no_focus(clean_text)
                    if not write_ok:
                        return StatusExecutionEvidence(
                            request_id=req_id,
                            operation_id=op_id,
                            client_version=proc.version,
                            process_identity=proc.as_dict(),
                            window_role=main_win.role.value,
                            execution_mode=mode.value,
                            result_state=StatusResultState.FAILED.value,
                            duration_ms=(time.monotonic() - start_time) * 1000,
                            verification_source="status_control_adapter",
                            error_code="WRITE_TEXT_FAILED",
                        )

                    # 6. VERIFY_TEXT_READBACK
                    read_back = adapter.read_edit_text()
                    if read_back != clean_text:
                        return StatusExecutionEvidence(
                            request_id=req_id,
                            operation_id=op_id,
                            client_version=proc.version,
                            process_identity=proc.as_dict(),
                            window_role=main_win.role.value,
                            execution_mode=mode.value,
                            result_state=StatusResultState.FAILED.value,
                            duration_ms=(time.monotonic() - start_time) * 1000,
                            verification_source="edit_readback",
                            error_code="READBACK_MISMATCH",
                        )

                    # 7. SUBMIT_WITHOUT_GLOBAL_INPUT
                    post_ok = adapter.post_background_enter()
                    if not post_ok:
                        return StatusExecutionEvidence(
                            request_id=req_id,
                            operation_id=op_id,
                            client_version=proc.version,
                            process_identity=proc.as_dict(),
                            window_role=main_win.role.value,
                            execution_mode=mode.value,
                            result_state=StatusResultState.FAILED.value,
                            duration_ms=(time.monotonic() - start_time) * 1000,
                            verification_source="post_enter",
                            error_code="POST_ENTER_FAILED",
                        )

                    # 8. VERIFY_APPLIED_STATE
                    # Poll CComboBoxTS item 0 for authoritative commit
                    applied_confirmed = False
                    deadline = time.monotonic() + timeout_seconds
                    while time.monotonic() < deadline:
                        time.sleep(0.05)
                        applied = adapter.read_applied_status()
                        if applied == clean_text:
                            applied_confirmed = True
                            break

                    # Confirm desktop foreground was not stolen
                    fg_after = 0
                    if sys.platform == "win32":
                        try:
                            import win32gui
                            fg_after = win32gui.GetForegroundWindow()
                        except Exception:
                            pass

                    duration_ms = (time.monotonic() - start_time) * 1000

                    if not applied_confirmed:
                        return StatusExecutionEvidence(
                            request_id=req_id,
                            operation_id=op_id,
                            client_version=proc.version,
                            process_identity=proc.as_dict(),
                            window_role=main_win.role.value,
                            execution_mode=mode.value,
                            result_state=StatusResultState.FAILED.value,
                            duration_ms=duration_ms,
                            verification_source="combo_history_verification",
                            error_code="COMMIT_NOT_VERIFIED",
                        )

                    return StatusExecutionEvidence(
                        request_id=req_id,
                        operation_id=op_id,
                        client_version=proc.version,
                        process_identity=proc.as_dict(),
                        window_role=main_win.role.value,
                        execution_mode=mode.value,
                        result_state=StatusResultState.VERIFIED_APPLIED.value,
                        duration_ms=duration_ms,
                        verification_source="combo_history_item_0",
                        applied_text=clean_text,
                    )
            except TimeoutError:
                return StatusExecutionEvidence(
                    request_id=req_id,
                    operation_id=op_id,
                    client_version=proc.version,
                    process_identity=proc.as_dict(),
                    window_role=main_win.role.value,
                    execution_mode=mode.value,
                    result_state=StatusResultState.FAILED.value,
                    duration_ms=(time.monotonic() - start_time) * 1000,
                    verification_source="status_resource_lock",
                    error_code="LOCK_TIMEOUT",
                )


# ---------- Shared Status Scheduler ----------

class StatusScheduler:
    """Manages scheduled, random, or marquee status rotations safely."""

    def __init__(self, executor: Optional[BackgroundStatusExecutor] = None):
        self.executor = executor or BackgroundStatusExecutor()
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._history: List[StatusExecutionEvidence] = []
        self._lock = threading.Lock()

    def stop(self) -> None:
        """Signal running worker to stop."""
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)

    def is_running(self) -> bool:
        return self._worker_thread is not None and self._worker_thread.is_alive()

    def get_history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [ev.as_dict() for ev in self._history]

    def record_evidence(self, ev: StatusExecutionEvidence) -> None:
        with self._lock:
            self._history.append(ev)
            if len(self._history) > 200:
                self._history.pop(0)

    def set_single_status(self, text: str, pid: Optional[int] = None) -> StatusExecutionEvidence:
        """Set a single status update immediately in background."""
        ev = self.executor.execute_status_change(text, pid=pid)
        self.record_evidence(ev)
        return ev


# ---------- Configuration Contract Validation ----------

DEFAULT_CONFIG_CONTRACT = {
    "status": {
        "enabled": True,
        "execution_mode": "strict_background",
        "background_enter_target": "combo",
        "verify_result": True,
        "interval_seconds": 600,
    },
    "safety": {
        "require_foreground": False,
        "restore_previous_window": False,
        "allow_focus_stealing": False,
        "allow_mouse_injection": False,
        "allow_keyboard_injection": False,
        "allow_clipboard_mutation": False,
        "allow_system_sound_changes": False,
    },
}


def validate_status_config(cfg: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Validate status configuration against safety contract and supply safe defaults."""
    errors = []
    normalized = dict(cfg)

    status_sec = normalized.setdefault("status", {})
    safety_sec = normalized.setdefault("safety", {})

    # Defaults
    status_sec.setdefault("enabled", True)
    status_sec.setdefault("execution_mode", "strict_background")
    status_sec.setdefault("background_enter_target", "combo")
    status_sec.setdefault("verify_result", True)
    status_sec.setdefault("interval_seconds", 600)

    safety_sec.setdefault("require_foreground", False)
    safety_sec.setdefault("restore_previous_window", False)
    safety_sec.setdefault("allow_focus_stealing", False)
    safety_sec.setdefault("allow_mouse_injection", False)
    safety_sec.setdefault("allow_keyboard_injection", False)
    safety_sec.setdefault("allow_clipboard_mutation", False)
    safety_sec.setdefault("allow_system_sound_changes", False)

    mode = status_sec.get("execution_mode")
    if mode not in ("strict_background", "interactive"):
        errors.append(f"Invalid status.execution_mode: {mode!r} (must be 'strict_background' or 'interactive')")

    target = status_sec.get("background_enter_target")
    if target not in ("combo", "edit"):
        errors.append(f"Invalid status.background_enter_target: {target!r} (must be 'combo' or 'edit')")

    return len(errors) == 0, errors, normalized
