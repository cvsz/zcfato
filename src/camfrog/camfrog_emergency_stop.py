"""Emergency Stop mechanism for ZChat V6.0 (Phase 22).

Provides authoritative, thread-safe emergency stop controls covering individual
features, accounts, agents, machines, or the entire ZChat operation.

Safety guarantees
-----------------
- MUST NOT call os.kill() or subprocess on any Camfrog client PID.
- MUST NOT modify the Windows registry.
- Audit records are preserved permanently even after deactivation.
- All public operations are thread-safe.
- Works on Linux and Windows (no Windows-only module-level imports).
- Deactivation is always explicit; stops do not auto-expire.
- Activating GLOBAL scope logically stops all lower scopes.
- EmergencyStopGuard raises StopIteration (never SystemExit) when stopped.
- In-flight operations that cannot be interrupted are reported, not killed.
- Emergency Stop cannot undo an already-executed external action.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Scope enumeration
# ---------------------------------------------------------------------------

class EmergencyStopScope(str, Enum):
    """Hierarchical scopes for emergency stop coverage.

    Hierarchy (broadest → narrowest):
        GLOBAL > MACHINE > AGENT > ACCOUNT > FEATURE
    Activating a broader scope implicitly stops all narrower scopes.
    """
    GLOBAL = "GLOBAL"
    MACHINE = "MACHINE"
    AGENT = "AGENT"
    ACCOUNT = "ACCOUNT"
    FEATURE = "FEATURE"


# Ordered from broadest to narrowest — used for hierarchy checks.
_SCOPE_HIERARCHY: List[EmergencyStopScope] = [
    EmergencyStopScope.GLOBAL,
    EmergencyStopScope.MACHINE,
    EmergencyStopScope.AGENT,
    EmergencyStopScope.ACCOUNT,
    EmergencyStopScope.FEATURE,
]


def _scope_rank(scope: EmergencyStopScope) -> int:
    """Return the rank of *scope* (lower rank = broader scope)."""
    return _SCOPE_HIERARCHY.index(scope)


# ---------------------------------------------------------------------------
# Stop reason record
# ---------------------------------------------------------------------------

@dataclass
class EmergencyStopReason:
    """Immutable record describing a single emergency stop activation.

    Attributes
    ----------
    stop_id:
        Unique identifier for this stop event.
    scope:
        The scope covered by this stop.
    reason_code:
        Machine-readable reason string (e.g., ``"OPERATOR_HALT"``).
    operator_id:
        Identity of the operator or system that activated the stop.
    timestamp:
        UNIX epoch timestamp (seconds) when the stop was activated.
    affected_resources:
        Optional list of specific resource keys affected (empty = all within scope).
    active:
        ``True`` while the stop is in force; ``False`` after explicit deactivation.
        Set by :class:`EmergencyStopRegistry` — callers must not mutate this directly.
    deactivated_at:
        UNIX epoch timestamp when the stop was explicitly deactivated, or ``None``.
    """
    scope: EmergencyStopScope
    reason_code: str
    operator_id: str
    timestamp: float = field(default_factory=time.time)
    affected_resources: List[str] = field(default_factory=list)
    stop_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    active: bool = field(default=True, init=False)
    deactivated_at: Optional[float] = field(default=None, init=False)

    def as_dict(self) -> Dict[str, Any]:
        """Return a serialisable representation suitable for audit logs."""
        return {
            "stop_id": self.stop_id,
            "scope": self.scope.value,
            "reason_code": self.reason_code,
            "operator_id": self.operator_id,
            "timestamp": self.timestamp,
            "affected_resources": list(self.affected_resources),
            "active": self.active,
            "deactivated_at": self.deactivated_at,
        }


# ---------------------------------------------------------------------------
# Registry — singleton
# ---------------------------------------------------------------------------

class EmergencyStopRegistry:
    """Singleton registry that tracks all active and historical emergency stops.

    Thread Safety
    -------------
    All public methods acquire the internal ``_lock`` before mutating state.

    Scope Hierarchy
    ---------------
    ``is_stopped`` returns ``True`` for scope *S* and optional *resource_key*
    if **any** active stop has a scope whose rank is ≤ the rank of *S*
    (i.e. a broader or equal scope is active).  A GLOBAL stop therefore causes
    every finer-grained ``is_stopped`` check to return ``True``.

    Audit Preservation
    ------------------
    ``_audit_log`` accumulates all stop events permanently.  Even after
    ``deactivate`` is called, the original :class:`EmergencyStopReason` record
    (with ``active=False`` and ``deactivated_at`` filled in) remains in the log.
    """

    _instance: Optional["EmergencyStopRegistry"] = None
    _singleton_lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "EmergencyStopRegistry":
        with cls._singleton_lock:
            if cls._instance is None:
                obj = super().__new__(cls)
                obj._lock = threading.RLock()
                # Maps stop_id -> EmergencyStopReason (active entries only)
                obj._active_stops: Dict[str, EmergencyStopReason] = {}
                # Permanent audit trail — never cleared
                obj._audit_log: List[EmergencyStopReason] = []
                cls._instance = obj
            return cls._instance

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _matching_active_stops(
        self,
        scope: EmergencyStopScope,
        resource_key: Optional[str],
    ) -> List[EmergencyStopReason]:
        """Return active stops that cover *scope* + *resource_key*."""
        target_rank = _scope_rank(scope)
        results: List[EmergencyStopReason] = []
        for stop in self._active_stops.values():
            stop_rank = _scope_rank(stop.scope)
            if stop_rank > target_rank:
                # This stop is narrower than the requested scope; skip.
                continue
            if stop_rank < target_rank:
                # This stop is broader — it covers everything; include.
                results.append(stop)
                continue
            # Same scope level.
            if not stop.affected_resources or resource_key is None:
                # Affects all resources at this scope.
                results.append(stop)
            elif resource_key in stop.affected_resources:
                results.append(stop)
        return results

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def activate(
        self,
        scope: EmergencyStopScope,
        reason_code: str,
        operator_id: str,
        affected_resources: Optional[List[str]] = None,
    ) -> EmergencyStopReason:
        """Activate an emergency stop for *scope*.

        Parameters
        ----------
        scope:
            The :class:`EmergencyStopScope` to cover.
        reason_code:
            Machine-readable code identifying the reason (e.g. ``"OPERATOR_HALT"``).
        operator_id:
            Identity of the entity triggering the stop.
        affected_resources:
            Optional list of specific resource keys within *scope* to affect.
            When empty or ``None``, the stop applies to **all** resources within
            the scope.

        Returns
        -------
        EmergencyStopReason
            The newly created stop record.
        """
        with self._lock:
            reason = EmergencyStopReason(
                scope=scope,
                reason_code=reason_code,
                operator_id=operator_id,
                affected_resources=list(affected_resources or []),
            )
            self._active_stops[reason.stop_id] = reason
            self._audit_log.append(reason)
            return reason

    def deactivate(
        self,
        scope: EmergencyStopScope,
        resource_key: Optional[str] = None,
    ) -> bool:
        """Explicitly deactivate active stops matching *scope* and *resource_key*.

        Deactivation marks every matching active stop as inactive and records the
        deactivation time.  The records remain in the audit log permanently.

        Parameters
        ----------
        scope:
            The scope level to deactivate.
        resource_key:
            When provided, only deactivate stops that explicitly list this key
            in ``affected_resources``.  When ``None``, deactivate all stops at
            the given *scope* level (regardless of ``affected_resources``).

        Returns
        -------
        bool
            ``True`` if at least one active stop was deactivated, ``False``
            otherwise.
        """
        now = time.time()
        with self._lock:
            to_deactivate: List[str] = []
            for stop_id, stop in self._active_stops.items():
                if stop.scope != scope:
                    continue
                if resource_key is None:
                    to_deactivate.append(stop_id)
                elif resource_key in stop.affected_resources:
                    to_deactivate.append(stop_id)

            for stop_id in to_deactivate:
                stop = self._active_stops.pop(stop_id)
                stop.active = False
                stop.deactivated_at = now

            return len(to_deactivate) > 0

    def is_stopped(
        self,
        scope: EmergencyStopScope,
        resource_key: Optional[str] = None,
    ) -> bool:
        """Return ``True`` if any active stop covers *scope* / *resource_key*.

        A stop at a **broader** scope (lower rank in the hierarchy) implicitly
        stops every narrower scope.  For example, an active GLOBAL stop makes
        every ``is_stopped`` call return ``True`` regardless of scope or key.

        Parameters
        ----------
        scope:
            The scope to check.
        resource_key:
            Optional specific resource key within the scope.
        """
        with self._lock:
            return bool(self._matching_active_stops(scope, resource_key))

    def get_active_stops(self) -> List[EmergencyStopReason]:
        """Return a snapshot list of all currently active stop records."""
        with self._lock:
            return list(self._active_stops.values())

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Return the full, permanent audit log as a list of dicts.

        Records are never removed, even after deactivation.
        """
        with self._lock:
            return [entry.as_dict() for entry in self._audit_log]

    # ------------------------------------------------------------------
    # Test / maintenance helpers
    # ------------------------------------------------------------------

    def _reset_for_testing(self) -> None:
        """Clear all state.  ONLY call this from test code."""
        with self._lock:
            self._active_stops.clear()
            self._audit_log.clear()


