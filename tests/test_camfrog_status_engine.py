"""Unit tests for camfrog_status_engine.py.

Verifies:
- Resource-scoped synchronization (StatusResourceLock)
- Strict background execution without focus stealing, mouse/keyboard injection, or clipboard mutations
- Authoritative status commit verification via CComboBoxTS item state
- Fail-closed handling for missing process, missing window controls, write failures, and lock timeouts
- Non-claim rule: text write or message dispatch alone does NOT prove Camfrog applied the status
- Configuration contract validation and safe defaults
"""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import camfrog_status_engine as cse
from camfrog_status_engine import (
    BackgroundStatusExecutor,
    ExecutionMode,
    StatusControlAdapter,
    StatusExecutionEvidence,
    StatusResourceLock,
    StatusResultState,
    StatusScheduler,
    validate_status_config,
)
from camfrog_windows_runtime import (
    ClassifiedWindow,
    ProcessIdentity,
    WindowRole,
)


# ---------- StatusResourceLock Tests ----------

def test_status_resource_lock_basic_acquire_and_release():
    lock = StatusResourceLock(resource_key="test_res_1", timeout_seconds=1.0)
    assert lock.acquire() is True
    lock.release()


def test_status_resource_lock_context_manager():
    with StatusResourceLock(resource_key="test_res_2", timeout_seconds=1.0) as lock:
        assert lock._acquired_thread is True


def test_status_resource_lock_blocks_concurrent_threads():
    barrier = threading.Barrier(2)
    acquired_second = []

    def holder():
        with StatusResourceLock(resource_key="test_res_3", timeout_seconds=2.0):
            barrier.wait()
            time.sleep(0.3)

    def contender():
        barrier.wait()
        start = time.monotonic()
        try:
            with StatusResourceLock(resource_key="test_res_3", timeout_seconds=0.1):
                acquired_second.append(True)
        except TimeoutError:
            acquired_second.append(False)

    t1 = threading.Thread(target=holder)
    t2 = threading.Thread(target=contender)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert acquired_second == [False]


# ---------- StatusControlAdapter Non-Windows Fallback Tests ----------

def test_status_control_adapter_linux_safety():
    adapter = StatusControlAdapter(combo_hwnd=123, edit_hwnd=456)
    # On non-Windows platforms, low-level Win32 calls safely return empty/False
    assert adapter.write_text_no_focus("Hello") is False
    assert adapter.read_edit_text() == ""
    assert adapter.read_applied_status() == ""
    assert adapter.post_background_enter() is False


# ---------- BackgroundStatusExecutor Tests ----------

def _make_mock_resolver(current_applied="Initial Status", target_readback="New Status"):
    proc = ProcessIdentity(
        pid=5555,
        create_time=100.0,
        exe_path="C:\\Camfrog\\Camfrog Video Chat.exe",
        publisher="Camfrog LLC",
        signature_valid=True,
        version="8.5.0.51219",
        is_agent_launched=False,
    )
    main_win = ClassifiedWindow(
        hwnd=9999,
        role=WindowRole.MAIN_DIRECTORY,
        title="zdevz (Online)",
        pid=5555,
        is_visible=True,
        signatures=["directory_tree", "status_combo"],
    )

    mock_adapter = MagicMock(spec=StatusControlAdapter)
    mock_adapter.combo_hwnd = 8881
    mock_adapter.edit_hwnd = 8882
    mock_adapter.write_text_no_focus.return_value = True
    mock_adapter.read_edit_text.return_value = target_readback
    mock_adapter.post_background_enter.return_value = True
    mock_adapter.read_applied_status.return_value = current_applied

    resolver = MagicMock()
    resolver.resolve_status_controls.return_value = (proc, main_win, mock_adapter)
    return resolver, proc, main_win, mock_adapter


