"""Camfrog web status updater - self-contained (updater logic + GUI inlined, no shared imports)."""
import argparse
import datetime
import getpass
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import base64
import random
import socket
import time
import urllib.parse
import urllib.request
from http.cookiejar import Cookie, CookieJar, MozillaCookieJar
from pathlib import Path
import queue
import threading
import unicodedata


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

ROTATE_INTERVAL_MIN = 30
ROTATE_INTERVAL_DEFAULT = 300
ROTATE_INTERVAL_MAX = 86400

WEB_MARQUEE_STEP_SECONDS = 5
WEB_MARQUEE_WIDTH = 28
WEB_MARQUEE_STRIDE = 2
WEB_MARQUEE_SEPARATOR = "   \u2022   "
WEB_MARQUEE_MAX_FRAMES = 80

WEB_STATUS_LOG_NAME = "web_status.log"
WEB_STATUS_LOG_MAX_BYTES = 512 * 1024
WEB_STATUS_LOG_BACKUPS = 3
WEB_STATUS_LOG_GUI_LINES = 200
WEB_STATUS_LOG_EVENTS = {
    "session_verification_started": "Session verification started",
    "session_verification_succeeded": "Session verification succeeded",
    "session_verification_failed": "Session verification failed",
    "browser_login_started": "Browser login started",
    "browser_session_captured": "Browser session captured",
    "status_lines_saved": "Status lines saved",
    "dry_run_rotation_started": "Dry-run rotation started",
    "live_rotation_started": "Live rotation started",
    "marquee_completed": "Marquee completed all populated slots",
    "status_previewed": "Dry-run status previewed",
    "status_update_succeeded": "Live status update succeeded",
    "status_update_failed": "Live status update failed",
    "rotation_stopped": "Rotation stopped",
}
_WEB_STATUS_LOG_LOCK = threading.Lock()


def web_status_log_path():
    return BASE / WEB_STATUS_LOG_NAME


def _web_status_log_entry(event, now=None):
    try:
        label = WEB_STATUS_LOG_EVENTS[event]
    except (KeyError, TypeError) as exc:
        raise ValueError("unknown activity") from exc
    timestamp = now or datetime.datetime.now().astimezone()
    return "{0:%Y-%m-%d %H:%M:%S %z} | {1}".format(timestamp, label)


def load_web_status_log(path=None):
    """Load only the bounded, most recent activity lines for the GUI."""
    log_path = Path(path) if path is not None else web_status_log_path()
    if not log_path.exists():
        return []
    with log_path.open("r", encoding="utf-8", errors="replace") as stream:
        return [line.rstrip("\r\n") for line in stream.readlines()[-WEB_STATUS_LOG_GUI_LINES:]
                if line.strip()]


def append_web_status_log(event, path=None, now=None):
    """Append one allowlisted event; callers cannot add status or session data."""
    entry = _web_status_log_entry(event, now)
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
        value = int(float(str(raw).strip()))
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("invalid interval: {0!r}".format(raw)) from exc
    return min(ROTATE_INTERVAL_MAX, max(ROTATE_INTERVAL_MIN, value))


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


TIMEOUT_MIN = 5.0
TIMEOUT_DEFAULT = 20.0
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


def perform_update(opener, status, timeout, confirm=False):
    """Single gated send point for one rotation tick. Returns (ok, message).

    Reads the profile page for its per-session CSRF token, then POSTs the new
    status. Refuses unless confirm=True (fail closed until a live round-trip is
    confirmed by the operator).
    """
    if not confirm:
        return False, ("update refused: endpoint captured from home.php but not "
                       "confirmed end to end yet; pass --confirm-update to send "
                       "for real (dry-run preview only).")
    html = fetch_profile(opener, "", timeout)
    csrf = extract_csrf(html)
    if not csrf:
        return False, ("update refused: no CSRF token on the profile page "
                       "(session expired or not signed in).")
    reply = _post(opener, WEB_UPDATE_URL, {"status": status, "csrf": csrf}, timeout)
    try:
        data = json.loads(reply)
    except ValueError:
        return False, "update refused: unrecognized server reply ({0}).".format(
            reply[:60])
    if not isinstance(data, dict):
        return False, "update refused: invalid server response format."
    if data.get("error"):
        return False, "update refused by the server (error response)."
    # Camfrog's profile form treats a non-empty response string as success and
    # writes it back into the status field. It does not require the literal "ok".
    response = data.get("response")
    if not isinstance(response, str) or not response.strip():
        return False, "update unconfirmed: server did not acknowledge success."
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
    parser.add_argument("--timeout", type=float, default=20.0)
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
        return response.read().decode("utf-8", "replace").strip()


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


