"""Validated, crash-safe storage for LINE Status Changer settings."""
from __future__ import annotations

import json
import os
import tempfile
import unicodedata
from datetime import datetime
from pathlib import Path


CONFIG_VERSION = 2
MAX_CONFIG_BYTES = 1024 * 1024
MAX_HISTORY = 500
MAX_SCHEDULES = 100
MAX_PRESETS = 25


class ConfigError(ValueError):
    """The saved configuration is invalid or unsupported."""


def default_config():
    return {
        "schema_version": CONFIG_VERSION,
        "last_text": "",
        "messages": [
            "ว่างคุยได้ ทักมาได้เลย",
            "กำลังทำงาน อาจตอบช้านิดนึง",
            "ขอให้วันนี้เป็นวันที่ดี",
        ],
        "presets": {
            "Work": "กำลังทำงาน อาจตอบช้านิดนึง",
            "Personal": "ว่างคุยได้ ทักมาได้เลย",
            "Away": "ไม่อยู่ชั่วคราว อาจตอบช้า",
        },
        "history": [],
        "schedule": {"paused": False, "items": [], "last_fired": {}},
        "start_with_windows": False,
        "show_hotkey": False,
    }


def validate_status_text(text):
    """Validate a single-line status message without altering its contents."""
    if not isinstance(text, str):
        raise ValueError("Status text must be a string.")
    if not text.strip():
        raise ValueError("Enter a status message first.")
    if len(text) > 5000:
        raise ValueError("Status text is over the local 5,000-character safety limit.")
    if any(unicodedata.category(char) == "Cc" for char in text):
        raise ValueError("Status text must be one line and cannot contain control characters.")
    try:
        text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("Status text contains invalid Unicode characters.") from exc
    return text


