"""Pure scheduling rules for recurring LINE status changes."""
from __future__ import annotations

from datetime import datetime, timedelta


def due_schedules(schedule, now=None, grace_seconds=90):
    """Return newly due item copies and their occurrence keys.

    Weekly entries fire once per local date/minute. Interval entries use their
    last-fired time; the first interval starts when its entry is created.
    Callers must persist each returned occurrence key before doing UI work.
    """
    now = now or datetime.now()
    if schedule.get("paused"):
        return []
    fired = schedule.setdefault("last_fired", {})
    due = []
    for item in schedule.get("items", []):
        if not item.get("enabled", True):
            continue
        item_id = item["id"]
        mode = item.get("mode", "weekly")
        if mode == "interval":
            previous_raw = fired.get(item_id)
            try:
                previous = datetime.fromisoformat(previous_raw) if previous_raw else None
            except (TypeError, ValueError):
                previous = None
            # ISO-8601 markers may be naive (older configs) or timezone-aware
            # (hand-edited/imported configs). Compare both forms on one timeline.
            if previous is None or now.timestamp() - previous.timestamp() >= item["interval_minutes"] * 60:
                occurrence = now.isoformat(timespec="seconds")
                due.append((dict(item), occurrence))
            continue

        if now.weekday() not in item["days"]:
            continue
        hour, minute = map(int, item["time"].split(":"))
        scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        age = (now - scheduled).total_seconds()
        if 0 <= age <= grace_seconds:
            occurrence = scheduled.isoformat(timespec="minutes")
            if fired.get(item_id) != occurrence:
                due.append((dict(item), occurrence))
    return due


def mark_schedule_fired(schedule, item_id, occurrence):
    """Persist a run marker and prune entries older than two weeks."""
    fired = schedule.setdefault("last_fired", {})
    fired[item_id] = occurrence
    cutoff = datetime.now().timestamp() - timedelta(days=14).total_seconds()
    for key, value in list(fired.items()):
        try:
            when = datetime.fromisoformat(value)
        except (TypeError, ValueError):
            del fired[key]
            continue
        try:
            expired = when.timestamp() < cutoff
        except (OverflowError, OSError, ValueError):
            expired = True
        if expired:
            del fired[key]