class WebStatusManager:
    def __init__(self, cookies_default=""):
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.ttk = ttk
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
        load_dotenv(BASE / ".env")  # pick up the encrypted account, if saved
        self.root = self.tk.Tk()
        style = self.ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except self.tk.TclError:
            pass
        style.configure("TFrame", background="#edf2f5")
        style.configure("TLabel", background="#edf2f5", foreground="#233548", font=("Segoe UI", 9))
        style.configure("TCheckbutton", background="#edf2f5", foreground="#233548")
        style.configure("TRadiobutton", background="#edf2f5", foreground="#233548")
        style.configure("TLabelframe", background="#edf2f5", bordercolor="#c4d1dc")
        style.configure("TLabelframe.Label", background="#edf2f5", foreground="#087b83",
                        font=("Segoe UI", 9, "bold"))
        style.configure("TButton", padding=(7, 4), font=("Segoe UI", 9),
                        background="#d9e8f0", foreground="#1a3a52")
        style.map("TButton", background=[("active", "#bdd9e9"), ("pressed", "#a4c9df")])
        style.configure("TEntry", padding=(4, 4), fieldbackground="#ffffff",
                        foreground="#152b3a")
        style.configure("TNotebook", background="#edf2f5")
        style.configure("TNotebook.Tab", padding=(11, 6), font=("Segoe UI", 9))
        style.map("TNotebook.Tab", background=[("selected", "#ffffff")],
                  foreground=[("selected", "#096c7b")])
        self.root.title("Camfrog Web Status (prototype)")
        self.root.geometry("500x620")
        self.root.minsize(480, 560)

        self.ttk.Label(self.root, text=(
            "Update status via profiles.camfrog.com. Dry-run is the default; "
            "nothing is sent unless Send live is on. Passwords and cookie values "
            "are never stored, logged, or shown."
        ), wraplength=440).pack(fill="x", padx=10, pady=(8, 6))

        self.nb = self.ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=10)
        setup_tab = self.ttk.Frame(self.nb, padding=(10, 6, 10, 6))
        session_tab = self.ttk.Frame(self.nb, padding=(10, 6, 10, 6))
        log_tab = self.ttk.Frame(self.nb, padding=(8, 6, 8, 6))
        self.nb.add(setup_tab, text="Setup")
        self.nb.add(session_tab, text="Account & Session")
        self.nb.add(log_tab, text="Activity Log")
        pool_lines, pool_load_warning = load_web_text_slots()

        form = self.ttk.Frame(setup_tab)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        self.ttk.Label(form, text="Nickname").grid(row=0, column=0, sticky="w")
        self.login = self.tk.StringVar(value="Seaza")
        self.ttk.Entry(form, textvariable=self.login).grid(row=0, column=1, sticky="ew", padx=6)
        self.ttk.Label(form, text="Status lines").grid(
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
        self.btn_save_web_text = self.ttk.Button(
            pool_btns, text="Save to webtext.db", command=self.save_web_texts)
        self.btn_save_web_text.pack(fill="x")
        self.ttk.Label(form, text="Switch every").grid(row=2, column=0, sticky="w", pady=(5, 0))
        timing = self.ttk.Frame(form)
        timing.grid(row=2, column=1, sticky="w", padx=6, pady=(5, 0))
        self.interval = self.tk.StringVar(value=str(ROTATE_INTERVAL_DEFAULT))
        self.ttk.Spinbox(timing, textvariable=self.interval,
                         from_=ROTATE_INTERVAL_MIN, to=ROTATE_INTERVAL_MAX,
                         increment=30, width=6).pack(side="left")
        self.ttk.Label(timing, text="s (min 30)").pack(side="left", padx=(4, 0))
        self.ttk.Label(timing, text="Timeout").pack(side="left", padx=(10, 0))
        self.timeout = self.tk.StringVar(value=str(TIMEOUT_DEFAULT))
        self.ttk.Entry(timing, textvariable=self.timeout, width=6).pack(side="left", padx=(3, 0))
        self.live = self.tk.BooleanVar(value=False)
        self.ttk.Checkbutton(form, text="Send live (otherwise dry-run preview only)",
                             variable=self.live).grid(row=3, column=0, columnspan=3,
                                                      sticky="w", pady=(6, 0))
        modes = self.ttk.Frame(form)
        modes.grid(row=4, column=0, columnspan=3, sticky="w", pady=(2, 0))
        self.marquee_mode = self.tk.BooleanVar(value=False)
        self.infinity_loop = self.tk.BooleanVar(value=True)
        self.ttk.Checkbutton(
            modes, text="Marquee (5 seconds per frame)",
            variable=self.marquee_mode).pack(side="left")
        self.ttk.Checkbutton(
            modes, text="Infinity Loop (last slot → slot 1)",
            variable=self.infinity_loop).pack(side="left", padx=(8, 0))

        browser = self.ttk.LabelFrame(session_tab, padding=(10, 6, 10, 6),
                                      text="Session (PHPSESSID via iframe / web login)")
        browser.pack(fill="x")
        self.ttk.Label(browser, text=(
            "Log in in your browser (via iframe/web login). In devtools Network tab, "
            "inspect https://profiles.camfrog.com/home.php to get PHPSESSID=..., "
            "paste below, then press 'Login' to verify and arm automation."
        ), wraplength=440, foreground="#555").pack(anchor="w", pady=(0, 4))
        row2 = self.ttk.Frame(browser)
        row2.pack(fill="x")
        self.ttk.Button(row2, text="Open login page",
                        command=self.open_login_page).pack(side="left")
        self.cookie_paste_var = self.tk.StringVar(value="")
        self.ttk.Entry(row2, textvariable=self.cookie_paste_var,
                       width=18).pack(side="left", padx=6, fill="x", expand=True)
        session_actions = self.ttk.Frame(browser)
        session_actions.pack(fill="x", pady=(4, 0))
        self.btn_login = self.ttk.Button(
            session_actions, text="Login", command=self.login_session)
        self.btn_login.pack(side="left")
        self.ttk.Button(session_actions, text="Login in browser",
                        command=self.login_via_browser).pack(side="left", padx=(6, 0))
        self.paste_state = self.ttk.Label(browser, text="", foreground="#555")
        self.paste_state.pack(anchor="w", pady=(4, 0))

        log_frame = self.ttk.Frame(log_tab)
        log_frame.pack(fill="both", expand=True)
        log_scroll = self.ttk.Scrollbar(log_frame, orient="vertical")
        log_scroll.pack(side="right", fill="y")
        self.log_view = self.tk.Text(
            log_frame, wrap="word", height=12, state="disabled",
            yscrollcommand=log_scroll.set)
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
        self.ttk.Button(actions, text="Preview plan", command=self.preview).pack(side="left", padx=5)
        self.ttk.Button(actions, text="Probe session", command=self.probe).pack(side="left")
        self.ttk.Button(actions, text="Update", command=self.check_update).pack(side="left", padx=5)
        actions2 = self.ttk.Frame(self.root, padding=(10, 0, 10, 6))
        actions2.pack(fill="x")
        self.btn_start = self.ttk.Button(actions2, text="Start", command=self.start)
        self.btn_start.pack(side="left", padx=(5, 0))
        self.btn_stop = self.ttk.Button(actions2, text="Stop", command=self.stop)
        self.btn_stop.pack(side="left", padx=5)
        self.ttk.Button(actions2, text="How to capture", command=self.capture).pack(side="right")
        self.note = self.tk.StringVar(value="Dry-run is on. Nothing has been sent.")
        if pool_load_warning:
            self.note.set(pool_load_warning)
        elif log_load_warning:
            self.note.set(log_load_warning)
        self.ttk.Label(self.root, textvariable=self.note, anchor="w",
                       padding=(10, 0, 10, 8), wraplength=450).pack(fill="x")
        self.root.after(120, self._poll)

    # ---- helpers
    def chrome_import(self):
        """Auto-import the session from Chrome's store (nothing saved to disk)."""
        def do():
            jar = import_chrome_jar()
            return "loaded session from Chrome: {0}".format(cookie_summary(jar))

        self._run_bg(do, on_done=lambda: setattr(self, "chrome_mode", True))

    def _run_bg(self, fn, force=False, on_done=None, on_error=None):
        if self.busy and not force:
            return
        self.busy = True
        self.note.set("Working...")
        threading.Thread(target=self._worker, args=(fn, on_done, on_error), daemon=True).start()

    def _worker(self, fn, on_done, on_error):
        try:
            text, ok = fn(), True
        except Exception as exc:  # shown in the GUI, never a traceback window
            text, ok = "failed: {0}: {1}".format(type(exc).__name__, exc), False
        self.q.put((ok, text, on_done, on_error))

    def _show_log_lines(self, lines):
        if not hasattr(self, "log_view"):
            return
        self.log_view.configure(state="normal")
        self.log_view.delete("1.0", "end")
        self.log_view.insert("end", "\n".join(lines[-WEB_STATUS_LOG_GUI_LINES:]))
        if lines:
            self.log_view.insert("end", "\n")
        self.log_view.configure(state="disabled")
        self.log_view.see("end")

    def _append_log_line(self, entry):
        if not hasattr(self, "log_view"):
            return
        self.log_view.configure(state="normal")
        self.log_view.insert("end", entry + "\n")
        line_count = int(self.log_view.index("end-1c").split(".", 1)[0])
        excess = max(0, line_count - WEB_STATUS_LOG_GUI_LINES - 1)
        if excess:
            self.log_view.delete("1.0", "{0}.0".format(excess + 1))
        self.log_view.configure(state="disabled")
        self.log_view.see("end")

    def _record_activity(self, event):
        try:
            entry = append_web_status_log(event)
        except (OSError, ValueError) as exc:
            try:
                entry = _web_status_log_entry(event)
            except ValueError:
                return
            if hasattr(self, "note"):
                self.note.set("Could not write web_status.log ({0}).".format(
                    type(exc).__name__))
        self._append_log_line(entry)

    def _poll(self):
        try:
            while True:
                ok, text, on_done, on_error = self.q.get_nowait()
                self.busy = False
                self.note.set(text)
                callback = on_done if ok else on_error
                if callback is not None:
                    try:
                        callback()
                    except Exception as exc:
                        self.note.set("{0} ({1})".format(text, exc))
        except queue.Empty:
            pass
        try:
            self.root.after(120, self._poll)
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
            self.note.set("Could not save status lines to webtext.db: {0}".format(
                type(exc).__name__))
            return False
        self._record_activity("status_lines_saved")
        if notify:
            self.note.set("Saved status lines to webtext.db.")
        return True

    def save_web_texts(self):
        self._save_web_texts()

    def _fields(self):
        return self._login_name(), self._pool()

    # ---- actions (network runs in worker threads; secrets never leave memory)
    def open_login_page(self):
        import webbrowser
        webbrowser.open(LOGIN_PAGE_URL)
        self.paste_state.configure(
            text="Login page opened. After signing in, capture PHPSESSID on "
                 "https://profiles.camfrog.com/home.php, paste it, then press Login.")

    def use_pasted_cookie(self):
        try:
            self._sync_pasted_cookie()
        except ValueError as exc:
            self.paste_state.configure(text=str(exc), foreground="#a00")
            return
        self.paste_state.configure(
            text="PHPSESSID ready in memory. Click Login to verify.", foreground="#555")

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
        """The cookie jar for probe/rotation: single flow using pasted PHPSESSID."""
        if not self.cookie_paste:
            raise ValueError("Enter or paste PHPSESSID first (Session tab).")
        return cookie_from_paste(self.cookie_paste)

    def _verify_session(self, login, timeout, on_done):
        """Probe PHPSESSID session in a worker; on_done runs on success."""

        def do():
            import urllib.request

            jar = self._session_jar()
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
            html = fetch_profile(opener, login, timeout)
            verdict, detail = summarize_session(html)
            if verdict != "signed-in":
                raise ValueError(detail)
            return detail

        self._record_activity("session_verification_started")

        def verified():
            self._record_activity("session_verification_succeeded")
            on_done()

        self._run_bg(
            do, force=True, on_done=verified,
            on_error=lambda: self._record_activity("session_verification_failed"))

    def login_via_browser(self):
        """One-click login: the real browser solves the CAPTCHA and the
        HttpOnly session cookie comes back through DevTools."""
        if find_browser() is None:
            self.note.set("No Chrome or Edge found on this computer.")
            return
        self._record_activity("browser_login_started")
        self.note.set("Browser opened - sign in there; this window confirms by itself.")

        def work():
            cookies, _profile = browser_login(
                on_status=lambda text: self.root.after(
                    0, lambda: self.note.set(text)))
            self.root.after(0, lambda: self._browser_login_done(cookies))
            return "done"

        self._run_bg(work, force=True)

    def _browser_login_done(self, cookies):
        try:
            cookie_from_paste(cookies)  # validate before adopting
        except ValueError as exc:
            self.note.set(str(exc))
            return
        self.cookie_paste = cookies
        self._cookie_from_browser = True
        self.cookie_paste_var.set("")
        self.session_ready = False
        self._invalidate_pending_start()
        self._record_activity("browser_session_captured")
        self.paste_state.configure(text="Session captured from browser.",
                                   foreground="#555")
        self._verify_session(self._login_name(),
                             self._timeout_value() or 20.0, self._on_logged_in)

    def login_session(self):
        """Verify the captured session live, arm automation on success."""
        try:
            login = self._login_name()
            self._sync_pasted_cookie()
        except ValueError as exc:
            self.note.set(str(exc))
            return
        timeout = self._timeout_value()
        if timeout is None:
            return
        self.session_ready = False
        self.paste_state.configure(text="Verifying PHPSESSID...", foreground="#555")
        self._verify_session(login, timeout, self._on_logged_in)

    def _on_logged_in(self):
        self.session_ready = True
        self.paste_state.configure(text="Logged in via PHPSESSID - automation armed.",
                                   foreground="#060")

    def preview(self):
        try:
            login, pool = self._fields()
        except ValueError as exc:
            self.note.set(str(exc))
            return
        live = self.live.get()
        self.note.set(build_plan(login, pool[0])
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
            self.note.set(str(exc))
            return None

    def probe(self):
        try:
            login = self._login_name()
            self._sync_pasted_cookie()
        except ValueError as exc:
            self.note.set(str(exc))
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
        self.note.set(CAPTURE_STEPS + COOKIE_STEPS)

    # ---- one-click auto-switch rotation (same fail-closed gates as one-shot ops)
    def start(self):
        if self.switching:
            return
        try:
            login, pool = self._fields()
            interval = parse_rotate_interval(self.interval.get())
            timeout = parse_timeout(self.timeout.get())
        except ValueError as exc:
            self.note.set(str(exc))
            return
        if not self._save_web_texts(notify=False):
            return
        live = self.live.get()
        if live:
            try:
                self._sync_pasted_cookie()
            except ValueError as exc:
                self.note.set(str(exc))
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
                "Send for real?",
                "This will sign in and POST your status to Camfrog for real.\n"
                "Continue?", parent=self.root)
            if not ok:
                self.note.set("Live start cancelled. Nothing was sent.")
                return
            self._live_confirmed = True
        self.switching = True
        self._cycle_marquee = (bool(self.marquee_mode.get())
                               if hasattr(self, "marquee_mode") else False)
        self._cycle_infinity_loop = (bool(self.infinity_loop.get())
                                     if hasattr(self, "infinity_loop") else True)
        self._record_activity("live_rotation_started" if live else "dry_run_rotation_started")
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
        self.paste_state.configure(text="Logged in - automation armed.",
                                   foreground="#060")
        login, pool, interval, timeout = pending[:4]
        from tkinter import messagebox
        ok = messagebox.askyesno(
            "Send for real?",
            "Logged in. This will POST your status to Camfrog for real.\n"
            "Continue?", parent=self.root)
        if not ok:
            self.note.set("Live start cancelled. Nothing was sent.")
            return
        self._live_confirmed = True
        self.switching = True
        self._cycle_marquee = (bool(self.marquee_mode.get())
                               if hasattr(self, "marquee_mode") else False)
        self._cycle_infinity_loop = (bool(self.infinity_loop.get())
                                     if hasattr(self, "infinity_loop") else True)
        self._record_activity("live_rotation_started")
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
        self.note.set("Auto-switch stopped. Nothing further will be sent.")
        if was_active:
            self._record_activity("rotation_stopped")

    def _cycle(self, login, pool, interval, timeout, live, index, frame_index=0,
               generation=None):
        if not self.switching:
            return
        current_generation = getattr(self, "_start_generation", 0)
        if generation is None:
            generation = current_generation
        if generation != current_generation:
            return
        try:
            pool = self._pool_values() or pool
            if not pool:
                raise ValueError("status pool is empty; add at least one line.")
            status = pool[index % len(pool)]
        except ValueError as exc:
            self.note.set(str(exc))
            self.stop()
            return
        marquee_setting = getattr(self, "marquee_mode", None)
        infinity_setting = getattr(self, "infinity_loop", None)
        marquee = bool(getattr(
            self, "_cycle_marquee",
            marquee_setting.get() if marquee_setting is not None else False))
        infinity_loop = bool(getattr(
            self, "_cycle_infinity_loop",
            infinity_setting.get() if infinity_setting is not None else True))
        frames = web_status_frames(status, enabled=marquee)
        frame_index = min(frame_index, len(frames) - 1)
        frame = frames[frame_index]
        slot_index = index % len(pool)
        step_delay = WEB_MARQUEE_STEP_SECONDS if marquee else interval

        def do():
            if not live:
                return "cycle #{0}/{1} (dry-run): {2}".format(
                    index + 1, len(pool), frame)
            import urllib.request

            try:
                jar = self._session_jar()
            except (OSError, ValueError) as exc:
                raise ValueError("cycle #{0}/{1} stopped: {2}".format(
                    index + 1, len(pool), exc)) from exc
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
            ok, message = perform_update(opener, frame, timeout, confirm=True)
            if not ok:
                raise RuntimeError(message)
            return "cycle #{0}/{1}: {2}".format(index + 1, len(pool), message)

        def advance():
            if (not self.switching
                    or generation != getattr(self, "_start_generation", 0)):
                return
            if not marquee:
                next_index = (slot_index + 1) % len(pool)
                next_frame = 0
            elif frame_index + 1 < len(frames):
                next_index = slot_index
                next_frame = frame_index + 1
            elif slot_index + 1 < len(pool):
                next_index = slot_index + 1
                next_frame = 0
            elif infinity_loop:
                next_index = 0
                next_frame = 0
            else:
                self.switching = False
                self.rotate_job = None
                self.session_ready = False
                self.chrome_mode = False
                self._invalidate_pending_start()
                self._record_activity("marquee_completed")
                self.note.set("Marquee completed all populated slots.")
                return
            self.rotate_job = self.root.after(
                max(1, int(step_delay)) * 1000, self._cycle,
                login, pool, interval, timeout, live, next_index, next_frame,
                generation)

        def failed():
            self.switching = False
            self.rotate_job = None
            self.session_ready = False
            self.chrome_mode = False
            self._invalidate_pending_start()
            self._record_activity("status_update_failed" if live else "rotation_stopped")

        self._run_bg(
            do, force=True, on_done=lambda: (
                self._record_activity("status_update_succeeded" if live
                                      else "status_previewed"),
                advance()), on_error=failed)


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


def _free_port():
    for _ in range(40):
        port = random.randint(49152, 59999)
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return 0


# ---------------------------------------------------------------- devtools ws
class _WebSocket:
    """Minimal RFC 6455 client: one connection, text frames, no extensions."""

    def __init__(self, url):
        if not url.startswith("ws://"):
            raise ValueError("only ws:// devtools URLs are supported")
        hostport, _, path = url[5:].partition("/")
        host, _, port = hostport.partition(":")
        self.sock = socket.create_connection((host, int(port or 80)), timeout=10)
        key = base64.b64encode(bytes(random.getrandbits(8) for _ in range(16)))
        handshake = (
            "GET /{path} HTTP/1.1\r\n"
            "Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).format(path=path, host=host, port=port or 80, key=key.decode())
        self.sock.sendall(handshake.encode())
        self._read_http_headers()
        self.buf = b""

    def _read_http_headers(self):
        data = b""
        while b"\r\n\r\n" not in data:
            block = self.sock.recv(4096)
            if not block:
                raise OSError("devtools websocket closed during handshake")
            data += block
        head, self.buf = data.split(b"\r\n\r\n", 1)
        if b" 101 " not in head.split(b"\r\n")[0]:
            raise OSError("devtools websocket handshake refused")

    def send_text(self, text):
        payload = text.encode("utf-8")
        header = bytearray([0x81])  # FIN + text
        mask = bytes(random.getrandbits(8) for _ in range(4))
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
        mask = bytes(random.getrandbits(8) for _ in range(4))
        header = bytearray([0x80 | opcode, 0x80 | len(payload)])
        self.sock.sendall(bytes(header) + mask
                          + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def _http_json(url):
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def _find_page_target(port):
    targets = _http_json("http://127.0.0.1:{0}/json/list".format(port))
    for target in targets:
        if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
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
    for cookie_from_paste(). Raises OSError/RuntimeError on failure.
    """
    browser = browser or find_browser()
    if not browser:
        raise OSError("no Chrome or Edge found on this computer")
    port = _free_port()
    tmp = Path(profile_dir) if profile_dir else Path(
        tempfile.mkdtemp(prefix="camfrog-login-"))
    tmp.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(
        [browser, "--remote-debugging-port={0}".format(port),
         "--user-data-dir={0}".format(tmp), "--no-first-run",
         "--no-default-browser-check", "--new-window", LOGIN_PAGE],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=0x08000000, close_fds=True)
    if on_status:
        on_status("browser opened")
    ws = None
    try:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if ws is None:
                    ws = _WebSocket(_find_page_target(port))
                cookies = _cdp_call(ws, "Network.getAllCookies").get(
                    "result", {}).get("cookies", [])
                if any(c.get("name") == SESSION_COOKIE and "camfrog" in (c.get("domain") or "")
                       for c in cookies):
                    return _cookies_to_string(cookies), str(tmp)
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
    """(tag, url, sums_url, notes) for a newer release carrying `asset_name`."""
    release = github_latest_release(timeout)
    if release is None:
        return None
    tag, notes, assets = release
    url = assets.get(asset_name)
    if url and version_newer(tag):
        sums_url = assets.get(UPDATE_ASSET_SUMS, "")
        if not sums_url:  # e.g. release-SHA256SUMS.txt alongside SHA256SUMS.txt
            sums_url = next((u for n, u in sorted(assets.items())
                             if n.endswith("SHA256SUMS.txt")), "")
        return tag, url, sums_url, notes
    return None


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
    """Stream a release asset to `target`. Returns the bytes written."""
    request = urllib.request.Request(
        url, headers={"User-Agent": "camfrog_auto/{0}".format(APP_VERSION)})
    written = 0
    with urllib.request.urlopen(request, timeout=timeout) as response, \
            open(target, "wb") as handle:
        while True:
            block = response.read(1 << 16)
            if not block:
                break
            handle.write(block)
            written += len(block)
    return written


def verify_against_sums(sums_url, asset_name, local_path, timeout=30.0):
    """True when local_path matches the release's SHA256SUMS entry."""
    request = urllib.request.Request(
        sums_url, headers={"User-Agent": "camfrog-auto/{0}".format(APP_VERSION)})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        text = response.read().decode("utf-8", "replace")
    want = ""
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        name = parts[1].lstrip("*")
        # release sums may be flat ("room-control.exe") or dist-relative
        # ("room-control/room-control.exe"); match either, first hit wins.
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
    return True, "update downloaded; the app will restart itself with {0}.".format(asset_name)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