# ---------------------------------------------------------------------------
# EmergencyStopGuard — context manager
# ---------------------------------------------------------------------------

class EmergencyStopGuard:
    """Context manager that gates execution on the current stop state.

    Usage
    -----
    .. code-block:: python

        guard = EmergencyStopGuard(
            scope=EmergencyStopScope.AGENT,
            resource_key="agent-42",
            registry=registry,
        )
        with guard:
            # Code here runs only if no emergency stop is active.
            do_work()

    Raises
    ------
    StopIteration
        If the registry reports the given scope/resource is stopped.
        ``StopIteration`` is used deliberately (not ``SystemExit``) so that
        callers may catch and handle it gracefully without risking interpreter
        shutdown.

    Notes
    -----
    - The guard does **not** modify Camfrog client processes.
    - It does **not** call ``os.kill()`` or modify the Windows registry.
    - The stop check is performed at ``__enter__`` time; an in-flight operation
      that was already past the guard when a stop is activated will complete.
      Such operations are considered "in-flight and cannot be interrupted" and
      must be reported separately.
    """

    def __init__(
        self,
        scope: EmergencyStopScope,
        resource_key: Optional[str] = None,
        registry: Optional[EmergencyStopRegistry] = None,
        description: str = "",
    ) -> None:
        self.scope = scope
        self.resource_key = resource_key
        self.registry = registry or EmergencyStopRegistry()
        self.description = description

    def __enter__(self) -> "EmergencyStopGuard":
        if self.registry.is_stopped(self.scope, self.resource_key):
            active = self.registry.get_active_stops()
            detail = "; ".join(
                f"[{s.scope.value}/{s.reason_code}]" for s in active
            )
            msg = (
                f"Emergency stop active for scope={self.scope.value}"
                + (f" resource={self.resource_key!r}" if self.resource_key else "")
                + (f" ({self.description})" if self.description else "")
                + (f". Active stops: {detail}" if detail else ".")
            )
            raise StopIteration(msg)
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> bool:
        # Never suppress exceptions from the guarded block.
        return False


