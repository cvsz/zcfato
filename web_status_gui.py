"""Camfrog web status updater - self-contained (updater logic + GUI inlined, no shared imports)."""
import argparse
import datetime
import email.utils
import getpass
import hashlib
import hmac
import http.client
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import base64
import socket
import time
import urllib.parse
import urllib.error
import urllib.request
from html.parser import HTMLParser
from http.cookiejar import Cookie, CookieJar, MozillaCookieJar
from pathlib import Path
import queue
import threading
import unicodedata


def system_taskkill_path():
    """Return taskkill.exe from Windows' system directory, never from PATH/cwd."""
    if os.name != "nt":
        return "taskkill.exe"
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_system_directory = kernel32.GetSystemDirectoryW
    get_system_directory.argtypes = (ctypes.POINTER(ctypes.c_wchar), ctypes.c_uint)
    get_system_directory.restype = ctypes.c_uint
    buffer = ctypes.create_unicode_buffer(32768)
    length = get_system_directory(buffer, len(buffer))
    if not length or length >= len(buffer):
        raise ctypes.WinError(ctypes.get_last_error())
    return os.path.join(buffer.value, "taskkill.exe")


# ============================================================
# Inlined updater logic (tools/web_status.py), main -> cli_main.
# ============================================================



# Frozen -> files live next to the exe; source -> the repo root (parent of tools/).
BASE = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) \
    else Path(__file__).resolve().parent.parent

LOGIN_URL = "https://www.camfrog.com/th/login/check.php"

# camfrog's edge blocks the default Python-urllib User-Agent with HTTP 403;
# every request therefore presents a plain browser identity. No cookies or
# credentials are added here.
BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}
LOGIN_PAGE_URL = "https://www.camfrog.com/th/login.php"

# Captured 2026-10-09 from a logged-in https://profiles.camfrog.com/home.php
# session: the profile page's hopping box POSTs {status, csrf} here, and the
# csrf token is embedded in that same page. The path is implemented but stays
# gated: the first live round-trip needs an explicit --confirm-update.
WEB_UPDATE_URL = "https://profiles.camfrog.com/ajax/update_status.php"
HOME_URL = "https://profiles.camfrog.com/home.php"

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_BLOCKED = 3

ROTATE_INTERVAL_MIN = 0.5
ROTATE_INTERVAL_DEFAULT = 10.0
ROTATE_INTERVAL_MAX = 86400
LIVE_ROTATE_INTERVAL_MIN = 10.0

WEB_MARQUEE_STEP_SECONDS_DEFAULT = 0.5
WEB_MARQUEE_STEP_SECONDS_MIN = 0.5
WEB_MARQUEE_STEP_SECONDS_MAX = 3600.0
WEB_MARQUEE_STEP_SECONDS = WEB_MARQUEE_STEP_SECONDS_DEFAULT
WEB_STATUS_LOOP_COUNT_DEFAULT = 0  # zero means infinite
WEB_STATUS_LOOP_COUNT_MAX = 10000
# Keep aliases for existing source-level integrations; the GUI no longer has
# a Web Status Marquee mode.
WEB_MARQUEE_LOOP_COUNT_DEFAULT = WEB_STATUS_LOOP_COUNT_DEFAULT
WEB_MARQUEE_LOOP_COUNT_MAX = WEB_STATUS_LOOP_COUNT_MAX
LIVE_RETRY_MAX_ATTEMPTS = 5
LIVE_RATE_LIMIT_RETRY_BASE_SECONDS = 30.0
LIVE_TIMEOUT_RETRY_BASE_SECONDS = LIVE_ROTATE_INTERVAL_MIN
LIVE_RETRY_MAX_DELAY_SECONDS = 120.0
LIVE_RETRY_MAX_SERVER_WAIT_SECONDS = 86400.0
WEB_STATUS_THEME = {
    "background": "#f4f1e8",
    "surface": "#fffdfa",
    "surface_high": "#ebe5d9",
    "entry": "#ffffff",
    "border": "#d5c8ac",
    "gold": "#8b672b",
    "gold_hover": "#76541f",
    "teal": "#d6e9e8",
    "text": "#283648",
    "muted": "#626d7a",
    "danger": "#9f3740",
    "success": "#28744c",
    "error": "#a3303a",
    "log_text": "#2c3b4d",
}
WEB_MARQUEE_WIDTH = 28
WEB_MARQUEE_STRIDE = 2
WEB_MARQUEE_SEPARATOR = "   \u2022   "
WEB_MARQUEE_MAX_FRAMES = 80

WEB_STATUS_LOG_NAME = "web_status.log"
WEB_STATUS_LOG_MAX_BYTES = 512 * 1024
WEB_STATUS_LOG_BACKUPS = 3
WEB_STATUS_LOG_GUI_LINES = 200
WEB_STATUS_LOG_DETAIL_MAX_CHARS = 1000
WEB_STATUS_LOG_FAILURE_EVENTS = frozenset((
    "session_verification_failed",
    "status_update_failed",
))
WEB_STATUS_LOG_DETAIL_EVENTS = WEB_STATUS_LOG_FAILURE_EVENTS | frozenset((
    "dry_run_rotation_started",
    "live_rotation_started",
    "live_retry_scheduled",
))
WEB_STATUS_LOG_EVENTS = {
    "session_verification_started": "Session verification started",
    "session_verification_succeeded": "Session verification succeeded",
    "session_verification_failed": "Session verification failed",
    "browser_login_started": "Browser login started",
    "browser_session_captured": "Browser session captured",
    "status_lines_saved": "Status lines saved",
    "dry_run_rotation_started": "Dry-run rotation started",
    "live_rotation_started": "Live rotation started",
    "marquee_completed": "Marquee completed configured rounds",
    "rotation_completed": "Rotation completed configured rounds",
    "status_previewed": "Dry-run status previewed",
    "status_update_succeeded": "Live status update succeeded",
    "status_update_failed": "Live status update failed",
    "live_retry_scheduled": "Live update retry scheduled",
    "rotation_stopped": "Rotation stopped",
}
WEB_STATUS_LOG_LABELS_TH = {
    "Session verification started": "เริ่มตรวจสอบเซสชัน",
    "Session verification succeeded": "ตรวจสอบเซสชันสำเร็จ",
    "Session verification failed": "ตรวจสอบเซสชันไม่สำเร็จ",
    "Browser login started": "เริ่มเข้าสู่ระบบผ่านเบราว์เซอร์",
    "Browser session captured": "รับเซสชันจากเบราว์เซอร์แล้ว",
    "Status lines saved": "บันทึกข้อความสถานะแล้ว",
    "Dry-run rotation started": "เริ่มวนสถานะแบบทดลอง",
    "Live rotation started": "เริ่มวนสถานะจริง",
    "Marquee completed configured rounds": "วนข้อความครบตามจำนวนรอบ",
    "Rotation completed configured rounds": "วนสถานะครบตามจำนวนรอบ",
    "Dry-run status previewed": "แสดงตัวอย่างสถานะแบบทดลอง",
    "Live status update succeeded": "อัปเดตสถานะจริงสำเร็จ",
    "Live status update failed": "อัปเดตสถานะจริงล้มเหลว",
    "Live update retry scheduled": "ตั้งเวลาลองอัปเดตสถานะจริงอีกครั้ง",
    "Rotation stopped": "หยุดการวนสถานะ",
}
WEB_STATUS_LOG_LABELS_EN = {
    thai: english for english, thai in WEB_STATUS_LOG_LABELS_TH.items()
}
_WEB_STATUS_LOG_LOCK = threading.Lock()
_GUI_CALLBACK_MARKER = object()


def _sanitize_web_status_detail(value, secrets=()):
    """Bound diagnostics and remove cookie, token, and caller-known secret values."""
    text = str(value)
    for secret in sorted((str(item) for item in secrets if item),
                         key=len, reverse=True):
        if len(secret) <= 3:
            text = re.sub(r"(?<!\w){0}(?!\w)".format(re.escape(secret)),
                          "[redacted]", text)
        else:
            text = text.replace(secret, "[redacted]")
    text = re.sub(
        r"(?im)(\b(?:cookie|set-cookie|authorization)\s*:\s*)[^\r\n]*",
        r"\1[redacted]", text)
    text = re.sub(
        r"(?i)(\b(?:php\s*session\s*id|phpsessid|session[_-]?id|csrf(?:[_-]?token)?|"
        r"access[_-]?token|auth[_-]?token|authorization|token|password|passwd|secret)\b"
        r"[\"']?\s*[:=]\s*)(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|[^&\s,;}}\]]+)",
        r"\1[redacted]", text)
    text = re.sub(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
                  "[email redacted]", text)
    text = re.sub(r"(?<!\w)\+?\d[\d().\s-]{6,}\d(?!\w)",
                  "[number redacted]", text)
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", text)
    text = re.sub(r"\s+", " ", text).replace("|", "/").strip()
    if len(text) > WEB_STATUS_LOG_DETAIL_MAX_CHARS:
        text = text[:WEB_STATUS_LOG_DETAIL_MAX_CHARS - 14].rstrip() + " [truncated]"
    return text


def _web_status_response_keys(data):
    """Return a small, safe summary of untrusted JSON object keys."""
    safe = []
    for key in data:
        if isinstance(key, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,39}", key):
            if re.search(r"(?i)cookie|csrf|token|password|secret|session", key):
                safe.append("[sensitive-key]")
            else:
                safe.append(key)
        else:
            safe.append("[other-key]")
    return ",".join(sorted(set(safe))[:12]) or "none"


def _web_status_value_summary(value, secrets=()):
    if isinstance(value, str):
        return "string({0} chars): {1}".format(
            len(value), _sanitize_web_status_detail(value, secrets=secrets))
    if isinstance(value, (bool, int, float)) or value is None:
        return "{0}: {1}".format(type(value).__name__, value)
    if isinstance(value, (dict, list, tuple)):
        return "{0}({1} items)".format(type(value).__name__, len(value))
    return type(value).__name__


class _VisibleResponseText(HTMLParser):
    """Collect visible response text without HTML attributes or script contents."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._hidden_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in ("script", "style", "noscript"):
            self._hidden_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() in ("script", "style", "noscript") and self._hidden_depth:
            self._hidden_depth -= 1

    def handle_data(self, data):
        if not self._hidden_depth and data.strip():
            self.parts.append(data.strip())


def _web_status_error_response_summary(value, secrets=()):
    """Summarize visible server error text while excluding markup and common PII."""
    if not isinstance(value, str):
        return _web_status_value_summary(value, secrets=secrets)
    parser = _VisibleResponseText()
    try:
        parser.feed(value)
        parser.close()
        visible = " ".join(parser.parts)
    except Exception:
        visible = value
    visible = _sanitize_web_status_detail(visible, secrets=secrets)
    if len(visible) > 300:
        visible = visible[:286].rstrip() + " [truncated]"
    return "string({0} chars); visible_text={1}".format(len(value), visible or "empty")


def _retry_after_seconds(value):
    """Parse Retry-After delta-seconds or HTTP-date without shortening it."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if re.fullmatch(r"\d+(?:\.\d+)?", raw):
        try:
            delay = float(raw)
        except (ValueError, OverflowError):
            return None
    else:
        try:
            retry_at = email.utils.parsedate_to_datetime(raw)
            if retry_at is None:
                return None
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=datetime.timezone.utc)
            now = datetime.datetime.now(datetime.timezone.utc)
            delay = (retry_at.astimezone(datetime.timezone.utc) - now).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return None
    if delay != delay or delay in (float("inf"), float("-inf")):
        return None
    return max(0.0, delay)


def _session_cookie_redaction_values(cookie):
    if not cookie:
        return ()
    value = str(cookie).strip()
    result = [value]
    if "=" in value:
        raw = value.split("=", 1)[1].strip()
        if raw:
            result.append(raw)
    return tuple(result)


def _web_status_request_error(stage, exc, secrets=()):
    """Describe a failed HTTP request without recording response headers or secrets."""
    if isinstance(exc, urllib.error.HTTPError):
        parts = ["{0}: HTTPError HTTP {1}".format(stage, exc.code)]
        if exc.reason:
            parts.append("reason={0}".format(exc.reason))
        headers = exc.headers or {}
        value = headers.get("Content-Type")
        if value:
            parts.append("content_type={0}".format(value))
        retry_after = _retry_after_seconds(headers.get("Retry-After"))
        if retry_after is not None:
            parts.append("retry_after={0:g}".format(retry_after))
        try:
            body = exc.read(4096).decode("utf-8", "replace")
            if body:
                try:
                    parsed = json.loads(body)
                except ValueError:
                    parts.append("response_body={0} chars (not JSON)".format(len(body)))
                else:
                    if isinstance(parsed, dict):
                        parts.append("response_keys={0}".format(
                            _web_status_response_keys(parsed)))
                        if retry_after is None:
                            body_retry_after = _retry_after_seconds(
                                parsed.get("retry_after"))
                            if body_retry_after is not None:
                                parts.append("retry_after={0:g}".format(
                                    body_retry_after))
                        if parsed.get("error"):
                            parts.append("server_error={0}".format(
                                _web_status_value_summary(
                                    parsed.get("error"), secrets=secrets)))
                    else:
                        parts.append("response_json_type={0}".format(
                            type(parsed).__name__))
        except Exception:
            parts.append("response_body=unavailable")
        return _sanitize_web_status_detail("; ".join(parts), secrets=secrets)
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        description = "{0}: URLError reason={1}".format(stage, reason)
    else:
        description = "{0}: {1}: {2}".format(
            stage, type(exc).__name__, exc)
    return _sanitize_web_status_detail(description, secrets=secrets)


def web_status_log_path():
    return BASE / WEB_STATUS_LOG_NAME


def _web_status_log_entry(event, now=None, detail=None, secrets=(), language="en"):
    try:
        label = WEB_STATUS_LOG_EVENTS[event]
    except (KeyError, TypeError) as exc:
        raise ValueError("unknown activity") from exc
    if language == "th":
        label = WEB_STATUS_LOG_LABELS_TH.get(label, label)
    timestamp = now or datetime.datetime.now().astimezone()
    entry = "{0:%Y-%m-%d %H:%M:%S %z} | {1}".format(timestamp, label)
    if detail is not None:
        if event not in WEB_STATUS_LOG_DETAIL_EVENTS:
            raise ValueError(
                "details are only allowed for diagnostic or rotation events")
        sanitized = _sanitize_web_status_detail(detail, secrets=secrets)
        if sanitized:
            entry += " | " + sanitized
    return entry


def load_web_status_log(path=None):
    """Load only the bounded, most recent activity lines for the GUI."""
    log_path = Path(path) if path is not None else web_status_log_path()
    if not log_path.exists():
        return []
    with log_path.open("r", encoding="utf-8", errors="replace") as stream:
        return [line.rstrip("\r\n") for line in stream.readlines()[-WEB_STATUS_LOG_GUI_LINES:]
                if line.strip()]


def append_web_status_log(event, path=None, now=None, detail=None, secrets=(),
                          language="en"):
    """Append one allowlisted event with bounded, redacted details."""
    entry = _web_status_log_entry(
        event, now, detail=detail, secrets=secrets, language=language)
    log_path = Path(path) if path is not None else web_status_log_path()
    encoded = (entry + "\n").encode("utf-8")
    with _WEB_STATUS_LOG_LOCK:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            current_size = log_path.stat().st_size
        except FileNotFoundError:
            current_size = 0
        if current_size and current_size + len(encoded) > WEB_STATUS_LOG_MAX_BYTES:
            for backup in range(WEB_STATUS_LOG_BACKUPS, 1, -1):
                source = Path(str(log_path) + ".{0}".format(backup - 1))
                target = Path(str(log_path) + ".{0}".format(backup))
                if source.exists():
                    os.replace(source, target)
            os.replace(log_path, Path(str(log_path) + ".1"))
        with log_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(entry + "\n")
    return entry


_WEB_MARQUEE_LEAD_VOWELS = set("\u0e40\u0e41\u0e42\u0e43\u0e44")