def test_executor_successful_status_application():
    new_status = "Available for chat"
    resolver, proc, main_win, mock_adapter = _make_mock_resolver(
        current_applied="Old Status",
        target_readback=new_status,
    )
    # After enter, read_applied_status returns the new status
    mock_adapter.read_applied_status.side_effect = ["Old Status", new_status]

    executor = BackgroundStatusExecutor(resolver=resolver)
    evidence = executor.execute_status_change(new_status, pid=5555)

    assert evidence.result_state == StatusResultState.VERIFIED_APPLIED.value
    assert evidence.verification_source == "combo_history_item_0"
    assert evidence.applied_text == new_status
    assert evidence.client_version == "8.5.0.51219"
    assert evidence.process_identity["pid"] == 5555
    assert evidence.error_code is None
    assert mock_adapter.write_text_no_focus.called
    assert mock_adapter.post_background_enter.called


def test_executor_duplicate_status_fast_path():
    same_status = "Currently In Meeting"
    resolver, proc, main_win, mock_adapter = _make_mock_resolver(
        current_applied=same_status,
        target_readback=same_status,
    )

    executor = BackgroundStatusExecutor(resolver=resolver)
    evidence = executor.execute_status_change(same_status, pid=5555)

    assert evidence.result_state == StatusResultState.VERIFIED_APPLIED.value
    assert evidence.verification_source == "combo_history_already_active"
    assert evidence.applied_text == same_status
    # UI writes and post-enter should be skipped when already active
    assert not mock_adapter.write_text_no_focus.called
    assert not mock_adapter.post_background_enter.called


def test_executor_never_claims_text_write_as_applied():
    """Text write or message dispatch alone does NOT prove Camfrog applied the status.

    If CComboBoxTS item 0 never updates to match, fail closed as COMMIT_NOT_VERIFIED.
    """
    new_status = "Never applied status"
    resolver, proc, main_win, mock_adapter = _make_mock_resolver(
        current_applied="Old Status",
        target_readback=new_status,
    )
    # read_applied_status stubbornly remains Old Status
    mock_adapter.read_applied_status.return_value = "Old Status"

    executor = BackgroundStatusExecutor(resolver=resolver)
    evidence = executor.execute_status_change(new_status, pid=5555, timeout_seconds=0.1)

    assert evidence.result_state == StatusResultState.FAILED.value
    assert evidence.error_code == "COMMIT_NOT_VERIFIED"
    assert evidence.verification_source == "combo_history_verification"
    assert evidence.applied_text == ""


def test_executor_empty_text_fails_fast():
    executor = BackgroundStatusExecutor()
    evidence = executor.execute_status_change("   ")
    assert evidence.result_state == StatusResultState.FAILED.value
    assert evidence.error_code == "EMPTY_STATUS_TEXT"


def test_executor_process_not_found():
    resolver = MagicMock()
    resolver.resolve_status_controls.side_effect = ProcessLookupError("No process")

    executor = BackgroundStatusExecutor(resolver=resolver)
    evidence = executor.execute_status_change("Test Status", pid=99999)

    assert evidence.result_state == StatusResultState.FAILED.value
    assert evidence.error_code == "PROCESS_NOT_FOUND"
    assert evidence.verification_source == "process_discovery"


def test_executor_controls_not_found():
    resolver = MagicMock()
    resolver.resolve_status_controls.side_effect = LookupError("Controls missing")

    executor = BackgroundStatusExecutor(resolver=resolver)
    evidence = executor.execute_status_change("Test Status", pid=5555)

    assert evidence.result_state == StatusResultState.BACKGROUND_UNSUPPORTED.value
    assert evidence.error_code == "CONTROLS_NOT_FOUND"


def test_executor_write_text_failure():
    resolver, proc, main_win, mock_adapter = _make_mock_resolver()
    mock_adapter.write_text_no_focus.return_value = False

    executor = BackgroundStatusExecutor(resolver=resolver)
    evidence = executor.execute_status_change("New Status", pid=5555)

    assert evidence.result_state == StatusResultState.FAILED.value
    assert evidence.error_code == "WRITE_TEXT_FAILED"