# ---------------------------------------------------------------------------
# EmergencyStopHook — mixin for StatusScheduler / BackgroundStatusExecutor
# ---------------------------------------------------------------------------

class EmergencyStopHook:
    """Mixin that integrates emergency stop awareness into executor/scheduler classes.

    Classes that inherit from this mixin gain:

    * ``stop_registry`` — a reference to the shared :class:`EmergencyStopRegistry`.
    * ``emergency_scope`` / ``emergency_resource_key`` — configurable scope defaults.
    * ``check_emergency_stop()`` — raises ``StopIteration`` if stopped.
    * ``stop_workers_safely()`` — signals internal stop events and joins worker
      threads without killing the Camfrog client process.
    * ``report_inflight_operations()`` — returns a snapshot of operations that
      were already executing when the stop was activated.

    Integration example
    -------------------
    .. code-block:: python

        class MyScheduler(EmergencyStopHook, StatusScheduler):
            pass

        scheduler = MyScheduler()
        scheduler.emergency_scope = EmergencyStopScope.AGENT
        scheduler.emergency_resource_key = "agent-1"

        with EmergencyStopGuard(scheduler.emergency_scope, scheduler.emergency_resource_key):
            scheduler.set_single_status("available")
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.stop_registry: EmergencyStopRegistry = EmergencyStopRegistry()
        self.emergency_scope: EmergencyStopScope = EmergencyStopScope.GLOBAL
        self.emergency_resource_key: Optional[str] = None
        # Tracks in-flight operation IDs for reporting.
        self._inflight_ops: Dict[str, str] = {}
        self._inflight_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Core hook methods
    # ------------------------------------------------------------------

    def check_emergency_stop(
        self,
        scope: Optional[EmergencyStopScope] = None,
        resource_key: Optional[str] = None,
    ) -> None:
        """Raise ``StopIteration`` if an active stop covers the given scope.

        Uses ``self.emergency_scope`` / ``self.emergency_resource_key`` as
        defaults when the caller does not provide explicit values.
        """
        effective_scope = scope or self.emergency_scope
        effective_key = resource_key if resource_key is not None else self.emergency_resource_key
        if self.stop_registry.is_stopped(effective_scope, effective_key):
            active = self.stop_registry.get_active_stops()
            detail = "; ".join(
                f"[{s.scope.value}/{s.reason_code}]" for s in active
            )
            raise StopIteration(
                f"Emergency stop active for {effective_scope.value}"
                + (f"/{effective_key}" if effective_key else "")
                + (f": {detail}" if detail else ".")
            )

    def register_inflight(self, op_id: str, description: str) -> None:
        """Register an operation as in-flight (already executing past the guard)."""
        with self._inflight_lock:
            self._inflight_ops[op_id] = description

    def complete_inflight(self, op_id: str) -> None:
        """Mark an in-flight operation as complete."""
        with self._inflight_lock:
            self._inflight_ops.pop(op_id, None)

    def report_inflight_operations(self) -> Dict[str, str]:
        """Return a snapshot of operations that cannot be immediately interrupted.

        Returns
        -------
        dict
            Mapping of ``op_id -> description`` for each in-flight operation.
        """
        with self._inflight_lock:
            return dict(self._inflight_ops)

    def stop_workers_safely(self, join_timeout: float = 2.0) -> None:
        """Signal any ZChat-owned worker threads to stop and wait for them.

        Safe guarantees
        ---------------
        - Does **not** call ``os.kill()`` on any PID.
        - Does **not** use ``subprocess`` to terminate any process.
        - Does **not** touch the Camfrog client in any way.
        - Signals internal ``threading.Event`` stop flags where available.
        - Joins worker threads with a bounded timeout so callers are not blocked.
        """
        # Signal stop events provided by StatusScheduler or BackgroundStatusExecutor.
        stop_event: Optional[threading.Event] = getattr(self, "_stop_event", None)
        if stop_event is not None:
            stop_event.set()

        worker: Optional[threading.Thread] = getattr(self, "_worker_thread", None)
        if worker is not None and worker.is_alive():
            worker.join(timeout=join_timeout)

    # ------------------------------------------------------------------
    # Convenience guard factory
    # ------------------------------------------------------------------

    def make_guard(
        self,
        scope: Optional[EmergencyStopScope] = None,
        resource_key: Optional[str] = None,
        description: str = "",
    ) -> EmergencyStopGuard:
        """Return an :class:`EmergencyStopGuard` configured for this instance."""
        return EmergencyStopGuard(
            scope=scope or self.emergency_scope,
            resource_key=resource_key if resource_key is not None else self.emergency_resource_key,
            registry=self.stop_registry,
            description=description,
        )