def _web_status_clusters(text):
    """Keep Thai marks, emoji modifiers, and leading vowels with their base."""
    out, prefix = [], ""
    for char in text:
        if char in _WEB_MARQUEE_LEAD_VOWELS:
            prefix += char
            continue
        attach = (unicodedata.category(char) in ("Mn", "Mc", "Me")
                  or char in "\u200d\ufe0f\ufe0e"
                  or (out and out[-1].endswith("\u200d")))
        if out and not prefix and attach:
            out[-1] += char
        else:
            out.append(prefix + char)
            prefix = ""
    if prefix:
        out.append(prefix)
    return out


def web_status_frames(text, enabled=True):
    """Build a bounded ticker for one status slot, then settle on its full text."""
    value = str(text).strip()
    if not value:
        return []
    if not enabled:
        return [value]
    clusters = _web_status_clusters(value)
    if len(clusters) <= WEB_MARQUEE_WIDTH:
        return [value]
    ticker = clusters + _web_status_clusters(WEB_MARQUEE_SEPARATOR)
    steps = min(WEB_MARQUEE_MAX_FRAMES,
                max(1, (len(ticker) + WEB_MARQUEE_STRIDE - 1) // WEB_MARQUEE_STRIDE))
    frames = []
    for frame_no in range(steps):
        start = (frame_no * WEB_MARQUEE_STRIDE) % len(ticker)
        frame = "".join(ticker[(start + offset) % len(ticker)]
                        for offset in range(WEB_MARQUEE_WIDTH)).strip()
        if frame and (not frames or frame != frames[-1]):
            frames.append(frame)
    if not frames or frames[-1] != value:
        frames.append(value)
    return frames


def parse_rotate_interval(raw):
    """Auto-switch interval in seconds. Clamped to the allowed window."""
    try:
        value = float(str(raw).strip())
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("invalid interval: {0!r}".format(raw)) from exc
    if not (value == value and value not in (float("inf"), float("-inf"))):
        raise ValueError("invalid interval: {0!r}".format(raw))
    return min(ROTATE_INTERVAL_MAX, max(ROTATE_INTERVAL_MIN, value))


def parse_marquee_step_seconds(raw):
    """Frame delay in seconds. Clamp numeric values to the GUI's supported range."""
    try:
        value = float(str(raw).strip())
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("invalid marquee frame interval: {0!r}".format(raw)) from exc
    if not (value == value and value not in (float("inf"), float("-inf"))):
        raise ValueError("invalid marquee frame interval: {0!r}".format(raw))
    return min(WEB_MARQUEE_STEP_SECONDS_MAX,
               max(WEB_MARQUEE_STEP_SECONDS_MIN, value))


def parse_loop_count(raw):
    """Return a status-pool pass count; zero means no limit."""
    value = str(raw).strip()
    if not re.fullmatch(r"\d+", value):
        raise ValueError("loop rounds must be a whole number from 0 to {0}.".format(
            WEB_STATUS_LOOP_COUNT_MAX))
    count = int(value)
    if count > WEB_STATUS_LOOP_COUNT_MAX:
        raise ValueError("loop rounds must be a whole number from 0 to {0}.".format(
            WEB_STATUS_LOOP_COUNT_MAX))
    return count


parse_marquee_loop_count = parse_loop_count


def _web_status_retry_policy(detail, retry_attempt):
    """Return (reason, delay) for safe retries; otherwise return None.

    A 429 or Camfrog's hopping_too_fast response explicitly refused the update.
    A profile GET timeout is safe to retry because the status POST has not begun.
    POST timeouts are deliberately not retried because the server may have applied
    the status before the connection timed out.
    """
    message = str(detail)
    lowered = message.casefold()
    rate_limited = ("hopping_too_fast" in lowered
                    or re.search(r"\bHTTP\s+429\b", message, re.IGNORECASE))
    if rate_limited:
        retry_after = re.search(
            r"\bretry_after\s*=\s*([^\s;,]+)", message, re.IGNORECASE)
        if retry_after:
            delay = _retry_after_seconds(retry_after.group(1))
            if delay is not None:
                # A very long server cooldown must stop automation, not be
                # shortened to our local retry cap and retried prematurely.
                if delay > LIVE_RETRY_MAX_SERVER_WAIT_SECONDS:
                    return None
                return "rate_limit", max(LIVE_ROTATE_INTERVAL_MIN, delay)
        delay = LIVE_RATE_LIMIT_RETRY_BASE_SECONDS * (2 ** retry_attempt)
        return "rate_limit", min(
            LIVE_RETRY_MAX_DELAY_SECONDS,
            max(LIVE_ROTATE_INTERVAL_MIN, delay))
    profile_get = "get /home.php" in lowered
    profile_timeout = (profile_get
                       and ("timeouterror" in lowered or "timed out" in lowered))
    profile_transient_error = (profile_get and (
        "urlerror" in lowered
        or re.search(r"\bHTTPError\s+HTTP\s+5\d\d\b", message, re.IGNORECASE)))
    if profile_timeout or profile_transient_error:
        delay = LIVE_TIMEOUT_RETRY_BASE_SECONDS * (2 ** retry_attempt)
        return ("profile_timeout" if profile_timeout else "profile_request"), min(
            LIVE_RETRY_MAX_DELAY_SECONDS, delay)
    return None


def parse_pool(text):
    """Parse legacy multi-line pool text; the GUI uses ten numbered slots."""
    return [line.strip() for line in str(text).splitlines() if line.strip()]


WEB_TEXT_DB_NAME = "webtext.db"
WEB_TEXT_SLOT_COUNT = 10


def web_text_db_path():
    return BASE / WEB_TEXT_DB_NAME


def _web_text_lines(lines):
    values = [str(value) for value in list(lines)[:WEB_TEXT_SLOT_COUNT]]
    return values + [""] * (WEB_TEXT_SLOT_COUNT - len(values))


def load_web_text_lines(path=None):
    """Load the ten GUI status slots from the local webtext database."""
    database = Path(path) if path is not None else web_text_db_path()
    values = [""] * WEB_TEXT_SLOT_COUNT
    connection = sqlite3.connect(str(database), timeout=5.0)
    try:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS webtext ("
            "line_no INTEGER PRIMARY KEY CHECK(line_no BETWEEN 1 AND 10), "
            "text TEXT NOT NULL)")
        rows = connection.execute(
            "SELECT line_no, text FROM webtext ORDER BY line_no").fetchall()
        connection.commit()
    finally:
        connection.close()
    for line_no, text in rows:
        if 1 <= line_no <= WEB_TEXT_SLOT_COUNT:
            values[line_no - 1] = text
    return values


def load_web_text_slots(path=None):
    """Load GUI status slots, falling back without modifying an unreadable DB."""
    try:
        return load_web_text_lines(path), ""
    except (OSError, sqlite3.Error) as exc:
        return ([""] * WEB_TEXT_SLOT_COUNT,
                "Could not load webtext.db ({0}); status fields are empty. "
                "The existing database was left unchanged.".format(type(exc).__name__))


def save_web_text_lines(lines, path=None):
    """Save exactly ten single-line status slots to the local database."""
    database = Path(path) if path is not None else web_text_db_path()
    values = _web_text_lines(lines)
    connection = sqlite3.connect(str(database), timeout=5.0)
    try:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS webtext ("
            "line_no INTEGER PRIMARY KEY CHECK(line_no BETWEEN 1 AND 10), "
            "text TEXT NOT NULL)")
        with connection:
            connection.executemany(
                "INSERT OR REPLACE INTO webtext (line_no, text) VALUES (?, ?)",
                [(line_no, text) for line_no, text in enumerate(values, 1)])
    finally:
        connection.close()
    return WEB_TEXT_SLOT_COUNT


def next_rotation(pool, index):
    """Round-robin step. Returns (status, next_index). Empty pool -> ValueError."""
    if not pool:
        raise ValueError("status pool is empty; add at least one line.")
    return pool[index % len(pool)], (index + 1) % len(pool)


TIMEOUT_MIN = 2.0
TIMEOUT_DEFAULT = 15.0
TIMEOUT_MAX = 120.0


def parse_timeout(raw):
    """Network timeout in seconds, clamped to the allowed window."""
    try:
        value = float(str(raw).strip())
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("invalid timeout: {0!r}".format(raw)) from exc
    if not (value == value and value not in (float("inf"), float("-inf"))):
        raise ValueError("invalid timeout: {0!r}".format(raw))
    return min(TIMEOUT_MAX, max(TIMEOUT_MIN, value))


class WebStatusUpdateCancelled(Exception):
    """The operator stopped rotation before the status POST was sent."""


def _raise_if_update_cancelled(cancelled):
    if cancelled is not None and cancelled():
        raise WebStatusUpdateCancelled(
            "update cancelled before the status POST was sent")


def perform_update(opener, status, timeout, confirm=False, cancelled=None,
                   on_post_started=None):
    """Single gated send point for one rotation tick. Returns (ok, message).

    Reads the profile page for its per-session CSRF token, then POSTs the new
    status. Refuses unless confirm=True (fail closed until a live round-trip is
    confirmed by the operator).
    """
    if not confirm:
        return False, ("update refused: endpoint captured from home.php but not "
                       "confirmed end to end yet; pass --confirm-update to send "
                       "for real (dry-run preview only).")
    _raise_if_update_cancelled(cancelled)
    try:
        html = fetch_profile(opener, "", timeout)
    except WebStatusUpdateCancelled:
        raise
    except Exception as exc:
        return False, _web_status_request_error(
            "GET /home.php", exc, secrets=(status,))
    _raise_if_update_cancelled(cancelled)
    csrf = extract_csrf(html)
    if not csrf:
        return False, ("update refused: no CSRF token on the profile page "
                       "(session expired or not signed in); profile_chars={0}.".format(
                           len(html)))
    _raise_if_update_cancelled(cancelled)
    if on_post_started is not None:
        on_post_started()
    try:
        reply = _post(opener, WEB_UPDATE_URL,
                      {"status": status, "csrf": csrf}, timeout)
    except Exception as exc:
        return False, _web_status_request_error(
            "POST /ajax/update_status.php", exc, secrets=(status, csrf))
    response_context = []
    status_code = getattr(reply, "status_code", None)
    content_type = getattr(reply, "content_type", None)
    if status_code is not None:
        response_context.append("http_status={0}".format(status_code))
    if content_type:
        response_context.append("content_type={0}".format(content_type))
    retry_after = _retry_after_seconds(getattr(reply, "retry_after", None))
    if retry_after is not None:
        response_context.append("retry_after={0:g}".format(retry_after))
    if response_context:
        response_context = ["response " + ", ".join(response_context)]
    response_context.append("response_chars={0}".format(len(reply)))
    context = "; ".join(response_context)
    try:
        data = json.loads(reply)
    except (TypeError, ValueError) as exc:
        parser_detail = type(exc).__name__
        if isinstance(exc, json.JSONDecodeError):
            parser_detail += " ({0}, line={1}, column={2}, char={3})".format(
                exc.msg, exc.lineno, exc.colno, exc.pos)
        return False, "update refused: invalid JSON server reply; {0}; {1}.".format(
            parser_detail, context)
    if not isinstance(data, dict):
        return False, ("update refused: expected a JSON object but received {0}; "
                       "{1}.").format(type(data).__name__, context)
    if retry_after is None:
        retry_after = _retry_after_seconds(data.get("retry_after"))
        if retry_after is not None:
            context = "{0}; retry_after={1:g}".format(context, retry_after)
    if data.get("error"):
        response_summary = _web_status_error_response_summary(
            data.get("response", "missing"), secrets=(status, csrf))
        return False, ("update refused by the server; response_keys={0}; "
                       "error={1}; server_response={2}; {3}.").format(
                           _web_status_response_keys(data),
                           _web_status_value_summary(
                               data.get("error"), secrets=(status, csrf)),
                           response_summary, context)
    # Camfrog's profile form treats a non-empty response string as success and
    # writes it back into the status field. It does not require the literal "ok".
    response = data.get("response")
    if not isinstance(response, str) or not response.strip():
        response_type = "missing" if "response" not in data else type(response).__name__
        response_chars = (len(response) if isinstance(response, str) else "n/a")
        return False, ("update unconfirmed: server did not acknowledge success; "
                       "response_type={0}; response_chars={1}; response_keys={2}; "
                       "{3}.").format(
                           response_type, response_chars,
                           _web_status_response_keys(data), context)
    return True, "status update acknowledged by server."


def extract_csrf(html):
    """The per-session CSRF token embedded in the logged-in profile page."""
    match = re.search(r"var\s+csrf\s*=\s*['\"]([0-9a-fA-F]{16,})['\"]", html)
    return match.group(1) if match else ""

CAPTURE_STEPS = """\
To capture PHPSESSID from https://profiles.camfrog.com/home.php:
1. Log in at https://profiles.camfrog.com/ or https://www.camfrog.com/th/login.php.
2. Open devtools (F12) -> Network tab (preserve log / filter for "home.php").
3. Navigate to https://profiles.camfrog.com/home.php.
4. Click the 'home.php' request -> Headers -> Request Headers (Cookie) or Response Headers (set-cookie).
5. Copy the PHPSESSID value (e.g. PHPSESSID=xxxx... or just the token).
6. Paste into the Cookie/PHPSESSID box below and press 'Login' to arm automation.
"""

COOKIE_STEPS = """\
To capture the real status-update endpoint:
1. On https://profiles.camfrog.com/home.php, change your status once.
2. In devtools Network tab, find POST /ajax/update_status.php with {status, csrf}.
3. The session uses your authenticated PHPSESSID cookie.
"""

# Markers seen on the logged-out login wall (fetched 2026-10-09).
LOGGED_OUT_MARKERS = ("nav-btn-sign-on", ">Sign On<", "Logon to view",
                      "<title>Camfrog - Login Page</title>")
# Markers seen on the signed-in profile page home.php (fetched 2026-10-09).
SIGNED_IN_MARKERS = ("nav-user-logged", "var _user_id = ")

CHROME_DOMAINS = (".camfrog.com", "camfrog.com")
CHROME_ENV_OVERRIDE = "CAMFROG_CHROME_USER_DATA"


def build_parser():
    parser = argparse.ArgumentParser(
        description="Prototype web status updater (dry-run by default).")
    parser.add_argument("--login", required=False, help="Camfrog nickname")
    parser.add_argument("--status", required=False, help="new status text")
    parser.add_argument("--live", action="store_true",
                        help="attempt web login (password is prompted, never stored)")
    parser.add_argument("--cookies-file",
                        help="Netscape cookie.txt exported from Chrome; "
                             "enables --probe without any password")
    parser.add_argument("--chrome", action="store_true",
                        help="auto-import the session from Chrome's cookie store "
                             "(Windows only; nothing is written to disk)")
    parser.add_argument("--probe", action="store_true",
                        help="check the session read-only (no status change)")
    parser.add_argument("--confirm-update", action="store_true",
                        help="actually POST the status to the captured endpoint "
                             "(without it every run stays a dry-run)")
    parser.add_argument("--timeout", type=float, default=TIMEOUT_DEFAULT)
    parser.add_argument("--how-to-capture", action="store_true",
                        help="print how to capture the update endpoint and exit")
    return parser


def build_plan(login, status):
    return ("dry-run: would sign in as {login!r} at {url}, open {home} for the "
            "session CSRF token, and set the status to {n} chars.".format(
                login=login, url=LOGIN_URL, home=HOME_URL,
                n=len(status)))


def cookie_from_paste(text):
    """Build a jar from a pasted `name=value` browser cookie or PHPSESSID. Value stays in memory.

    This supports copying either the full cookie, name=value pairs, or capturing
    PHPSESSID from network inspection (e.g. headers or request/response on
    https://profiles.camfrog.com/home.php).
    """
    raw = str(text).strip()
    if not raw:
        raise ValueError(
            "paste a cookie as name=value or PHPSESSID=... (copy it from the "
            "network capture on profiles.camfrog.com/home.php or browser devtools).")

    pairs = []
    # If the user pasted something like 'PHPSESSID=xyz' directly or in cookie string
    for chunk in raw.replace(";", " ").split():
        if "=" in chunk:
            key, _, value = chunk.partition("=")
            key, value = key.strip(), value.strip()
            if key and value:
                pairs.append((key, value))

    # Also handle if user pasted just the raw PHPSESSID hash or 'PHPSESSID: xyz'
    if not pairs:
        m = re.search(r"PHPSESSID\s*[:=]\s*([a-zA-Z0-9_-]+)", raw, re.IGNORECASE)
        if m:
            pairs.append(("PHPSESSID", m.group(1)))
        elif re.fullmatch(r"[a-zA-Z0-9_-]{16,64}", raw):
            pairs.append(("PHPSESSID", raw))

    if not pairs:
        raise ValueError(
            "paste a cookie as name=value (copy PHPSESSID from devtools: "
            "Network -> home.php -> Headers/Cookies or Application -> Cookies).")
    jar = CookieJar()
    for key, value in pairs:
        jar.set_cookie(Cookie(
            version=0, name=key, value=value, port=None, port_specified=False,
            domain=".camfrog.com", domain_specified=True, domain_initial_dot=True,
            path="/", path_specified=True, secure=True, expires=None,
            discard=False, comment=None, comment_url=None, rest={}, rfc2109=False))
    return jar


def load_cookie_jar(path):
    """Load a Netscape cookie.txt export. Raises ValueError with a safe message."""
    if Path(path).name == ENV_ENC_NAME:
        raise ValueError(
            "that is your encrypted account (.env.enc), not a cookies export - "
            "use the Account section of the GUI (Save encrypted) and leave the "
            "cookies file empty, or export cookies with \"Get cookies.txt "
            "LOCALLY\" and pick that file.")
    jar = MozillaCookieJar(path)
    try:
        jar.load(ignore_discard=True, ignore_expires=True)
    except Exception as exc:
        raise ValueError(
            "cannot load cookies file: {0}: {1}. A cookies export must come from "
            "\"Get cookies.txt LOCALLY\" in Chrome (or the Chrome button with "
            "Chrome closed); the Account section needs no cookies at all.".format(
                type(exc).__name__, exc)) from exc
    if not len(jar):
        raise ValueError("cookies file holds no cookies; export camfrog.com cookies first.")
    return jar


def cookie_summary(jar):
    """Redacted summary: counts and domains only, never values."""
    domains = sorted({c.domain for c in jar})
    return "{0} cookies for: {1}".format(len(jar), ", ".join(domains))


def chrome_user_data_dir():
    override = os.environ.get(CHROME_ENV_OVERRIDE)
    if override:
        return override
    local = os.environ.get("LOCALAPPDATA", "")
    return os.path.join(local, "Google", "Chrome", "User Data") if local else ""


def find_chrome_profiles(user_data=""):
    """[(profile, Cookies-db-path)] for standard Chrome profiles, else []."""
    base = user_data or chrome_user_data_dir()
    if not base or not os.path.isdir(base):
        return []
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return []
    found = []
    for name in names:
        if name != "Default" and not name.startswith("Profile "):
            continue
        # Chrome 127+ keeps the cookie DB under Network/; older builds (<127)
        # used <profile>/Cookies. The Network file wins when both exist.
        db = os.path.join(base, name, "Network", "Cookies")
        if not os.path.isfile(db):
            db = os.path.join(base, name, "Cookies")
        if os.path.isfile(db):
            found.append((name, db))
    return found


def _data_blob(data):
    """DATA_BLOB for DPAPI with its backing buffer pinned to the struct.

    The pointer must stay valid while CryptUnprotectData runs; returning the
    bare cast of a temporary buffer would be a use-after-free.
    """
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char))]

    raw = bytes(data)
    backing = ctypes.create_string_buffer(raw)
    blob = DATA_BLOB(len(raw), ctypes.cast(backing, ctypes.POINTER(ctypes.c_char)))
    blob._backing = backing
    return blob