def validate_config(data):
    if not isinstance(data, dict):
        raise ConfigError("Configuration must be a JSON object.")
    version = data.get("schema_version", 1)
    if type(version) is not int or version not in (1, CONFIG_VERSION):
        raise ConfigError(f"Unsupported line_config.json schema version: {version!r}.")

    last_text = data.get("last_text", "")
    if not isinstance(last_text, str):
        raise ConfigError("'last_text' must be a string.")
    try:
        validate_status_text(last_text) if last_text else None
    except ValueError as exc:
        raise ConfigError(f"'last_text' is invalid: {exc}") from exc

    messages = data.get("messages", [])
    if not isinstance(messages, list):
        raise ConfigError("'messages' must be a list of strings.")
    if len(messages) > 1000:
        raise ConfigError("'messages' contains more than 1,000 saved entries.")
    for index, message in enumerate(messages):
        if not isinstance(message, str):
            raise ConfigError(f"'messages[{index}]' must be a string.")
        try:
            validate_status_text(message)
        except ValueError as exc:
            raise ConfigError(f"'messages[{index}]' is invalid: {exc}") from exc

    presets = data.get("presets", default_config()["presets"])
    if not isinstance(presets, dict) or len(presets) > MAX_PRESETS:
        raise ConfigError(f"'presets' must be an object with at most {MAX_PRESETS} entries.")
    normalized_presets = {}
    for name, text in presets.items():
        if (not isinstance(name, str) or not name.strip() or len(name) > 40
                or any(unicodedata.category(char) == "Cc" for char in name)):
            raise ConfigError("Preset names must be non-empty, single-line text up to 40 characters.")
        try:
            validate_status_text(text)
        except ValueError as exc:
            raise ConfigError(f"Preset {name!r} is invalid: {exc}") from exc
        normalized_presets[name.strip()] = text

    history = data.get("history", [])
    if not isinstance(history, list) or len(history) > MAX_HISTORY:
        raise ConfigError(f"'history' must be a list with at most {MAX_HISTORY} entries.")
    normalized_history = []
    for index, entry in enumerate(history):
        if not isinstance(entry, dict):
            raise ConfigError(f"'history[{index}]' must be an object.")
        text, timestamp = entry.get("text"), entry.get("timestamp")
        outcome = entry.get("outcome", "saved")
        if not isinstance(text, str) or not isinstance(timestamp, str):
            raise ConfigError(f"'history[{index}]' needs text and timestamp strings.")
        try:
            datetime.fromisoformat(timestamp)
        except ValueError as exc:
            raise ConfigError(f"'history[{index}].timestamp' must be ISO-8601.") from exc
        try:
            validate_status_text(text)
        except ValueError as exc:
            raise ConfigError(f"'history[{index}]' is invalid: {exc}") from exc
        if outcome not in ("saved", "verified", "scheduled"):
            raise ConfigError(f"'history[{index}].outcome' is invalid.")
        normalized_history.append({"text": text, "timestamp": timestamp, "outcome": outcome})

    schedule = data.get("schedule", {"paused": False, "items": [], "last_fired": {}})
    if not isinstance(schedule, dict):
        raise ConfigError("'schedule' must be an object.")
    paused = schedule.get("paused", False)
    items = schedule.get("items", [])
    last_fired = schedule.get("last_fired", {})
    if type(paused) is not bool or not isinstance(items, list) or len(items) > MAX_SCHEDULES:
        raise ConfigError("Schedule pause flag or item list is invalid.")
    normalized_items = []
    seen_ids = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ConfigError(f"'schedule.items[{index}]' must be an object.")
        item_id, text, clock, days = (
            item.get("id"), item.get("text"), item.get("time"), item.get("days")
        )
        mode = item.get("mode", "weekly")
        interval_minutes = item.get("interval_minutes")
        enabled = item.get("enabled", True)
        if (not isinstance(item_id, str) or not item_id or len(item_id) > 64
                or item_id in seen_ids):
            raise ConfigError(f"'schedule.items[{index}].id' is invalid or duplicated.")
        seen_ids.add(item_id)
        if mode not in ("weekly", "interval"):
            raise ConfigError(f"'schedule.items[{index}].mode' is invalid.")
        if mode == "weekly":
            if (not isinstance(clock, str) or len(clock) != 5 or clock[2] != ":"
                    or not clock[:2].isdigit() or not clock[3:].isdigit()
                    or int(clock[:2]) > 23 or int(clock[3:]) > 59):
                raise ConfigError(f"'schedule.items[{index}].time' must be HH:MM.")
            if (not isinstance(days, list) or not days or len(days) > 7
                    or any(type(day) is not int or day < 0 or day > 6 for day in days)
                    or len(set(days)) != len(days)):
                raise ConfigError(f"'schedule.items[{index}].days' must contain unique weekdays 0–6.")
        elif type(interval_minutes) is not int or not 1 <= interval_minutes <= 10080:
            raise ConfigError(f"'schedule.items[{index}].interval_minutes' must be 1–10,080.")
        if type(enabled) is not bool:
            raise ConfigError(f"'schedule.items[{index}].enabled' must be boolean.")
        try:
            validate_status_text(text)
        except ValueError as exc:
            raise ConfigError(f"'schedule.items[{index}].text' is invalid: {exc}") from exc
        normalized_items.append({
            "id": item_id, "text": text,
            "time": clock if mode == "weekly" else "",
            "days": sorted(days) if mode == "weekly" else [],
            "mode": mode,
            "interval_minutes": interval_minutes if mode == "interval" else None,
            "enabled": enabled,
        })
    if (not isinstance(last_fired, dict) or len(last_fired) > MAX_SCHEDULES * 14
            or any(not isinstance(k, str) or not isinstance(v, str)
                   for k, v in last_fired.items())):
        raise ConfigError("'schedule.last_fired' is invalid.")
    for value in last_fired.values():
        try:
            datetime.fromisoformat(value)
        except ValueError as exc:
            raise ConfigError("'schedule.last_fired' values must be ISO-8601 timestamps.") from exc

    start_with_windows = data.get("start_with_windows", False)
    show_hotkey = data.get("show_hotkey", False)
    if type(start_with_windows) is not bool or type(show_hotkey) is not bool:
        raise ConfigError("Windows integration settings must be booleans.")

    # Preserve future/user-added keys instead of deleting them on the next save.
    result = dict(data)
    result.pop("tray_on_close", None)  # Legacy option is no longer user-configurable.
    result.update({
        "schema_version": CONFIG_VERSION,
        "last_text": last_text,
        "messages": list(messages),
        "presets": normalized_presets,
        "history": normalized_history[-MAX_HISTORY:],
        "schedule": {
            "paused": paused, "items": normalized_items,
            "last_fired": dict(last_fired),
        },
        "start_with_windows": start_with_windows,
        "show_hotkey": show_hotkey,
    })
    return result


def save_config(path, data):
    path = Path(path)
    normalized = validate_config(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as temp:
            temp_path = Path(temp.name)
            json.dump(normalized, temp, ensure_ascii=False, indent=2)
            temp.write("\n")
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def load_config(path, create_if_missing=True):
    path = Path(path)
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        if not create_if_missing:
            raise
        data = default_config()
        save_config(path, data)
        return data
    if size > MAX_CONFIG_BYTES:
        raise ConfigError(f"Configuration is larger than {MAX_CONFIG_BYTES} bytes: {path}")

    def reject_constant(value):
        raise ConfigError(f"Non-standard JSON numeric value is not allowed: {value}")

    try:
        with path.open("r", encoding="utf-8-sig") as stream:
            data = json.load(stream, parse_constant=reject_constant)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"Invalid JSON in {path} at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    except UnicodeDecodeError as exc:
        raise ConfigError(f"Configuration is not valid UTF-8: {path}") from exc
    normalized = validate_config(data)
    if data.get("schema_version", 1) < CONFIG_VERSION:
        save_config(path, normalized)
    return normalized