def test_executor_readback_mismatch():
    resolver, proc, main_win, mock_adapter = _make_mock_resolver(target_readback="Mismatched Text")

    executor = BackgroundStatusExecutor(resolver=resolver)
    evidence = executor.execute_status_change("Expected Text", pid=5555)

    assert evidence.result_state == StatusResultState.FAILED.value
    assert evidence.error_code == "READBACK_MISMATCH"


def test_executor_post_enter_failure():
    resolver, proc, main_win, mock_adapter = _make_mock_resolver(target_readback="Valid")
    mock_adapter.post_background_enter.return_value = False

    executor = BackgroundStatusExecutor(resolver=resolver)
    evidence = executor.execute_status_change("Valid", pid=5555)

    assert evidence.result_state == StatusResultState.FAILED.value
    assert evidence.error_code == "POST_ENTER_FAILED"


# ---------- StatusScheduler Tests ----------

def test_status_scheduler_record_and_history():
    scheduler = StatusScheduler()
    assert len(scheduler.get_history()) == 0

    ev = StatusExecutionEvidence(
        request_id="req-1",
        operation_id="op-1",
        client_version="8.5.0",
        process_identity={"pid": 1234},
        window_role="main_directory",
        execution_mode="strict_background",
        result_state="VERIFIED_APPLIED",
        duration_ms=45.2,
        verification_source="combo_history_item_0",
        applied_text="Hello",
    )
    scheduler.record_evidence(ev)
    history = scheduler.get_history()
    assert len(history) == 1
    assert history[0]["applied_text"] == "Hello"
    assert history[0]["result_state"] == "VERIFIED_APPLIED"


def test_status_scheduler_stop_not_running():
    scheduler = StatusScheduler()
    assert scheduler.is_running() is False
    scheduler.stop()
    assert scheduler.is_running() is False


# ---------- Configuration Contract Validation Tests ----------

def test_validate_status_config_defaults():
    valid, errors, normalized = validate_status_config({})
    assert valid is True
    assert errors == []
    assert normalized["status"]["execution_mode"] == "strict_background"
    assert normalized["status"]["background_enter_target"] == "combo"
    assert normalized["safety"]["allow_focus_stealing"] is False
    assert normalized["safety"]["allow_mouse_injection"] is False
    assert normalized["safety"]["allow_keyboard_injection"] is False
    assert normalized["safety"]["allow_system_sound_changes"] is False


def test_validate_status_config_invalid_mode_and_target():
    invalid_cfg = {
        "status": {
            "execution_mode": "invalid_stealing",
            "background_enter_target": "unsupported",
        }
    }
    valid, errors, _ = validate_status_config(invalid_cfg)
    assert valid is False
    assert any("execution_mode" in e for e in errors)
    assert any("background_enter_target" in e for e in errors)


def test_executor_ambiguous_identity_returns_evidence_not_raise():
    resolver = MagicMock()
    resolver.resolve_status_controls.side_effect = RuntimeError(
        "Multiple verified Camfrog processes detected ([1111, 2222])."
    )

    executor = BackgroundStatusExecutor(resolver=resolver)
    evidence = executor.execute_status_change("Test Status")

    assert evidence.result_state == StatusResultState.FAILED.value
    assert evidence.error_code == "AMBIGUOUS_PROCESS_IDENTITY"
    assert evidence.verification_source == "process_discovery"


def test_executor_refuses_new_work_during_emergency_stop():
    from camfrog_emergency_stop import EmergencyStopRegistry, EmergencyStopScope

    registry = EmergencyStopRegistry()
    registry._reset_for_testing()
    try:
        resolver, _, _, _ = _make_mock_resolver(
            current_applied="Old Status", target_readback="New Status"
        )
        executor = BackgroundStatusExecutor(resolver=resolver)
        registry.activate(EmergencyStopScope.GLOBAL, "OPERATOR_HALT", "op-test")

        evidence = executor.execute_status_change("New Status")

        assert evidence.result_state == StatusResultState.FAILED.value
        assert evidence.error_code == "EMERGENCY_STOP"
        assert evidence.verification_source == "emergency_stop"
    finally:
        registry._reset_for_testing()