def dpapi_protect(data):
    """Windows DPAPI encrypt to a blob (this user, this machine).

    The result only decrypts under the same Windows user, so a copied
    .env.enc is useless elsewhere. Raises ValueError off-Windows.
    """
    import ctypes

    windll = getattr(ctypes, "windll", None)
    if windll is None:
        raise ValueError("DPAPI encrypt needs Windows")
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise ValueError("nothing to encrypt")
    in_blob = _data_blob(data)
    out = type(in_blob)()
    ok = windll.crypt32.CryptProtectData(
        ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out))
    if not ok:
        raise ValueError("DPAPI could not encrypt this data")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        try:
            windll.kernel32.LocalFree(out.pbData)
        except Exception:
            pass


def dpapi_unprotect(blob):
    """Windows DPAPI decrypt (ctypes, stdlib only). Raises ValueError off-Windows."""
    import ctypes

    windll = getattr(ctypes, "windll", None)
    if windll is None:
        raise ValueError("DPAPI decrypt needs Windows")
    if not isinstance(blob, (bytes, bytearray)) or not blob:
        raise ValueError("empty DPAPI blob")
    in_blob = _data_blob(blob)
    out = type(in_blob)()
    ok = windll.crypt32.CryptUnprotectData(
        ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out))
    if not ok:
        raise ValueError("DPAPI could not decrypt this cookie (different Windows user?)")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        try:
            windll.kernel32.LocalFree(out.pbData)
        except Exception:
            pass


def chrome_aes_key(user_data):
    """AES key for v10/v11 cookies from Chrome's Local State (DPAPI-wrapped)."""
    import base64
    import json

    path = os.path.join(user_data or chrome_user_data_dir(), "Local State")
    try:
        with open(path, encoding="utf-8") as handle:
            state = json.load(handle)
        raw = base64.b64decode(state["os_crypt"]["encrypted_key"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError("cannot read Chrome AES key from Local State: {0}".format(exc)) from exc
    if not raw.startswith(b"DPAPI"):
        raise ValueError("unexpected Chrome key wrapping (not DPAPI)")
    return dpapi_unprotect(raw[len(b"DPAPI"):])


def decrypt_chrome_value(blob, user_data=""):
    """Decrypt one Chrome cookie value. v10/v11 need the 'cryptography' package."""
    if blob is None:
        return ""
    if isinstance(blob, str):
        return blob
    if blob.startswith(b"v10") or blob.startswith(b"v11"):
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError as exc:
            raise ValueError("AES-encrypted Chrome cookie needs the 'cryptography' "
                             "package (pip install cryptography), or export "
                             "cookies.txt instead.") from exc
        key = chrome_aes_key(user_data)
        return AESGCM(key).decrypt(blob[3:15], blob[15:], None).decode("utf-8")
    return dpapi_unprotect(blob).decode("utf-8", "replace")


def _chrome_domain_match(host, domains=CHROME_DOMAINS):
    host = (host or "").lstrip(".").lower()
    return any(host == dom.lstrip(".").lower()
               or host.endswith("." + dom.lstrip(".").lower()) for dom in domains)


CHROME_LOCKED_MESSAGE = (
    "Chrome is running and holds its cookie file closed to every other process "
    "(sharing violation). Close Chrome and retry, export cookies with \"Get "
    "cookies.txt LOCALLY\" and pass --cookies-file, or skip cookies entirely: "
    "save your account in the GUI (Account / Save encrypted) and run without "
    "--chrome.")


def read_cookie_rows(db):
    """All rows of a Chrome cookie DB via a temp snapshot copy.

    Chrome opens its cookie DB exclusively (sharing violation, error 32), so the
    copy only succeeds while Chrome is closed; the caller reports
    CHROME_LOCKED_MESSAGE instead of guessing. Nothing is written next to the DB.
    """
    query = ("SELECT host_key, name, value, encrypted_value, path, "
             "is_secure, expires_utc FROM cookies")
    try:
        with tempfile.TemporaryDirectory(prefix="camfrog-chrome-") as tmp:
            snapshot = os.path.join(tmp, "Cookies")
            shutil.copyfile(db, snapshot)
            connection = sqlite3.connect(snapshot)
            try:
                return connection.execute(query).fetchall()
            finally:
                connection.close()
    except PermissionError as exc:
        raise ValueError(CHROME_LOCKED_MESSAGE) from exc


def import_chrome_jar(user_data="", domains=CHROME_DOMAINS):
    """Build a CookieJar from Chrome's cookie store. Nothing is written to disk.

    Only camfrog.com cookies are imported; values stay in memory.
    Raises ValueError with a safe (value-free) message on any failure.
    """
    profiles = find_chrome_profiles(user_data)
    if not profiles:
        raise ValueError("no Chrome cookie store found; is Chrome installed "
                         "with a Default/Profile directory?")
    jar = CookieJar()
    notes = []
    for profile, db in profiles:
        try:
            rows = read_cookie_rows(db)
        except ValueError as exc:
            notes.append(str(exc))  # our own value-free guidance
            continue
        except Exception as exc:
            notes.append("{0}: {1}".format(profile, type(exc).__name__))
            continue
        for host, name, value, encrypted, path, secure, _expires in rows:
            if not _chrome_domain_match(host, domains) or not name:
                continue
            try:
                text = value if value else decrypt_chrome_value(encrypted, user_data)
            except Exception as exc:
                notes.append("{0}/{1}: {2}".format(profile, name, exc))
                continue
            jar.set_cookie(Cookie(
                version=0, name=name, value=text, port=None, port_specified=False,
                domain=host, domain_specified=host.startswith("."),
                domain_initial_dot=host.startswith("."), path=path or "/",
                path_specified=True, secure=bool(secure), expires=None,
                discard=False, comment=None, comment_url=None, rest={}, rfc2109=False))
    if not len(jar):
        detail = "; ".join(notes[:3])
        raise ValueError("no usable camfrog.com cookies in Chrome profiles"
                         + (" ({0})".format(detail) if detail else
                            "; log in at profiles.camfrog.com first"))
    return jar


def fetch_profile(opener, login, timeout):
    """The signed-in landing page: session markers plus the CSRF token."""
    request = urllib.request.Request(HOME_URL, headers=dict(
        BROWSER_HEADERS, Referer=HOME_URL))
    with opener.open(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def summarize_session(html):
    """Read-only verdict on an exported session. Never claims verified blindly."""
    match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = (match.group(1).strip() if match else "?")[:80]
    if any(marker in html for marker in LOGGED_OUT_MARKERS):
        return ("logged-out",
                "session is NOT signed in (page: {0!r}); log in via Chrome and "
                "re-export cookies.".format(title))
    user = re.search(r"var\s+_user_id\s*=\s*['\"](\d+)['\"]", html)
    nick = re.search(r"var\s+nick\s*=\s*['\"]([^'\"]+)['\"]", html)
    if user and nick:
        return ("signed-in",
                "session is signed in as {0!r} (user id {1}, page {2!r}).".format(
                    nick.group(1), user.group(1), title))
    return ("unconfirmed",
            "no login wall found (page: {0!r}, {1} chars) but no signed-in marker "
            "either; confirm visually before any live use.".format(title, len(html)))


def _post(opener, url, fields, timeout):
    data = urllib.parse.urlencode(fields).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=dict(
        BROWSER_HEADERS, Referer=LOGIN_PAGE_URL))
    with opener.open(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", "replace").strip()
        headers = getattr(response, "headers", None)
        content_type = headers.get("Content-Type") if headers is not None else None
        retry_after = headers.get("Retry-After") if headers is not None else None
        return WebStatusReply(
            body, status_code=getattr(response, "status", None)
            or (response.getcode() if hasattr(response, "getcode") else None),
            content_type=content_type, retry_after=retry_after)


class WebStatusReply(str):
    """Text response with only non-sensitive HTTP metadata used for diagnostics."""

    def __new__(cls, value, status_code=None, content_type=None, retry_after=None):
        reply = super().__new__(cls, value)
        reply.status_code = status_code
        reply.content_type = content_type
        reply.retry_after = retry_after
        return reply


def attempt_login(opener, login, password, timeout):
    """POST credentials. Returns the raw server reply (never logs the password)."""
    return _post(opener, LOGIN_URL, {
        "login": login,
        "passwd": password,
        "save": "0",
        "code": "",
    }, timeout)


def stored_account():
    """(login, password) from the encrypted store / environment, if any."""
    user = (os.environ.get("CAMFROG_USER") or "").strip()
    password = os.environ.get("CAMFROG_PASSWORD") or ""
    return (user, password) if user and password else None


def live_update(login, password, status, timeout, confirm=False):
    """Password path: sign in, then the gated status update. Returns (code, message).

    Needs no cookies and no Chrome. `confirm` is the explicit operator consent
    (the CLI --confirm-update flag, or an armed live start in the GUI).
    """
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    try:
        reply = attempt_login(opener, login, password, timeout)
    except Exception as exc:
        return EXIT_USAGE, "login request failed: {0}: {1}".format(
            type(exc).__name__, exc)
    finally:
        del password
    code, message = handle_login_reply(reply)
    if not (code == EXIT_BLOCKED and reply.startswith("http")):
        return code, message  # wrong password, captcha, ban, server error...
    try:
        html = fetch_profile(opener, login, timeout)
    except Exception as exc:
        return EXIT_USAGE, "profile page failed: {0}: {1}".format(
            type(exc).__name__, exc)
    verdict, detail = summarize_session(html)
    if verdict != "signed-in":
        guidance = (" Use --confirm-update for live changes; a verified signed-in "
                    "session is also required.") if not confirm else ""
        return EXIT_BLOCKED, "status update blocked: session not confirmed signed in." + guidance
    ok, update_message = perform_update(opener, status, timeout, confirm=confirm)
    return (EXIT_OK if ok else EXIT_BLOCKED), "{0}\n{1}".format(detail, update_message)


def handle_login_reply(reply):
    """Map the login/check.php reply to (exit_code, message). No secrets involved."""
    if reply == "password":
        return EXIT_USAGE, "web login failed: nickname or password incorrect."
    if reply.startswith("ban:"):
        return EXIT_USAGE, "web login refused by the server (ban response)."
    if reply == "captcha":
        return EXIT_BLOCKED, ("web login blocked: the server requires a CAPTCHA "
                              "token and this tool does not bypass it.")
    if reply in ("privacy", "under_16"):
        return EXIT_BLOCKED, "web login blocked: server replied {0!r}.".format(reply)
    if reply.startswith("http"):
        return EXIT_BLOCKED, ("logged in, but the status update was not confirmed: "
                              "re-run with --confirm-update to POST it for real.")
    return EXIT_USAGE, "web login failed: unexpected server reply."


ENV_ENC_NAME = ".env.enc"


def env_enc_path():
    return BASE / ENV_ENC_NAME


def load_dotenv(path):
    """Load credentials into os.environ: the DPAPI-encrypted .env.enc first,
    then a plaintext .env (legacy). Existing environment variables always win,
    and values are never logged.

    .env.enc is written by the GUI account setup (Save encrypted) and only
    decrypts under the Windows user that saved it.
    """
    if load_env_enc():
        return True
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except OSError:
        return False
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not key or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ[key] = value
    return True


def save_credentials(user, password):
    """Encrypt the account into .env.enc (DPAPI). Returns (ok, message).

    Nothing is logged; the plaintext never touches the disk.
    """
    import base64

    user, password = str(user).strip(), str(password)
    if not user or not password:
        return False, "enter both the nickname and the password."
    try:
        blob = dpapi_protect(
            "CAMFROG_USER={0}\nCAMFROG_PASSWORD={1}\n".format(
                user, password).encode("utf-8"))
        env_enc_path().write_text(
            base64.b64encode(blob).decode("ascii") + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        return False, "could not save the encrypted account: {0}".format(exc)
    return True, ("saved the encrypted account for {0!r} "
                  "(this Windows user only).").format(user)


def load_env_enc():
    """Decrypt .env.enc into os.environ. Returns True when it was used."""
    import base64

    path = env_enc_path()
    if not path.is_file():
        return False
    try:
        blob = base64.b64decode(path.read_text(encoding="utf-8").strip())
        text = dpapi_unprotect(blob).decode("utf-8", "replace")
    except (OSError, ValueError):
        return False
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value
    return True


def cli_main(argv=None):
    load_dotenv(BASE / ".env")
    args = build_parser().parse_args(argv)
    if args.how_to_capture:
        print(CAPTURE_STEPS)
        print(COOKIE_STEPS)
        return EXIT_OK
    if not args.login:
        args.login = (os.environ.get("CAMFROG_USER") or "").strip()
    if not args.login or not args.status:
        build_parser().error("--login and --status are required "
                             "(or set CAMFROG_USER in .env)")
    if not args.status.strip():
        print("refusing empty status text.")
        return EXIT_USAGE
    if args.probe:
        if args.chrome and args.cookies_file:
            build_parser().error("use only one of --chrome and --cookies-file")
        try:
            if args.chrome:
                jar = import_chrome_jar()
                print("loaded session from Chrome: {0}".format(cookie_summary(jar)))
            elif args.cookies_file:
                jar = load_cookie_jar(args.cookies_file)
                print("loaded session: {0}".format(cookie_summary(jar)))
            else:
                build_parser().error("--probe requires --cookies-file or --chrome")
        except (OSError, ValueError) as exc:
            print(exc)
            return EXIT_USAGE
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        try:
            html = fetch_profile(opener, args.login, args.timeout)
        except Exception as exc:
            print("session probe failed: {0}: {1}".format(type(exc).__name__, exc))
            return EXIT_USAGE
        _verdict, detail = summarize_session(html)
        print(detail)
        print("no status was changed (read-only probe).")
        return EXIT_OK
    if not args.live:
        print(build_plan(args.login, args.status))
        return EXIT_OK
    env_password = os.environ.get("CAMFROG_PASSWORD")
    if env_password:
        password = env_password  # from .env / environment; never printed or logged
        print("using the CAMFROG_PASSWORD from the environment (value not shown).")
    else:
        try:
            password = getpass.getpass("Camfrog password for {0!r}: ".format(args.login))
        except (EOFError, KeyboardInterrupt):
            print("password prompt cancelled; nothing was sent.")
            return EXIT_USAGE
    if not password:
        print("empty password; nothing was sent.")
        return EXIT_USAGE
    code, message = live_update(args.login, password, args.status, args.timeout,
                                confirm=args.confirm_update)
    print(message)
    return code





# ============================================================
# GUI (from web_status_gui.py).
# ============================================================






def wants_gui(argv):
    """No CLI args -> GUI mode. Headless-safe (no tkinter needed)."""
    return not list(argv)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if wants_gui(argv):
        manager = WebStatusManager()
        manager.root.mainloop()
        return 0
    if getattr(sys, "stdout", None) is None:
        return run_cli_headless(argv)  # frozen --windowed: no console to print to
    return cli_main(argv)


def run_cli_headless(argv, show=None):
    """Run the CLI with output captured into a dialog (windowed exe, no console)."""
    import contextlib
    import io

    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            code = cli_main(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 2
    except Exception as exc:  # never a silent no-op
        code = 2
        buf.write("failed: {0}: {1}".format(type(exc).__name__, exc))
    text = buf.getvalue().strip() or "(no output)"
    if show is None:
        from tkinter import messagebox

        show = messagebox.showinfo
    show("Web Status", text)
    return code


_CLIPBOARD_WIDGET_CLASSES = {
    "Entry", "TEntry", "TCombobox", "Spinbox", "TSpinbox", "Text",
}
_CLIPBOARD_EDITABLE_CLASSES = {
    "Entry", "TEntry", "TCombobox", "Spinbox", "TSpinbox", "Text",
}


def _windows_open_clipboard(clipboard, attempts=20, interval=0.025):
    """Retry briefly while another Windows process holds the clipboard."""
    last_error = None
    for attempt in range(attempts):
        try:
            clipboard.OpenClipboard(None)
            return
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(interval)
    raise OSError("Could not open the Windows clipboard: {0}".format(
        type(last_error).__name__ if last_error else "unknown error")) from last_error


def _read_clipboard_text(root):
    """Read text through Win32 first, with Tk as a portable fallback."""
    clipboard_error = None
    if os.name == "nt":
        try:
            import win32clipboard
            import win32con
        except ImportError:
            pass
        else:
            try:
                _windows_open_clipboard(win32clipboard)
                try:
                    if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                        value = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                        return value if isinstance(value, str) else str(value)
                    if win32clipboard.IsClipboardFormatAvailable(win32con.CF_TEXT):
                        value = win32clipboard.GetClipboardData(win32con.CF_TEXT)
                        if isinstance(value, bytes):
                            value = value.decode("mbcs", errors="replace")
                        return value if isinstance(value, str) else str(value)
                finally:
                    win32clipboard.CloseClipboard()
            except Exception as exc:
                clipboard_error = exc

    try:
        return str(root.clipboard_get())
    except Exception as exc:
        if clipboard_error is not None:
            raise OSError("Could not read the system clipboard ({0}).".format(
                type(clipboard_error).__name__)) from clipboard_error
        raise OSError("Could not read text from the system clipboard.") from exc


def _write_clipboard_text(root, value):
    """Write text through Win32 first, with Tk as a portable fallback."""
    text = str(value)
    clipboard_error = None
    if os.name == "nt":
        try:
            import win32clipboard
            import win32con
        except ImportError:
            pass
        else:
            try:
                _windows_open_clipboard(win32clipboard)
                try:
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
                finally:
                    win32clipboard.CloseClipboard()
                return
            except Exception as exc:
                clipboard_error = exc

    try:
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update_idletasks()
    except Exception as exc:
        if clipboard_error is not None:
            raise OSError("Could not write the Windows clipboard ({0}).".format(
                type(clipboard_error).__name__)) from clipboard_error
        raise OSError("Could not write text to the system clipboard.") from exc


def _clipboard_widget_class(widget):
    try:
        return widget.winfo_class()
    except Exception:
        return ""


def _clipboard_widget_editable(widget):
    if _clipboard_widget_class(widget) not in _CLIPBOARD_EDITABLE_CLASSES:
        return False
    try:
        return str(widget.cget("state")) not in {"disabled", "readonly"}
    except Exception:
        return True


class WebStatusClipboardController:
    """Bind layout-independent copy, select-all, and paste shortcuts to GUI fields."""

    def __init__(self, root, on_error=None, translate=None):
        import tkinter as tk

        self.root = root
        self.on_error = on_error
        self.translate = translate or (lambda key: key)
        self.target = None
        self.menu = tk.Menu(root, tearoff=False)
        self.menu.add_command(label=self.translate("clipboard_cut"), command=self.cut_target)
        self.menu.add_command(label=self.translate("clipboard_copy"), command=self.copy_target)
        self.menu.add_command(label=self.translate("clipboard_paste"), command=self.paste_target)
        self.menu.add_separator()
        self.menu.add_command(label=self.translate("clipboard_select_all"),
                              command=self.select_all_target)

    def install(self, parent):
        for widget in parent.winfo_children():
            if _clipboard_widget_class(widget) in _CLIPBOARD_WIDGET_CLASSES:
                if _clipboard_widget_class(widget) == "Text":
                    try:
                        widget.configure(
                            background=WEB_STATUS_THEME["entry"],
                            foreground=WEB_STATUS_THEME["log_text"],
                            insertbackground=WEB_STATUS_THEME["gold"],
                            selectbackground=WEB_STATUS_THEME["border"],
                            selectforeground=WEB_STATUS_THEME["text"])
                    except Exception:
                        pass
                for sequence in ("<Control-v>", "<Control-V>", "<Shift-Insert>"):
                    widget.bind(sequence, self.handle, add="+")
                # Some Windows layouts (including Thai) report Ctrl shortcuts
                # with keysym "??". Match their control characters or VK codes.
                widget.bind("<Control-KeyPress>", self.handle_control_key, add="+")
                widget.bind("<Button-3>", self.show_menu, add="+")
            self.install(widget)

    def handle(self, event):
        self.target = event.widget
        self.paste(self.target)
        return "break"

    def handle_control_key(self, event):
        """Handle Ctrl+A/C/V/X when the active layout changes its keysyms."""
        keysym = str(getattr(event, "keysym", "")).lower()
        char = str(getattr(event, "char", "") or "")
        try:
            keycode = int(getattr(event, "keycode", -1))
        except (TypeError, ValueError):
            keycode = -1
        shortcuts = {
            "a": ({"a", "\x01"}, 65),
            "c": ({"c", "\x03"}, 67),
            "v": ({"v", "\x16"}, 86),
            "x": ({"x", "\x18"}, 88),
        }
        shortcut = next((name for name, (chars, code) in shortcuts.items()
                         if keysym == name or char in chars or keycode == code), None)
        if shortcut is None:
            return None

        self.target = event.widget
        if shortcut == "a":
            self.select_all(self.target)
        elif shortcut == "v":
            self.paste(self.target)
        elif shortcut == "x":
            self.cut(self.target)
        else:
            self.copy(self.target)
        return "break"

    def select_all(self, widget):
        if _clipboard_widget_class(widget) not in _CLIPBOARD_WIDGET_CLASSES:
            return False
        try:
            widget.focus_set()
            if _clipboard_widget_class(widget) == "Text":
                widget.tag_remove("sel", "1.0", "end")
                widget.tag_add("sel", "1.0", "end-1c")
                widget.mark_set("insert", "end-1c")
                widget.see("insert")
            else:
                widget.selection_range(0, "end")
                widget.icursor("end")
            return True
        except Exception as exc:
            if self.on_error:
                self.on_error(exc)
            return False

    def copy(self, widget):
        if _clipboard_widget_class(widget) not in _CLIPBOARD_WIDGET_CLASSES:
            return False
        try:
            if _clipboard_widget_class(widget) == "Text":
                if not widget.tag_ranges("sel"):
                    return False
                value = widget.get("sel.first", "sel.last")
            else:
                if not widget.selection_present():
                    return False
                start = widget.index("sel.first")
                end = widget.index("sel.last")
                value = widget.get()[start:end]
            if not value:
                return False
            _write_clipboard_text(self.root, value)
            return True
        except Exception as exc:
            if self.on_error:
                self.on_error(exc)
            return False

    def cut(self, widget):
        """Copy and then remove the current selection from an editable field."""
        if not _clipboard_widget_editable(widget):
            return False
        try:
            widget_class = _clipboard_widget_class(widget)
            has_selection = (bool(widget.tag_ranges("sel")) if widget_class == "Text"
                             else bool(widget.selection_present()))
            if not has_selection or not self.copy(widget):
                return False
            widget.delete("sel.first", "sel.last")
            return True
        except Exception as exc:
            if self.on_error:
                self.on_error(exc)
            return False

    def cut_target(self):
        self.cut(self.target)

    def copy_target(self):
        self.copy(self.target)

    def select_all_target(self):
        self.select_all(self.target)

    def paste_target(self):
        self.paste(self.target)

    def paste(self, widget):
        if widget is None or not _clipboard_widget_editable(widget):
            return False
        try:
            value = _read_clipboard_text(self.root)
            if not value:
                raise ValueError("The system clipboard does not contain text.")
            widget_class = _clipboard_widget_class(widget)
            if widget_class == "Text":
                if widget.tag_ranges("sel"):
                    widget.delete("sel.first", "sel.last")
                widget.insert("insert", value)
            else:
                if widget.selection_present():
                    widget.delete("sel.first", "sel.last")
                widget.insert("insert", value)
            return True
        except Exception as exc:
            if self.on_error:
                self.on_error(exc)
            return False

    def show_menu(self, event):
        self.target = event.widget
        self.target.focus_set()
        for index, key in enumerate(("clipboard_cut", "clipboard_copy", "clipboard_paste")):
            self.menu.entryconfigure(index, label=self.translate(key))
        self.menu.entryconfigure(4, label=self.translate("clipboard_select_all"))
        widget_class = _clipboard_widget_class(self.target)
        try:
            selected = (bool(self.target.tag_ranges("sel")) if widget_class == "Text"
                        else bool(self.target.selection_present()))
        except Exception:
            selected = False
        editable = _clipboard_widget_editable(self.target)
        self.menu.entryconfigure(0, state="normal" if editable and selected else "disabled")
        self.menu.entryconfigure(1, state="normal" if selected else "disabled")
        self.menu.entryconfigure(2, state="normal" if editable else "disabled")
        self.menu.entryconfigure(4, state="normal" if widget_class in _CLIPBOARD_WIDGET_CLASSES
                                 else "disabled")
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        except Exception as exc:
            if self.on_error:
                self.on_error(exc)
        finally:
            try:
                self.menu.grab_release()
            except Exception:
                pass
        return "break"


WEB_STATUS_LANGUAGE_TEXT = {
    "en": {
        "intro": ("Update status via profiles.camfrog.com. Dry-run is the default; "
                  "nothing is sent unless Send live is on. Passwords and cookie values "
                  "are never stored, logged, or shown."),
        "setup": "Setup",
        "account_session": "Account & Session",
        "activity_log": "Activity Log",
        "nickname": "Nickname",
        "status_lines": "Status lines",
        "save_status": "Save to webtext.db",
        "switch_every": "Switch every",
        "seconds_live_min": "s (live min 10)",
        "timeout": "Timeout",
        "send_live": "Send live (otherwise dry-run preview only)",
        "loop_rounds": "Loop rounds",
        "infinite": "0 = infinite",
        "session_title": "Session (PHPSESSID via iframe / web login)",
        "session_help": ("Log in in your browser (via iframe/web login). In devtools Network tab, "
                         "inspect https://profiles.camfrog.com/home.php to get PHPSESSID=..., "
                         "paste below, then press 'Login' to verify and arm automation."),
        "open_login": "Open login page",
        "login": "Login",
        "browser_login": "Login in browser",
        "cloudbot_login": "Connect via cloudbot",
        "cloudbot_param": "Cloudbot parameter",
        "preview_plan": "Preview plan",
        "probe_session": "Probe session",
        "update": "Update",
        "bot_manager": "Bot manager",
        "start": "Start",
        "stop": "Stop",
        "capture_help": "How to capture",
        "clipboard_cut": "Cut",
        "clipboard_copy": "Copy",
        "clipboard_paste": "Paste",
        "clipboard_select_all": "Select all",
        "ready_note": "Dry-run is on. Nothing has been sent.",
        "capture_instructions": CAPTURE_STEPS + COOKIE_STEPS,
        "confirm_title": "Send for real?",
        "confirm_start": ("This will sign in and POST your status to Camfrog for real.\n"
                           "Continue?"),
        "confirm_after_login": ("Logged in. This will POST your status to Camfrog for real.\n"
                                "Continue?"),
    },
    "th": {
        "intro": ("อัปเดตสถานะผ่าน profiles.camfrog.com ค่าเริ่มต้นเป็นโหมดทดลอง "
                  "ระบบจะไม่ส่งข้อมูลจริงจนกว่าจะเปิดส่งสถานะจริง และจะไม่บันทึกรหัสผ่านหรือ cookie"),
        "setup": "ตั้งค่า",
        "account_session": "บัญชีและเซสชัน",
        "activity_log": "บันทึกกิจกรรม",
        "bot_manager": "ตัวจัดการบอท",
        "nickname": "ชื่อเล่น",
        "status_lines": "ข้อความสถานะ",
        "save_status": "บันทึกลง webtext.db",
        "switch_every": "สลับทุก",
        "seconds_live_min": "วินาที (Live ขั้นต่ำ 10)",
        "timeout": "หมดเวลา",
        "send_live": "ส่งสถานะจริง (ปิด = แสดงตัวอย่างเท่านั้น)",
        "loop_rounds": "จำนวนรอบ",
        "infinite": "0 = ไม่จำกัด",
        "session_title": "เซสชัน (PHPSESSID ผ่าน iframe / เว็บ)",
        "session_help": ("เข้าสู่ระบบในเบราว์เซอร์ แล้วเปิดแท็บ Network ในเครื่องมือ devtools "
                         "ตรวจคำขอ https://profiles.camfrog.com/home.php เพื่อหา PHPSESSID=... "
                         "วางค่าในช่องด้านล่าง แล้วกด Login เพื่อตรวจสอบเซสชัน"),
        "open_login": "เปิดหน้าเข้าสู่ระบบ",
        "login": "ตรวจสอบ Login",
        "browser_login": "เข้าสู่ระบบในเบราว์เซอร์",
        "cloudbot_login": "เชื่อมต่อผ่าน cloudbot",
        "cloudbot_param": "พารามิเตอร์ cloudbot",
        "preview_plan": "ดูตัวอย่างแผน",
        "probe_session": "ตรวจสอบเซสชัน",
        "update": "อัปเดต",
        "start": "เริ่ม",
        "stop": "หยุด",
        "capture_help": "วิธีรับ PHPSESSID",
        "clipboard_cut": "ตัด",
        "clipboard_copy": "คัดลอก",
        "clipboard_paste": "วาง",
        "clipboard_select_all": "เลือกทั้งหมด",
        "ready_note": "โหมดทดลองเปิดอยู่ ยังไม่มีการส่งสถานะ",
        "capture_instructions": ("วิธีรับ PHPSESSID จาก https://profiles.camfrog.com/home.php:\n"
                                 "1. เข้าสู่ระบบที่ https://profiles.camfrog.com/ หรือหน้าเข้าสู่ระบบ Camfrog\n"
                                 "2. กด F12 แล้วเปิดแท็บ Network\n"
                                 "3. เปิด https://profiles.camfrog.com/home.php\n"
                                 "4. เลือกคำขอ home.php แล้วดู Headers ใน Request Headers (Cookie) "
                                 "หรือ Response Headers (set-cookie)\n"
                                 "5. คัดลอกค่า PHPSESSID=... หรือคัดลอกเฉพาะ token\n"
                                 "6. วางในช่อง PHPSESSID แล้วกด Login\n\n"
                                 "วิธีตรวจ endpoint อัปเดตสถานะ:\n"
                                 "1. เปลี่ยนสถานะหนึ่งครั้งจากหน้า home.php\n"
                                 "2. ในแท็บ Network หา POST /ajax/update_status.php ที่มี {status, csrf}\n"
                                 "3. คำขอใช้ cookie PHPSESSID ของบัญชีที่เข้าสู่ระบบแล้ว"),
        "confirm_title": "ยืนยันการส่งจริง",
        "confirm_start": "ระบบจะเข้าสู่ระบบและส่งสถานะไปยัง Camfrog จริง\nดำเนินการต่อหรือไม่?",
        "confirm_after_login": "เข้าสู่ระบบแล้ว ระบบจะส่งสถานะไปยัง Camfrog จริง\nดำเนินการต่อหรือไม่?",
    },
}


class WebStatusManager:
    def __init__(self, cookies_default=""):
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.ttk = ttk
        self._language = "th"
        self._language_widgets = []
        self._note_source = ""
        self._note_key = None
        self._paste_state_source = ""
        self._paste_state_color = WEB_STATUS_THEME["muted"]
        self.q = queue.Queue()
        self.busy = False
        self.switching = False
        self.rotate_job = None
        self.chrome_mode = False
        self.cookie_paste = ""
        self._cookie_from_browser = False
        self.session_ready = False
        self._pending = None
        self._start_generation = 0
        self._closed = False
        load_dotenv(BASE / ".env")  # pick up the encrypted account, if saved
        self.root = self.tk.Tk()
        style = self.ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except self.tk.TclError:
            pass
        self._apply_theme(style)
        self.root.title("Camfrog Web Status | Control Studio")
        self.root.geometry("600x700")
        self.root.minsize(540, 620)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        header = self.ttk.Frame(self.root)
        header.pack(fill="x", padx=16, pady=(12, 8))
        heading = self.ttk.Frame(header)
        heading.pack(fill="x")
        self.ttk.Label(
            heading, text="CAMFROG  /  WEB STATUS",
            style="Brand.TLabel").pack(side="left", fill="x", expand=True)
        self.language_button = self.ttk.Button(
            heading, text="TH / EN", width=8, command=self.switch_language)
        self.language_button.pack(side="right", anchor="n", padx=(6, 0))
        self._language_label(
            header, "intro", style="Hint.TLabel", wraplength=550).pack(
                fill="x", pady=(5, 0))
        self.ttk.Separator(self.root, orient="horizontal").pack(
            fill="x", padx=16, pady=(0, 8))

        self.nb = self.ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=14)
        setup_tab = self.ttk.Frame(self.nb, padding=(10, 6, 10, 6))
        session_tab = self.ttk.Frame(self.nb, padding=(10, 6, 10, 6))
        log_tab = self.ttk.Frame(self.nb, padding=(8, 6, 8, 6))
        self.nb.add(setup_tab, text=self._text("setup"))
        self._register_language_widget(setup_tab, "setup", notebook_tab=True)
        self.nb.add(session_tab, text=self._text("account_session"))
        self._register_language_widget(session_tab, "account_session", notebook_tab=True)
        # Add bot manager tab
        self.nb.add(log_tab, text=self._text("activity_log"))
        self._register_language_widget(log_tab, "activity_log", notebook_tab=True)
        # Bot manager tab
        bot_manager_tab = self.ttk.Frame(self.nb, padding=(10, 6, 10, 6))
        self.nb.add(bot_manager_tab, text=self._text("bot_manager"))
        self._register_language_widget(bot_manager_tab, "bot_manager", notebook_tab=True)
        pool_lines, pool_load_warning = load_web_text_slots()

        form = self.ttk.Frame(setup_tab)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        self._language_label(form, "nickname").grid(row=0, column=0, sticky="w")
        self.login = self.tk.StringVar(value="Seaza")
        self.ttk.Entry(form, textvariable=self.login).grid(row=0, column=1, sticky="ew", padx=6)
        self._language_label(form, "status_lines").grid(
            row=1, column=0, sticky="nw", pady=(5, 0))
        pool_frame = self.ttk.Frame(form)
        pool_frame.grid(row=1, column=1, sticky="ew", padx=6, pady=(5, 0))
        self.pool_vars = []
        self.pool_entries = []
        for column in range(2):
            pool_frame.columnconfigure(column, weight=1)
        for slot in range(WEB_TEXT_SLOT_COUNT):
            cell = self.ttk.Frame(pool_frame)
            cell.grid(row=slot % 5, column=slot // 5, sticky="ew",
                      padx=(0, 8), pady=2)
            self.ttk.Label(cell, text="{0}.".format(slot + 1), width=3).pack(side="left")
            variable = self.tk.StringVar(value=pool_lines[slot])
            entry = self.ttk.Entry(cell, textvariable=variable, width=18)
            entry.pack(side="left", fill="x", expand=True)
            self.pool_vars.append(variable)
            self.pool_entries.append(entry)
        pool_btns = self.ttk.Frame(form)
        pool_btns.grid(row=1, column=2, sticky="n", pady=(5, 0))
        self.btn_save_web_text = self._language_button(
            pool_btns, "save_status", command=self.save_web_texts)
        self.btn_save_web_text.pack(fill="x")
        self._language_label(form, "switch_every").grid(
            row=2, column=0, sticky="w", pady=(5, 0))
        timing = self.ttk.Frame(form)
        timing.grid(row=2, column=1, sticky="w", padx=6, pady=(5, 0))
        self.interval = self.tk.StringVar(value=str(ROTATE_INTERVAL_DEFAULT))
        self.ttk.Spinbox(timing, textvariable=self.interval,
                         from_=ROTATE_INTERVAL_MIN, to=ROTATE_INTERVAL_MAX,
                         increment=0.5, width=6).pack(side="left")
        self._language_label(timing, "seconds_live_min").pack(side="left", padx=(4, 0))
        self._language_label(timing, "timeout").pack(side="left", padx=(10, 0))
        self.timeout = self.tk.StringVar(value=str(TIMEOUT_DEFAULT))
        self.ttk.Entry(timing, textvariable=self.timeout, width=6).pack(side="left", padx=(3, 0))
        self.live = self.tk.BooleanVar(value=False)
        self._language_checkbutton(
            form, "send_live", variable=self.live).grid(
                row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))
        modes = self.ttk.Frame(form)
        modes.grid(row=4, column=0, columnspan=3, sticky="w", pady=(2, 0))
        self._language_label(modes, "loop_rounds").pack(side="left", padx=(8, 3))
        self.loop_count = self.tk.StringVar(value=str(WEB_STATUS_LOOP_COUNT_DEFAULT))
        self.loop_count_spinbox = self.ttk.Spinbox(
            modes, textvariable=self.loop_count,
            from_=0, to=WEB_STATUS_LOOP_COUNT_MAX, increment=1,
            width=5)
        self.loop_count_spinbox.pack(side="left")
        self._language_label(modes, "infinite").pack(side="left", padx=(3, 0))

        browser = self._language_labelframe(
            session_tab, "session_title", padding=(10, 6, 10, 6))
        browser.pack(fill="x")
        self._language_label(
            browser, "session_help", wraplength=520,
            foreground=WEB_STATUS_THEME["muted"]).pack(anchor="w", pady=(0, 4))
        row2 = self.ttk.Frame(browser)
        row2.pack(fill="x")
        self._language_button(row2, "open_login",
                              command=self.open_login_page).pack(side="left")
        self.cookie_paste_var = self.tk.StringVar(value="")
        self.ttk.Entry(row2, textvariable=self.cookie_paste_var,
                       width=18).pack(side="left", padx=6, fill="x", expand=True)
        session_actions = self.ttk.Frame(browser)
        session_actions.pack(fill="x", pady=(4, 0))
        self.btn_login = self._language_button(
            session_actions, "login", command=self.login_session)
        self.btn_login.configure(style="Primary.TButton")
        self.btn_login.pack(side="left")
        self._language_button(session_actions, "browser_login",
                              command=self.login_via_browser).pack(
                                  side="left", padx=(6, 0))
        # Add cloudbot connection button
        self._language_button(session_actions, "cloudbot_login",
                              command=self.login_via_cloudbot).pack(
                                  side="left", padx=(6, 0))
        self.paste_state = self.ttk.Label(
            browser, text="", foreground=WEB_STATUS_THEME["muted"])
        self.paste_state.pack(anchor="w", pady=(4, 0))

        # Add cloudbot parameter input field
        cloudbot_frame = self.ttk.Frame(browser)
        cloudbot_frame.pack(fill="x", pady=(4, 0))
        self._language_label(cloudbot_frame, "cloudbot_param").pack(side="left")
        self.cloudbot_param_var = self.tk.StringVar(value="")
        self.ttk.Entry(cloudbot_frame, textvariable=self.cloudbot_param_var,
                      width=20).pack(side="left", padx=6, fill="x", expand=True)

        log_frame = self.ttk.Frame(log_tab)
        log_frame.pack(fill="both", expand=True)
        log_scroll = self.ttk.Scrollbar(log_frame, orient="vertical")
        log_scroll.pack(side="right", fill="y")
        self.log_view = self.tk.Text(
            log_frame, wrap="word", height=12, state="disabled",
            yscrollcommand=log_scroll.set)
        self.log_view.configure(
            background=WEB_STATUS_THEME["entry"],
            foreground=WEB_STATUS_THEME["log_text"],
            insertbackground=WEB_STATUS_THEME["gold"],
            selectbackground=WEB_STATUS_THEME["border"],
            relief="flat", padx=10, pady=9, font=("Consolas", 9))
        self.log_view.pack(side="left", fill="both", expand=True)
        log_scroll.configure(command=self.log_view.yview)
        try:
            self._show_log_lines(load_web_status_log())
            log_load_warning = ""
        except OSError as exc:
            log_load_warning = "Could not load web_status.log ({0}).".format(
                type(exc).__name__)

        actions = self.ttk.Frame(self.root, padding=(10, 0, 10, 2))
        actions.pack(fill="x")
        self._language_button(actions, "preview_plan", command=self.preview).pack(
            side="left", padx=5)
        self._language_button(actions, "probe_session", command=self.probe).pack(side="left")
        self._language_button(actions, "update", command=self.check_update).pack(
            side="left", padx=5)
        actions2 = self.ttk.Frame(self.root, padding=(10, 0, 10, 6))
        actions2.pack(fill="x")
        self.btn_start = self._language_button(actions2, "start", command=self.start)
        self.btn_start.configure(style="Primary.TButton")
        self.btn_start.pack(side="left", padx=(5, 0))
        self.btn_stop = self._language_button(actions2, "stop", command=self.stop)
        self.btn_stop.configure(style="Danger.TButton")
        self.btn_stop.pack(side="left", padx=5)
        self._language_button(actions2, "capture_help", command=self.capture).pack(
            side="right")
        self.note = self.tk.StringVar(value="")
        if pool_load_warning:
            self._set_note(pool_load_warning)
        elif log_load_warning:
            self._set_note(log_load_warning)
        else:
            self._set_note("", key="ready_note")
        self.ttk.Label(self.root, textvariable=self.note, anchor="w",
                       style="Hint.TLabel", padding=(16, 0, 16, 12),
                       wraplength=560).pack(fill="x")
        self.clipboard_controller = WebStatusClipboardController(
            self.root, on_error=self._clipboard_error,
            translate=lambda key: self._text(key))
        self.clipboard_controller.install(self.root)
        self.root.after(120, self._poll)

    def _apply_theme(self, style):
        """Apply a bright ivory, champagne, and navy palette to the GUI."""
        colors = WEB_STATUS_THEME
        self.root.configure(background=colors["background"])
        style.configure("TFrame", background=colors["background"])
        style.configure(
            "TLabel", background=colors["background"], foreground=colors["text"],
            font=("Segoe UI", 9))
        style.configure(
            "Hint.TLabel", background=colors["background"],
            foreground=colors["muted"], font=("Segoe UI", 9))
        style.configure(
            "Brand.TLabel", background=colors["background"],
            foreground=colors["gold"], font=("Segoe UI", 12, "bold"))
        style.configure(
            "TCheckbutton", background=colors["background"],
            foreground=colors["text"], font=("Segoe UI", 9))
        style.map(
            "TCheckbutton", background=[("active", colors["background"])],
            foreground=[("disabled", colors["muted"])])
        style.configure(
            "TRadiobutton", background=colors["background"],
            foreground=colors["text"])
        style.configure(
            "TLabelframe", background=colors["background"],
            bordercolor=colors["border"], relief="solid", padding=8)
        style.configure(
            "TLabelframe.Label", background=colors["background"],
            foreground=colors["gold"], font=("Segoe UI", 9, "bold"))
        style.configure(
            "TButton", padding=(10, 6), background=colors["surface_high"],
            foreground=colors["text"], bordercolor=colors["border"],
            font=("Segoe UI", 9, "bold"), relief="flat")
        style.map(
            "TButton",
            background=[("disabled", colors["surface"]),
                        ("pressed", colors["border"]),
                        ("active", colors["teal"])],
            foreground=[("disabled", colors["muted"])])
        style.configure(
            "Primary.TButton", padding=(12, 7), background=colors["gold"],
            foreground=colors["surface"], bordercolor=colors["gold"],
            font=("Segoe UI", 9, "bold"), relief="flat")
        style.map(
            "Primary.TButton",
            background=[("disabled", colors["surface_high"]),
                        ("pressed", colors["gold"]),
                        ("active", colors["gold_hover"])],
            foreground=[("disabled", colors["muted"])])
        style.configure(
            "Danger.TButton", padding=(10, 7), background=colors["danger"],
            foreground=colors["surface"], bordercolor=colors["danger"],
            font=("Segoe UI", 9, "bold"), relief="flat")
        style.map(
            "Danger.TButton",
            background=[("disabled", colors["surface_high"]),
                        ("pressed", colors["danger"]),
                        ("active", "#e79595")],
            foreground=[("disabled", colors["muted"])])
        style.configure(
            "TEntry", padding=(7, 6), fieldbackground=colors["entry"],
            foreground=colors["text"], bordercolor=colors["border"],
            lightcolor=colors["gold"], darkcolor=colors["border"])
        style.configure(
            "TSpinbox", padding=(5, 5), fieldbackground=colors["entry"],
            foreground=colors["text"], bordercolor=colors["border"],
            arrowcolor=colors["gold"])
        style.configure(
            "TNotebook", background=colors["background"], borderwidth=0)
        style.configure(
            "TNotebook.Tab", padding=(15, 8), background=colors["surface_high"],
            foreground=colors["muted"], font=("Segoe UI", 9, "bold"))
        style.map(
            "TNotebook.Tab",
            background=[("selected", colors["surface"])],
            foreground=[("selected", colors["gold"])])
        style.configure("TSeparator", background=colors["gold"])
        style.configure(
            "TScrollbar", background=colors["surface_high"],
            troughcolor=colors["background"], bordercolor=colors["background"],
            arrowcolor=colors["gold"])

    # ---- helpers
    def _text(self, key):
        return WEB_STATUS_LANGUAGE_TEXT[getattr(self, "_language", "en")][key]

    def _register_language_widget(self, widget, key, notebook_tab=False):
        self._language_widgets.append((widget, key, notebook_tab))
        return widget

    def _language_label(self, parent, key, **kwargs):
        return self._register_language_widget(
            self.ttk.Label(parent, text=self._text(key), **kwargs), key)

    def _language_button(self, parent, key, **kwargs):
        return self._register_language_widget(
            self.ttk.Button(parent, text=self._text(key), **kwargs), key)

    def _language_checkbutton(self, parent, key, **kwargs):
        return self._register_language_widget(
            self.ttk.Checkbutton(parent, text=self._text(key), **kwargs), key)

    def _language_labelframe(self, parent, key, **kwargs):
        return self._register_language_widget(
            self.ttk.LabelFrame(parent, text=self._text(key), **kwargs), key)

    def switch_language(self):
        self._language = "th" if self._language == "en" else "en"
        for widget, key, notebook_tab in self._language_widgets:
            if notebook_tab:
                self.nb.tab(widget, text=self._text(key))
            else:
                widget.configure(text=self._text(key))
        if self._note_key:
            self.note.set(self._text(self._note_key))
        else:
            self.note.set(self._translate_message(self._note_source))
        if hasattr(self, "paste_state"):
            self.paste_state.configure(
                text=self._translate_message(self._paste_state_source),
                foreground=self._paste_state_color)
        if hasattr(self, "_log_source_lines"):
            self._show_log_lines(self._log_source_lines)

    def _set_note(self, text, key=None):
        self._note_source = str(text)
        self._note_key = key
        rendered = self._text(key) if key else self._translate_message(self._note_source)
        self.note.set(rendered)

    def _set_paste_state(self, text, foreground=None):
        foreground = foreground or WEB_STATUS_THEME["muted"]
        self._paste_state_source = str(text)
        self._paste_state_color = foreground
        self.paste_state.configure(
            text=self._translate_message(self._paste_state_source),
            foreground=foreground)

    def _translate_message(self, text):
        if getattr(self, "_language", "en") != "th":
            return text
        exact = {
            "Dry-run is on. Nothing has been sent.": "โหมดทดลองเปิดอยู่ ยังไม่มีการส่งสถานะ",
            "Working...": "กำลังทำงาน...",
            "Saved status lines to webtext.db.": "บันทึกข้อความสถานะลง webtext.db แล้ว",
            "No Chrome or Edge found on this computer.": "ไม่พบ Chrome หรือ Edge ในคอมพิวเตอร์เครื่องนี้",
            "Browser opened - sign in there; this window confirms by itself.":
                "เปิดเบราว์เซอร์แล้ว กรุณาเข้าสู่ระบบ หน้าต่างนี้จะตรวจสอบให้อัตโนมัติ",
            "browser opened": "เปิดเบราว์เซอร์แล้ว กำลังรอเข้าสู่ระบบ...",
            "Login page opened. After signing in, capture PHPSESSID on "
            "https://profiles.camfrog.com/home.php, paste it, then press Login.":
                "เปิดหน้า Login แล้ว หลังเข้าสู่ระบบ ให้รับค่า PHPSESSID จาก "
                "https://profiles.camfrog.com/home.php วางค่า แล้วกดตรวจสอบ Login",
            "PHPSESSID ready in memory. Click Login to verify.":
                "เก็บ PHPSESSID ไว้ในหน่วยความจำแล้ว กดตรวจสอบ Login",
            "Session captured from browser.": "รับเซสชันจากเบราว์เซอร์แล้ว",
            "Verifying PHPSESSID...": "กำลังตรวจสอบ PHPSESSID...",
            "Logged in via PHPSESSID - automation armed.":
                "ตรวจสอบ PHPSESSID แล้ว พร้อมใช้งานระบบอัตโนมัติ",
            "Logged in - automation armed.": "เข้าสู่ระบบแล้ว พร้อมใช้งานระบบอัตโนมัติ",
            "Live start cancelled. Nothing was sent.": "ยกเลิกการเริ่มส่งจริงแล้ว ไม่มีการส่งข้อมูล",
            "Stop requested. The current request may finish; no new updates will be scheduled.":
                "ส่งคำขอหยุดแล้ว คำขอที่กำลังทำงานอาจเสร็จก่อน จากนั้นจะไม่ส่งรายการใหม่",
            "Stop the live rotation before starting another network task.":
                "กรุณาหยุดการวนสถานะจริงก่อนเริ่มงานเครือข่ายอื่น",
            "Wait for the current request to finish before starting.":
                "รอให้คำขอปัจจุบันเสร็จก่อนเริ่มใหม่",
            "Enter a nickname first.": "กรุณากรอกชื่อเล่นก่อน",
            "Enter at least one status line.": "กรุณากรอกข้อความสถานะอย่างน้อยหนึ่งบรรทัด",
            "Enter or paste PHPSESSID first (Session tab).":
                "กรุณากรอกหรือวาง PHPSESSID ก่อน (แท็บบัญชีและเซสชัน)",
        }
        if text in exact:
            return exact[text]
        match = re.fullmatch(r"Rotation completed (\d+) round\(s\)\.", text)
        if match:
            return "วนครบ {0} รอบแล้ว".format(match.group(1))
        match = re.fullmatch(
            r"Temporary Live error; retrying in ([0-9.]+) seconds \((\d+)/(\d+)\)\.",
            text)
        if match:
            return "พบข้อผิดพลาดชั่วคราว กำลังลองอีกครั้งใน {0} วินาที ({1}/{2})".format(
                *match.groups())
        match = re.fullmatch(
            r"Live update failed after (\d+) retries; see Activity Log\.", text)
        if match:
            return "อัปเดต Live ไม่สำเร็จหลังลองซ้ำ {0} ครั้ง ดูรายละเอียดในบันทึกกิจกรรม".format(
                match.group(1))
        return text

    def _clipboard_error(self, exc):
        if hasattr(self, "note"):
            self._set_note("Paste failed: {0}: {1}".format(
                type(exc).__name__, exc))

    def chrome_import(self):
        """Auto-import the session from Chrome's store (nothing saved to disk)."""
        def do():
            jar = import_chrome_jar()
            return "loaded session from Chrome: {0}".format(cookie_summary(jar))

        self._run_bg(do, on_done=lambda: setattr(self, "chrome_mode", True))

    def _run_bg(self, fn, force=False, on_done=None, on_error=None):
        if getattr(self, "_closed", False):
            return False
        if self.busy:
            self._set_note("Wait for the current request to finish before starting.")
            return False
        if self.switching and not force:
            self._set_note("Stop the live rotation before starting another network task.")
            return False
        self.busy = True
        self._set_note("Working...")
        worker = threading.Thread(
            target=self._worker, args=(fn, on_done, on_error), daemon=True)
        try:
            worker.start()
        except RuntimeError:
            self.busy = False
            self._set_note("Could not start the background task.")
            return False
        return True

    def _worker(self, fn, on_done, on_error):
        try:
            text, ok = fn(), True
        except Exception as exc:  # shown in the GUI, never a traceback window
            text, ok = "failed: {0}: {1}".format(type(exc).__name__, exc), False
        self.q.put((ok, text, on_done, on_error))

    def _queue_ui_call(self, callback):
        """Queue a Tk operation for the main thread instead of calling Tk from a worker."""
        if not getattr(self, "_closed", False):
            self.q.put((_GUI_CALLBACK_MARKER, callback))

    def _queue_ui_status(self, text):
        self._queue_ui_call(
            lambda text=str(text): self._set_note(text))

    def _show_log_lines(self, lines):
        if not hasattr(self, "log_view"):
            return
        self._log_source_lines = list(lines[-WEB_STATUS_LOG_GUI_LINES:])
        display_lines = [self._translate_log_line(line)
                         for line in self._log_source_lines]
        self.log_view.configure(state="normal")
        self.log_view.delete("1.0", "end")
        self.log_view.insert("end", "\n".join(display_lines))
        if display_lines:
            self.log_view.insert("end", "\n")
        self.log_view.configure(state="disabled")
        self.log_view.see("end")

    def _append_log_line(self, entry):
        if not hasattr(self, "log_view"):
            return
        self._show_log_lines(
            getattr(self, "_log_source_lines", []) + [entry])

    def _translate_log_line(self, line):
        parts = line.split(" | ", 2)
        if len(parts) < 2:
            return line
        if getattr(self, "_language", "en") == "th":
            parts[1] = WEB_STATUS_LOG_LABELS_TH.get(parts[1], parts[1])
        else:
            parts[1] = WEB_STATUS_LOG_LABELS_EN.get(parts[1], parts[1])
        return " | ".join(parts)

    def _record_activity(self, event, detail=None, secrets=()):
        try:
            entry = append_web_status_log(
                event, detail=detail, secrets=secrets,
                language=getattr(self, "_language", "en"))
        except (OSError, ValueError) as exc:
            try:
                entry = _web_status_log_entry(
                    event, detail=detail, secrets=secrets,
                    language=getattr(self, "_language", "en"))
            except ValueError:
                return
            if hasattr(self, "note"):
                self._set_note("Could not write web_status.log ({0}).".format(
                    type(exc).__name__))
        self._append_log_line(entry)

    def _rotation_settings_detail(self, interval, timeout, live, pool):
        delay_source = "switch_every"
        delay = interval
        effective_delay = (max(delay, LIVE_ROTATE_INTERVAL_MIN)
                           if live else delay)
        loop_count = getattr(self, "_cycle_loop_count", 0)
        loop_label = "{0} (infinite)".format(loop_count) if loop_count == 0 \
            else str(loop_count)
        return (
            "mode={0}; delay_source={1}; configured_delay_s={2}; "
            "effective_delay_s={3}; loop_rounds={4}; timeout_s={5}; "
            "populated_slots={6}"
        ).format(
            "live" if live else "dry-run",
            delay_source,
            delay,
            effective_delay,
            loop_label,
            timeout,
            len(pool),
        )

    def _poll(self):
        if getattr(self, "_closed", False):
            return
        try:
            while True:
                item = self.q.get_nowait()
                if item[0] is _GUI_CALLBACK_MARKER:
                    try:
                        item[1]()
                    except Exception as exc:
                        self._set_note("UI update failed ({0}).".format(
                            type(exc).__name__))
                    continue
                ok, text, on_done, on_error = item
                self.busy = False
                if text:
                    self._set_note(text)
                callback = on_done if ok else on_error
                if callback is not None:
                    try:
                        callback()
                    except Exception as exc:
                        self._set_note("{0} ({1})".format(text, exc))
        except queue.Empty:
            pass
        if getattr(self, "_closed", False):
            return
        try:
            self.root.after(120, self._poll)
        except Exception:
            pass

    def close(self):
        """Cancel queued work and prevent any new POST when the window closes."""
        if getattr(self, "_closed", False):
            return
        self.stop()
        self._closed = True
        try:
            self.root.destroy()
        except Exception:
            pass

    def _login_name(self):
        login = self.login.get().strip()
        if not login:
            raise ValueError("Enter a nickname first.")
        return login

    def _pool(self):
        pool = self._pool_values()
        if not pool:
            raise ValueError("Enter at least one status line.")
        return pool

    def _pool_values(self):
        return [value for variable in self.pool_vars
                if (value := variable.get().strip())]

    def _save_web_texts(self, notify=True):
        try:
            save_web_text_lines([variable.get() for variable in self.pool_vars])
        except (OSError, sqlite3.Error) as exc:
            self._set_note("Could not save status lines to webtext.db: {0}".format(
                type(exc).__name__))
            return False
        self._record_activity("status_lines_saved")
        if notify:
            self._set_note("Saved status lines to webtext.db.")
        return True

    def save_web_texts(self):
        self._save_web_texts()

    def _fields(self):
        return self._login_name(), self._pool()

    # ---- actions (network runs in worker threads; secrets never leave memory)
    def open_login_page(self):
        import webbrowser
        webbrowser.open(LOGIN_PAGE_URL)
        self._set_paste_state(
            "Login page opened. After signing in, capture PHPSESSID on "
            "https://profiles.camfrog.com/home.php, paste it, then press Login.")

    def use_pasted_cookie(self):
        try:
            self._sync_pasted_cookie()
        except ValueError as exc:
            self._set_paste_state(
                str(exc), foreground=WEB_STATUS_THEME["error"])
            return
        self._set_paste_state(
            "PHPSESSID ready in memory. Click Login to verify.")

    def _sync_pasted_cookie(self):
        """Validate the current entry and use it instead of any stale cached paste."""
        text = self.cookie_paste_var.get().strip()
        if not text:
            if self.cookie_paste and self._cookie_from_browser:
                return self.cookie_paste
            if self.cookie_paste or self.session_ready:
                self.cookie_paste = ""
                self._cookie_from_browser = False
                self.session_ready = False
                self._invalidate_pending_start()
            raise ValueError("Enter or paste PHPSESSID first (Session tab).")
        changed = text != self.cookie_paste
        if changed:
            self.session_ready = False
            self._invalidate_pending_start()
        self._cookie_from_browser = False
        try:
            cookie_from_paste(text)
        except ValueError:
            if changed:
                self.cookie_paste = ""
                self._cookie_from_browser = False
            raise
        self.cookie_paste = text
        self._cookie_from_browser = False
        return text

    def _session_jar(self):
        """The cookie jar for probe/rotation: single flow using pasted PHPSESSID or cloudbot."""
        if not self.cookie_paste:
            raise ValueError("Enter or paste PHPSESSID or cloudbot first (Session tab).")
        return cookie_from_paste(self.cookie_paste)

    def login_via_cloudbot(self):
        """Connect via cloudbot parameter (UI action)."""
        if self.busy:
            self._set_note("Wait for the current request to finish before starting.")
            return
        if self.switching:
            self._set_note("Stop the live rotation before starting another network task.")
            return

        cloudbot_param = self.cloudbot_param_var.get().strip()
        login = self.login.get().strip()
        timeout = float(self.timeout.get().strip()) if self.timeout.get().strip() else TIMEOUT_DEFAULT

        try:
            if not cloudbot_param:
                raise ValueError("Enter cloudbot parameter first (Session tab).")
            if not login:
                raise ValueError("Enter nickname first (Setup tab).")

            # Parse cloudbot parameter (format: cloudbot=<token>)
            if not cloudbot_param.startswith("cloudbot="):
                raise ValueError("Invalid cloudbot parameter format. Use: cloudbot=<token>")

            cloudbot_token = cloudbot_param.split("=", 1)[1]
            if not cloudbot_token:
                raise ValueError("Empty cloudbot token.")

            # Use the _connect_via_cloudbot method
            self._connect_via_cloudbot(login, cloudbot_param, timeout,
                                      on_done=lambda: setattr(self, "session_ready", True))
        except ValueError as exc:
            self._set_note("Cloudbot connection failed: {0}".format(exc))

    def _connect_via_cloudbot(self, login, cloudbot_param, timeout, on_done):
        """Connect via cloudbot parameter for Camfrogbot control."""
        if not cloudbot_param.strip():
            raise ValueError("Enter cloudbot parameter first (Session tab).")
        if not login.strip():
            raise ValueError("Enter nickname first (Setup tab).")

        def do():
            import urllib.request

            # Parse cloudbot parameter (format: cloudbot=<token>)
            if not cloudbot_param.startswith("cloudbot="):
                raise ValueError("Invalid cloudbot parameter format. Use: cloudbot=<token>")

            cloudbot_token = cloudbot_param.split("=", 1)[1]
            if not cloudbot_token:
                raise ValueError("Empty cloudbot token.")

            # Create a cookie jar with the cloudbot token
            jar = CookieJar()
            jar.set_cookie(Cookie(
                version=0, name="cloudbot", value=cloudbot_token,
                port=None, port_specified=False,
                domain=".camfrog.com", domain_specified=True,
                domain_initial_dot=True, path="/", path_specified=True,
                secure=True, expires=None, discard=False,
                comment=None, comment_url=None, rest={}, rfc2109=False))

            opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(jar))

            # Try to fetch the profile page with cloudbot token
            try:
                html = fetch_profile(opener, login, timeout)
                verdict, detail = summarize_session(html)

                if verdict != "signed-in":
                    raise ValueError(f"Cloudbot connection failed: {detail}")

                return f"Cloudbot connection successful. {detail}"
            except Exception as exc:
                diagnostic = _web_status_request_error(
                    "cloudbot connection", exc,
                    secrets=(login, cloudbot_token))
                raise RuntimeError(diagnostic) from exc

        self._record_activity("browser_login_started")

        def success():
            self.session_ready = True
            self._set_note("Connected via cloudbot. Automation armed.")

        def error(exc):
            self._set_note("Cloudbot connection failed: {0}".format(exc))

        self._run_bg(do, on_done=success, on_error=error)

    def _verify_session(self, login, timeout, on_done):
        """Probe PHPSESSID session in a worker; on_done runs on success."""
        if self.busy:
            self._set_note("Wait for the current request to finish before starting.")
            return
        if self.switching:
            self._set_note("Stop the live rotation before starting another network task.")
            return
        failure_detail = []
        cookie_secrets = _session_cookie_redaction_values(
            getattr(self, "cookie_paste", ""))

        def do():
            import urllib.request

            try:
                jar = self._session_jar()
                opener = urllib.request.build_opener(
                    urllib.request.HTTPCookieProcessor(jar))
                html = fetch_profile(opener, login, timeout)
                verdict, detail = summarize_session(html)
                if verdict != "signed-in":
                    raise ValueError(detail)
                return detail
            except Exception as exc:
                diagnostic = _web_status_request_error(
                    "session verification GET /home.php", exc,
                    secrets=(login,) + cookie_secrets)
                failure_detail[:] = [diagnostic]
                raise RuntimeError(diagnostic) from exc

        self._record_activity("session_verification_started")

        def verified():
            self._record_activity("session_verification_succeeded")
            on_done()

        self._run_bg(
            do, on_done=verified,
            on_error=lambda: self._record_activity(
                "session_verification_failed",
                detail=failure_detail[0] if failure_detail else
                "session verification worker failed without diagnostic details",
                secrets=cookie_secrets))

    def login_via_browser(self):
        """One-click login: the real browser solves the CAPTCHA and the
        HttpOnly session cookie comes back through DevTools."""
        if self.busy:
            self._set_note("Wait for the current request to finish before starting.")
            return
        if self.switching:
            self._set_note("Stop the live rotation before starting another network task.")
            return
        if find_browser() is None:
            self._set_note("No Chrome or Edge found on this computer.")
            return
        self._record_activity("browser_login_started")
        self._set_note("Browser opened - sign in there; this window confirms by itself.")

        captured = []

        def work():
            cookies, _profile = browser_login(
                on_status=self._queue_ui_status)
            captured.append(cookies)
            return "done"

        self._run_bg(
            work,
            on_done=lambda: self._browser_login_done(captured[0]) if captured else None)

    def _browser_login_done(self, cookies):
        try:
            cookie_from_paste(cookies)  # validate before adopting
        except ValueError as exc:
            self._set_note(str(exc))
            return
        self.cookie_paste = cookies
        self._cookie_from_browser = True
        self.cookie_paste_var.set("")
        self.session_ready = False
        self._invalidate_pending_start()
        self._record_activity("browser_session_captured")
        self._set_paste_state("Session captured from browser.")
        self._verify_session(self._login_name(),
                             self._timeout_value() or 20.0, self._on_logged_in)

    def login_session(self):
        """Verify the captured session live, arm automation on success."""
        if getattr(self, "busy", False):
            self._set_note("Wait for the current request to finish before starting.")
            return
        if getattr(self, "switching", False):
            self._set_note("Stop the live rotation before starting another network task.")
            return
        try:
            login = self._login_name()
            self._sync_pasted_cookie()
        except ValueError as exc:
            self._set_note(str(exc))
            return
        timeout = self._timeout_value()
        if timeout is None:
            return
        self.session_ready = False
        self._set_paste_state("Verifying PHPSESSID...")
        self._verify_session(login, timeout, self._on_logged_in)

    def _on_logged_in(self):
        self.session_ready = True
        self._set_paste_state(
            "Logged in via PHPSESSID - automation armed.",
            foreground=WEB_STATUS_THEME["success"])

    def preview(self):
        try:
            login, pool = self._fields()
        except ValueError as exc:
            self._set_note(str(exc))
            return
        live = self.live.get()
        self._set_note(build_plan(login, pool[0])
                      + (" LIVE ARMED (still gated)." if live else ""))

    def check_update(self):
        def do():
            state, message = self_update("web-status.exe")
            return "{0}\n{1}".format(
                message, "restart the app to run the new version."
                if state == "ready" else "")
        self._run_bg(do)

    def _timeout_value(self):
        try:
            return parse_timeout(self.timeout.get())
        except ValueError as exc:
            self._set_note(str(exc))
            return None

    def probe(self):
        try:
            login = self._login_name()
            self._sync_pasted_cookie()
        except ValueError as exc:
            self._set_note(str(exc))
            return
        timeout = self._timeout_value()
        if timeout is None:
            return

        def do():
            import urllib.request

            jar = self._session_jar()
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
            html = fetch_profile(opener, login, timeout)
            _verdict, detail = summarize_session(html)
            return "loaded session: {0}. {1}".format(cookie_summary(jar), detail)

        self._run_bg(do)

    def capture(self):
        self._set_note("", key="capture_instructions")

    # ---- one-click auto-switch rotation (same fail-closed gates as one-shot ops)
    def start(self):
        if self.switching:
            return
        if getattr(self, "busy", False):
            self._set_note("Wait for the current request to finish before starting.")
            return
        try:
            login, pool = self._fields()
            interval = parse_rotate_interval(self.interval.get())
            timeout = parse_timeout(self.timeout.get())
            loop_setting = getattr(self, "loop_count", None)
            if loop_setting is not None:
                loop_count = parse_loop_count(loop_setting.get())
            else:
                infinity_setting = getattr(self, "infinity_loop", None)
                infinity = (infinity_setting.get()
                            if infinity_setting is not None else True)
                loop_count = 0 if infinity else 1
        except ValueError as exc:
            self._set_note(str(exc))
            return
        self._cycle_marquee = False
        self._cycle_marquee_step_seconds = WEB_MARQUEE_STEP_SECONDS_DEFAULT
        self._cycle_loop_count = loop_count
        self._cycle_rounds_completed = 0
        if not self._save_web_texts(notify=False):
            return
        live = self.live.get()
        if live:
            try:
                self._sync_pasted_cookie()
            except ValueError as exc:
                self._set_note(str(exc))
                return
        if live and not getattr(self, "session_ready", False):
            # Single login: verify the session first, then chain into rotation.
            generation = self._invalidate_pending_start()
            self._pending = (login, pool, interval, timeout, generation)
            self._verify_session(
                login, timeout,
                lambda: self._after_login(generation))
            return
        self._invalidate_pending_start()
        if live and not getattr(self, "_live_confirmed", False):
            from tkinter import messagebox
            ok = messagebox.askyesno(
                self._text("confirm_title"), self._text("confirm_start"),
                parent=self.root)
            if not ok:
                self._set_note("Live start cancelled. Nothing was sent.")
                return
            self._live_confirmed = True
        self.switching = True
        event = "live_rotation_started" if live else "dry_run_rotation_started"
        self._record_activity(
            event,
            detail=self._rotation_settings_detail(
                interval, timeout, live, pool))
        self._cycle(login, pool, interval, timeout, live, 0)

    def _invalidate_pending_start(self):
        """Invalidate queued login callbacks before Stop or another Start."""
        self._start_generation = getattr(self, "_start_generation", 0) + 1
        self._pending = None
        return self._start_generation

    def _after_login(self, generation):
        """Continue a pending live Start after the session verified."""
        pending = getattr(self, "_pending", None)
        if not pending or pending[4] != generation:
            return
        self._pending = None
        self.session_ready = True
        self._set_paste_state(
            "Logged in - automation armed.",
            foreground=WEB_STATUS_THEME["success"])
        login, pool, interval, timeout = pending[:4]
        from tkinter import messagebox
        ok = messagebox.askyesno(
            self._text("confirm_title"), self._text("confirm_after_login"),
            parent=self.root)
        if not ok:
            self._set_note("Live start cancelled. Nothing was sent.")
            return
        self._live_confirmed = True
        self.switching = True
        self._record_activity(
            "live_rotation_started",
            detail=self._rotation_settings_detail(
                interval, timeout, True, pool))
        self._cycle(login, pool, interval, timeout, True, 0)

    def stop(self):
        was_active = self.switching or self._pending is not None
        self._invalidate_pending_start()
        self.switching = False
        self.session_ready = False  # next Start re-verifies the session
        self.chrome_mode = False  # Stop also drops an imported Chrome session
        if self.rotate_job is not None:
            try:
                self.root.after_cancel(self.rotate_job)
            except Exception:
                pass
            self.rotate_job = None
        self._set_note(
            "Stop requested. The current request may finish; no new updates will be scheduled.")
        if was_active:
            self._record_activity("rotation_stopped")

    def _cycle(self, login, pool, interval, timeout, live, index, frame_index=0,
               generation=None, retry_attempt=0):
        if getattr(self, "_closed", False) or not self.switching:
            return
        current_generation = getattr(self, "_start_generation", 0)
        if generation is None:
            generation = current_generation
        if generation != current_generation:
            return
        if getattr(self, "busy", False):
            self.rotate_job = self.root.after(
                250, lambda: self._cycle(
                    login, pool, interval, timeout, live, index, frame_index,
                    generation=generation, retry_attempt=retry_attempt))
            return
        try:
            pool = self._pool_values() or pool
            if not pool:
                raise ValueError("status pool is empty; add at least one line.")
            status = pool[index % len(pool)]
        except ValueError as exc:
            self._set_note(str(exc))
            self.stop()
            return
        marquee_setting = getattr(self, "marquee_mode", None)
        marquee = bool(getattr(
            self, "_cycle_marquee",
            marquee_setting.get() if marquee_setting is not None else False))
        frame_seconds = float(getattr(
            self, "_cycle_marquee_step_seconds", WEB_MARQUEE_STEP_SECONDS_DEFAULT))
        loop_count = getattr(self, "_cycle_loop_count", None)
        if loop_count is None:
            infinity_setting = getattr(self, "infinity_loop", None)
            infinity = bool(getattr(
                self, "_cycle_infinity_loop",
                infinity_setting.get() if infinity_setting is not None else True))
            loop_count = 0 if infinity else 1
        frames = web_status_frames(status, enabled=marquee)
        frame_index = min(frame_index, len(frames) - 1)
        frame = frames[frame_index]
        slot_index = index % len(pool)
        step_delay = (frame_seconds if marquee else
                      max(interval, LIVE_ROTATE_INTERVAL_MIN) if live else interval)
        cookie_secrets = _session_cookie_redaction_values(
            getattr(self, "cookie_paste", ""))
        diagnostic_secrets = (frame, login) + cookie_secrets
        failure_detail = []
        retry_context = []
        post_started = []

        def cancelled():
            return (getattr(self, "_closed", False)
                    or not self.switching
                    or generation != getattr(self, "_start_generation", 0))

        def do():
            if not live:
                if cancelled():
                    return ""
                return "cycle #{0}/{1} (dry-run): {2}".format(
                    index + 1, len(pool), frame)
            if cancelled():
                return ""
            try:
                import urllib.request

                jar = self._session_jar()
                opener = urllib.request.build_opener(
                    urllib.request.HTTPCookieProcessor(jar))
                ok, message = perform_update(
                    opener, frame, timeout, confirm=True, cancelled=cancelled,
                    on_post_started=lambda: post_started.append(True))
                if not ok:
                    diagnostic = _sanitize_web_status_detail(
                        message, secrets=diagnostic_secrets)
                    failure_detail[:] = [diagnostic]
                    retry_policy = _web_status_retry_policy(
                        diagnostic, retry_attempt)
                    if retry_policy:
                        retry_context[:] = [retry_policy]
                        return "Live update retry scheduled."
                    raise RuntimeError(diagnostic)
            except WebStatusUpdateCancelled:
                return ""
            except Exception as exc:
                diagnostic = _web_status_request_error(
                    "live status update", exc, secrets=diagnostic_secrets)
                failure_detail[:] = [diagnostic]
                retry_policy = _web_status_retry_policy(
                    diagnostic, retry_attempt)
                if retry_policy:
                    retry_context[:] = [retry_policy]
                    return "Live update retry scheduled."
                raise RuntimeError(diagnostic) from exc
            return "cycle #{0}/{1}: {2}".format(index + 1, len(pool), message)

        def advance():
            if (not self.switching
                    or generation != getattr(self, "_start_generation", 0)):
                return
            if marquee and frame_index + 1 < len(frames):
                next_index = slot_index
                next_frame = frame_index + 1
            elif slot_index + 1 < len(pool):
                next_index = slot_index + 1
                next_frame = 0
            else:
                rounds_completed = getattr(self, "_cycle_rounds_completed", 0) + 1
                self._cycle_rounds_completed = rounds_completed
                if loop_count and rounds_completed >= loop_count:
                    self.switching = False
                    self.rotate_job = None
                    self.session_ready = False
                    self.chrome_mode = False
                    self._invalidate_pending_start()
                    self._record_activity(
                        "marquee_completed" if marquee else "rotation_completed")
                    self._set_note("{0} completed {1} round(s).".format(
                        "Marquee" if marquee else "Rotation", rounds_completed))
                    return
                next_index = 0
                next_frame = 0
            self.rotate_job = self.root.after(
                max(1, int(round(step_delay * 1000))), self._cycle,
                login, pool, interval, timeout, live, next_index, next_frame,
                generation)

        def failed():
            if live:
                detail = failure_detail[0] if failure_detail else \
                    "live status update worker failed without diagnostic details"
                if retry_attempt:
                    detail = "retry_attempts={0}; {1}".format(
                        retry_attempt, detail)
                detail += "; " + self._rotation_settings_detail(
                    interval, timeout, live, pool)
                self._record_activity(
                    "status_update_failed",
                    detail=detail,
                    secrets=diagnostic_secrets)
            else:
                self._record_activity("rotation_stopped")
            if generation != getattr(self, "_start_generation", 0):
                return
            self.switching = False
            self.rotate_job = None
            self.session_ready = False
            self.chrome_mode = False
            self._invalidate_pending_start()

        def completed():
            if (not self.switching
                    or generation != getattr(self, "_start_generation", 0)):
                if live and post_started:
                    self._record_activity("status_update_succeeded")
                return
            if retry_context:
                if retry_attempt >= LIVE_RETRY_MAX_ATTEMPTS:
                    failed()
                    self._set_note(
                        "Live update failed after {0} retries; see Activity Log."
                        .format(LIVE_RETRY_MAX_ATTEMPTS))
                    return
                reason, retry_delay = retry_context[0]
                retry_detail = failure_detail[0] if failure_detail else \
                    "retryable live update failure without diagnostic details"
                detail = (
                    "reason={0}; attempt={1}/{2}; retry_in_s={3}; cause={4}; {5}"
                ).format(
                    reason,
                    retry_attempt + 1,
                    LIVE_RETRY_MAX_ATTEMPTS,
                    retry_delay,
                    retry_detail,
                    self._rotation_settings_detail(interval, timeout, live, pool),
                )
                self._record_activity(
                    "live_retry_scheduled",
                    detail=detail,
                    secrets=diagnostic_secrets)
                self._set_note(
                    "Temporary Live error; retrying in {0:g} seconds ({1}/{2})."
                    .format(
                        retry_delay, retry_attempt + 1,
                        LIVE_RETRY_MAX_ATTEMPTS))
                self.rotate_job = self.root.after(
                    max(1, int(round(retry_delay * 1000))),
                    lambda: self._cycle(
                        login, pool, interval, timeout, live, index, frame_index,
                        generation=generation, retry_attempt=retry_attempt + 1))
                return
            self._record_activity("status_update_succeeded" if live
                                  else "status_previewed")
            advance()

        self._run_bg(
            do, force=True, on_done=completed, on_error=failed)


# ============================================================
# Inlined browser login (tools/browser_login.py): real-browser login +
# DevTools cookie harvest. tools/browser_login.py stays the tested copy.
# ============================================================

BROWSER_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
)
LOGIN_PAGE = "https://www.camfrog.com/th/login.php"
SESSION_COOKIE = "PHPSESSID"
WAIT_TIMEOUT = 300.0  # seconds the user gets to finish logging in


def find_browser():
    for path in BROWSER_CANDIDATES:
        if Path(path).is_file():
            return path
    return None


def _close_browser_process(process):
    """Close the dedicated login browser process tree without touching other browsers."""
    if process is None:
        return
    try:
        if process.poll() is not None:
            return
        if os.name == "nt":
            try:
                subprocess.run(
                    [system_taskkill_path(), "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    check=False, timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                pass
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# ---------------------------------------------------------------- devtools ws
class _WebSocket:
    """Minimal RFC 6455 client: one connection, text frames, no extensions."""

    def __init__(self, url):
        try:
            endpoint = urllib.parse.urlsplit(url)
            port = endpoint.port
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid local DevTools websocket URL") from exc
        host = (endpoint.hostname or "").casefold()
        if (endpoint.scheme.casefold() != "ws"
                or host not in {"127.0.0.1", "localhost", "::1"}
                or not port or endpoint.username or endpoint.password):
            raise ValueError("only loopback ws:// DevTools URLs are supported")
        self.sock = socket.create_connection((host, port), timeout=10)
        self.buf = b""
        key = base64.b64encode(os.urandom(16))
        path = endpoint.path or "/"
        if endpoint.query:
            path += "?" + endpoint.query
        handshake = (
            "GET {path} HTTP/1.1\r\n"
            "Host: {host_header}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).format(path=path, host_header=endpoint.netloc, key=key.decode())
        try:
            self.sock.sendall(handshake.encode())
            self._read_http_headers(key)
        except Exception:
            self.close()
            raise

    def _read_http_headers(self, key):
        data = b""
        while b"\r\n\r\n" not in data:
            block = self.sock.recv(4096)
            if not block:
                raise OSError("devtools websocket closed during handshake")
            data += block
            if len(data) > 65536:
                raise OSError("devtools websocket handshake headers are too large")
        head, self.buf = data.split(b"\r\n\r\n", 1)
        lines = head.decode("iso-8859-1").split("\r\n")
        status = lines[0].split()
        headers = {}
        for line in lines[1:]:
            name, separator, value = line.partition(":")
            if separator:
                headers[name.strip().casefold()] = value.strip()
        connection_tokens = {
            token.strip().casefold()
            for token in headers.get("connection", "").split(",")
        }
        expected_accept = base64.b64encode(hashlib.sha1(
            key + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11",
            usedforsecurity=False).digest()).decode("ascii")
        if (len(status) < 2 or status[1] != "101"
                or headers.get("upgrade", "").casefold() != "websocket"
                or "upgrade" not in connection_tokens
                or not hmac.compare_digest(
                    headers.get("sec-websocket-accept", ""), expected_accept)):
            raise OSError("devtools websocket handshake refused")

    def send_text(self, text):
        payload = text.encode("utf-8")
        header = bytearray([0x81])  # FIN + text
        mask = os.urandom(4)
        n = len(payload)
        if n < 126:
            header.append(0x80 | n)
        elif n < 1 << 16:
            header.append(0x80 | 126)
            header += n.to_bytes(2, "big")
        else:
            header.append(0x80 | 127)
            header += n.to_bytes(8, "big")
        self.sock.sendall(bytes(header) + mask
                          + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def _recv_frame(self):
        while True:
            if len(self.buf) >= 2:
                fin_op, length = self.buf[0], self.buf[1] & 0x7F
                pos = 2
                if length == 126:
                    if len(self.buf) < 4:
                        break
                    length = int.from_bytes(self.buf[2:4], "big")
                    pos = 4
                elif length == 127:
                    if len(self.buf) < 10:
                        break
                    length = int.from_bytes(self.buf[2:10], "big")
                    pos = 10
                if len(self.buf) >= pos + length:
                    payload = self.buf[pos:pos + length]
                    self.buf = self.buf[pos + length:]
                    return fin_op & 0x0F, payload
            block = self.sock.recv(65536)
            if not block:
                raise OSError("devtools websocket closed")
            self.buf += block

    def read_json(self):
        """Next data frame decoded as JSON; pings answered with pongs."""
        while True:
            opcode, payload = self._recv_frame()
            if opcode == 0x9:  # ping -> pong
                self._send_frame(0xA, payload)
                continue
            if opcode == 0xA:
                continue
            return json.loads(payload.decode("utf-8", "replace"))

    def _send_frame(self, opcode, payload):
        mask = os.urandom(4)
        header = bytearray([0x80 | opcode, 0x80 | len(payload)])
        self.sock.sendall(bytes(header) + mask
                          + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def _http_json(url):
    try:
        endpoint = urllib.parse.urlsplit(url)
        port = endpoint.port
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid local DevTools HTTP URL") from exc
    if (endpoint.scheme.casefold() != "http"
            or (endpoint.hostname or "").casefold() != "127.0.0.1"
            or not port or endpoint.username or endpoint.password):
        raise ValueError("only loopback DevTools HTTP URLs are supported")
    # Use a direct HTTP connection so redirects cannot escape loopback.
    target = endpoint.path or "/"
    if endpoint.query:
        target += "?" + endpoint.query
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request("GET", target, headers={"Connection": "close"})
        response = connection.getresponse()
        if response.status != 200:
            raise OSError("local DevTools endpoint returned HTTP {0}".format(
                response.status))
        return json.loads(response.read().decode("utf-8", "replace"))
    finally:
        connection.close()


def _find_page_target(port):
    targets = _http_json("http://127.0.0.1:{0}/json/list".format(port))
    for target in targets:
        if target.get("type") != "page" or not target.get("webSocketDebuggerUrl"):
            continue
        try:
            endpoint = urllib.parse.urlsplit(target["webSocketDebuggerUrl"])
            target_port = endpoint.port
        except (TypeError, ValueError):
            continue
        if (endpoint.scheme.casefold() == "ws"
                and (endpoint.hostname or "").casefold()
                in {"127.0.0.1", "localhost", "::1"}
                and target_port == int(port)
                and not endpoint.username and not endpoint.password):
            return target["webSocketDebuggerUrl"]
    raise OSError("no browser page target found")


def _cdp_call(ws, method, params=None):
    request = {"id": 1, "method": method}
    if params:
        request["params"] = params
    ws.send_text(json.dumps(request))
    while True:
        message = ws.read_json()
        if message.get("id") == 1:
            return message
        # browser events that arrive while we work are ignored


# ---------------------------------------------------------------- the flow
def browser_login(timeout=WAIT_TIMEOUT, on_status=None, browser=None,
                  profile_dir=None, keep_browser=False):
    """Open the login page in a private browser session and harvest cookies.

    Returns (cookie_string, profile_dir). cookie_string is `name=value; ...`
    for cookie_from_paste(). The browser is closed by default; its temporary
    profile is also removed unless `keep_browser` is true. A supplied profile
    directory is never deleted. Raises OSError/RuntimeError on failure.
    """
    browser = browser or find_browser()
    if not browser:
        raise OSError("no Chrome or Edge found on this computer")
    port = _free_port()
    temporary_profile = profile_dir is None
    tmp = Path(profile_dir) if profile_dir else Path(
        tempfile.mkdtemp(prefix="camfrog-login-"))
    tmp.mkdir(parents=True, exist_ok=True)
    process = None
    ws = None
    try:
        spawn = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "close_fds": True,
        }
        if os.name == "nt":
            spawn["creationflags"] = 0x08000000
        process = subprocess.Popen(
            [browser, "--remote-debugging-port={0}".format(port),
             "--user-data-dir={0}".format(tmp), "--no-first-run",
             "--no-default-browser-check", "--new-window", LOGIN_PAGE],
            **spawn)
        if on_status:
            on_status("browser opened")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if ws is None:
                    ws = _WebSocket(_find_page_target(port))
                cookies = _cdp_call(ws, "Network.getAllCookies").get(
                    "result", {}).get("cookies", [])
                if any(c.get("name") == SESSION_COOKIE and "camfrog" in (c.get("domain") or "")
                       for c in cookies):
                    return _cookies_to_string(cookies), (
                        str(tmp) if keep_browser or not temporary_profile else None)
                time.sleep(1.5)
            except (OSError, ValueError, TimeoutError):
                try:
                    ws.close()
                except Exception:
                    pass
                ws = None
                time.sleep(1.5)  # browser still starting
        raise RuntimeError("login was not completed in time")
    finally:
        try:
            ws.close()
        except Exception:
            pass
        if not keep_browser:
            _close_browser_process(process)
            if temporary_profile:
                shutil.rmtree(tmp, ignore_errors=True)


def _cookies_to_string(cookies):
    seen, parts = set(), []
    for cookie in cookies:
        domain = (cookie.get("domain") or "").lstrip(".").lower()
        if not domain.endswith("camfrog.com"):
            continue
        name, value = cookie.get("name") or "", cookie.get("value") or ""
        if not name or not value or name in seen:
            continue
        seen.add(name)
        parts.append("{0}={1}".format(name, value))
    if not parts:
        raise ValueError("no camfrog.com cookies in this browser session")
    return "; ".join(parts)


# ---------- self-update from the GitHub release ----------
# Read-only GitHub API (no token needed for public repos, stdlib only). Each
# packaged app checks the same repo's latest release and downloads only its
# own executable asset, verified against the release's SHA256SUMS.txt.
APP_VERSION = "2.19.2"
GITHUB_REPO = os.environ.get("CAMFROG_UPDATE_REPO", "cvsz/zcfato")
UPDATE_ASSET_SUMS = "SHA256SUMS.txt"


def _version_key(text):
    parts = [int(p) for p in re.findall(r"\d+", str(text))[:3]]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def version_newer(latest, current=APP_VERSION):
    """True when `latest` sorts above `current` (2.19.0 > 2.18.3)."""
    return _version_key(latest) > _version_key(current)


def _validate_github_release_url(url):
    """Accept only HTTPS URLs on GitHub's release and asset hosts."""
    allowed_hosts = {
        "github.com", "objects.githubusercontent.com",
        "release-assets.githubusercontent.com",
    }
    try:
        parsed = urllib.parse.urlsplit(str(url))
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid GitHub release URL") from exc
    if (parsed.scheme.casefold() != "https"
            or (parsed.hostname or "").casefold() not in allowed_hosts
            or parsed.username or parsed.password
            or port not in (None, 443)):
        raise ValueError("update URL must use HTTPS on a GitHub release host")
    return str(url)


def _validate_github_response_url(response, requested_url):
    geturl = getattr(response, "geturl", None)
    final_url = geturl() if callable(geturl) else requested_url
    _validate_github_release_url(final_url)


def github_latest_release(timeout=15.0):
    """(tag, notes, {asset_name: url}) for the newest release, or None."""
    request = urllib.request.Request(
        "https://api.github.com/repos/{0}/releases/latest".format(GITHUB_REPO),
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": "camfrog-auto/{0}".format(APP_VERSION)})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8", "replace"))
    tag = str(data.get("tag_name") or "").lstrip("v")
    if not tag:
        return None
    assets = {}
    for asset in data.get("assets") or []:
        name = str(asset.get("name") or "")
        url = str(asset.get("browser_download_url") or "")
        if name and url:
            assets[name] = url
    return tag, str(data.get("body") or ""), assets


def check_for_update(asset_name, timeout=15.0):
    """(tag, url, notes) when a newer release carries this asset, else None."""
    found = check_release_assets(asset_name, timeout)
    return None if found is None else found[:3]


def check_release_assets(asset_name, timeout=15.0):
    """Return verified GitHub release URLs only when the asset has checksums."""
    release = github_latest_release(timeout)
    if release is None:
        return None
    tag, notes, assets = release
    url = assets.get(asset_name)
    if not url or not version_newer(tag):
        return None
    sums_url = assets.get(UPDATE_ASSET_SUMS, "")
    if not sums_url:  # e.g. release-SHA256SUMS.txt alongside SHA256SUMS.txt
        sums_url = next((value for name, value in sorted(assets.items())
                         if name.endswith("SHA256SUMS.txt")), "")
    if not sums_url:
        return None
    try:
        _validate_github_release_url(url)
        _validate_github_release_url(sums_url)
    except ValueError:
        return None
    return tag, url, sums_url, notes


def self_update(asset_name, confirm=None, timeout=15.0):
    """Check -> confirm -> download -> verify -> stage the swap.

    Returns (state, message) with state in
    ("no-update", "declined", "ready", "failed"); "ready" means the new file is
    staged as <asset>.new and camfrog-update.cmd will swap it after we exit.
    """
    found = check_release_assets(asset_name, timeout)
    if found is None:
        return "no-update", "no update available (running v{0}).".format(APP_VERSION)
    tag, url, sums_url, _notes = found
    if confirm is not None and not confirm(tag):
        return "declined", "update to v{0} declined.".format(tag)
    ok, message = stage_and_swap_update(url, asset_name, sums_url or None)
    return ("ready" if ok else "failed"), message


def _sha256_file(path, chunk=1 << 20):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def download_update(url, target, timeout=60.0):
    """Stream a GitHub release asset to `target`. Returns the bytes written."""
    _validate_github_release_url(url)
    request = urllib.request.Request(
        url, headers={"User-Agent": "camfrog-auto/{0}".format(APP_VERSION)})
    written = 0
    with urllib.request.urlopen(request, timeout=timeout) as response:
        _validate_github_response_url(response, url)
        with open(target, "wb") as handle:
            while True:
                block = response.read(1 << 16)
                if not block:
                    break
                handle.write(block)
                written += len(block)
    return written


def verify_against_sums(sums_url, asset_name, local_path, timeout=30.0):
    """True when local_path matches the GitHub release's SHA256SUMS entry."""
    _validate_github_release_url(sums_url)
    request = urllib.request.Request(
        sums_url, headers={"User-Agent": "camfrog-auto/{0}".format(APP_VERSION)})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        _validate_github_response_url(response, sums_url)
        text = response.read().decode("utf-8", "replace")
    want = ""
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        name = parts[1].lstrip("*")
        # Release sums may be flat or dist-relative; match either, first hit wins.
        if name == asset_name or name.endswith("/" + asset_name):
            want = parts[0].lower()
            break
    return bool(want) and want == _sha256_file(local_path)


def stage_and_swap_update(url, asset_name, sums_url=None):
    """Download the new exe beside this one, then swap it in after we exit.

    A running .exe cannot be overwritten on Windows, so the new file lands as
    `<asset>.new` and a small `camfrog-update.cmd` moves it into place a few
    seconds after this process exits. Returns (ok, message).
    """
    if not getattr(sys, "frozen", False):
        return False, "self-update only applies to the packaged executable."
    if not sums_url:
        return False, "release checksum is unavailable; update refused."
    if not isinstance(asset_name, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]{0,123}\.exe",
            asset_name, flags=re.IGNORECASE):
        return False, "invalid update asset name."
    try:
        _validate_github_release_url(url)
        _validate_github_release_url(sums_url)
    except ValueError as exc:
        return False, str(exc)
    exe = Path(sys.executable).resolve()
    staged = exe.parent / (asset_name + ".new")
    try:
        written = download_update(url, staged)
        if not written:
            raise OSError("empty download")
        if sums_url and not verify_against_sums(sums_url, asset_name, staged):
            staged.unlink(missing_ok=True)
            return False, "checksum mismatch; update refused."
    except Exception as exc:
        staged.unlink(missing_ok=True)
        return False, "download failed: {0}: {1}".format(type(exc).__name__, exc)
    script = exe.parent / "camfrog-update.cmd"
    script.write_text(
        "@echo off\r\n"
        "ping -n 4 127.0.0.1 >nul\r\n"
        'move /Y "{staged}" "{exe}"\r\n'
        'del "%~f0"\r\n'.format(staged=staged, exe=exe), encoding="utf-8")
    command = ["cmd", "/c", str(script)]
    spawn = {"cwd": str(exe.parent)}
    if os.name == "nt":  # CREATE_NO_WINDOW: no console flash during the swap
        spawn["creationflags"] = 0x08000000
    subprocess.Popen(command, close_fds=True, **spawn)
    return True, "update is staged; it will replace {0} after the app exits.".format(asset_name)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

