"""Camfrog web status updater - self-contained (updater logic + GUI inlined, no shared imports)."""
import argparse
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
import urllib.parse
import urllib.request
from http.cookiejar import Cookie, CookieJar, MozillaCookieJar
from pathlib import Path
import queue
import threading


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


def parse_pool(text):
    """Multi-line pool box -> [status, ...], blanks dropped."""
    return [line.strip() for line in str(text).splitlines() if line.strip()]


def parse_rotate_interval(raw):
    """Auto-switch interval in seconds. Clamped to the allowed window."""
    try:
        value = int(float(str(raw).strip()))
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("invalid interval: {0!r}".format(raw)) from exc
    return min(ROTATE_INTERVAL_MAX, max(ROTATE_INTERVAL_MIN, value))


POOL_TEXT_NAME = "web_status_pool.txt"


def default_pool_path():
    return BASE / POOL_TEXT_NAME


def save_pool_text(path, text):
    """Save the status pool text (statuses only, never secrets)."""
    Path(path).write_text(str(text), encoding="utf-8")
    return len(str(text))


def load_pool_text(path):
    """Load status pool text saved by save_pool_text."""
    return Path(path).read_text(encoding="utf-8-sig")


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
    # The observed API success acknowledgement is {"response": "ok"}.
    # No missing, empty, or unrecognized response may be treated as success.
    if data.get("response") != "ok":
        return False, "update unconfirmed: server did not acknowledge success."
    return True, "status update acknowledged by server."


def extract_csrf(html):
    """The per-session CSRF token embedded in the logged-in profile page."""
    match = re.search(r"var\s+csrf\s*=\s*['\"]([0-9a-fA-F]{16,})['\"]", html)
    return match.group(1) if match else ""

CAPTURE_STEPS = """\
To capture the real status-update endpoint:
1. Log in at https://profiles.camfrog.com/ in your browser.
2. Open devtools (F12) -> Network tab, then change your status once.
3. Find the POST/XHR request that carries the new status text.
4. Record its full URL, parameters, and which cookies it needs.
5. Hand the (redacted, password-free) request details to the maintainer so
   WEB_UPDATE_URL/WEB_UPDATE_VERIFIED above can be confirmed. Never paste
   your password or full session cookies into chat, issues, or files.
"""

COOKIE_STEPS = """\
To reuse your Chrome session (no password needed):
1. In Chrome, log in at https://profiles.camfrog.com/ as usual.
2. Export cookies with an extension such as "Get cookies.txt LOCALLY"
   (localhost-only export, nothing uploaded) for camfrog.com.
3. Save the file OUTSIDE this repository, e.g. Documents/camfrog-cookies.txt.
   (*cookies*.txt is git-ignored so it can never be committed.)
4. Run: python tools/web_status.py --login Seaza --status "..." \\
           --cookies-file <path> --probe
   Only the cookie count and domains are printed, never cookie values.
5. Do not paste cookie values into chat, issues, or files.
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
    """Build a jar from a pasted `name=value` browser cookie. Value stays in memory.

    This is the "log in in your browser" path: the real browser solves the
    CAPTCHA, the user copies the profile cookie from devtools, and the tool
    probes it (a wrong cookie simply reports a logged-out session).
    """
    pairs = []
    for chunk in str(text).replace(";", " ").split():
        if "=" in chunk:
            key, _, value = chunk.partition("=")
            key, value = key.strip(), value.strip()
            if key and value:
                pairs.append((key, value))
    if not pairs:
        raise ValueError(
            "paste a cookie as name=value (copy it from the browser's "
            "devtools: Application -> Cookies -> profiles.camfrog.com).")
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
        style.configure("TButton", padding=(9, 6), font=("Segoe UI", 9),
                        background="#d9e8f0", foreground="#1a3a52")
        style.map("TButton", background=[("active", "#bdd9e9"), ("pressed", "#a4c9df")])
        style.configure("TEntry", padding=(4, 4), fieldbackground="#ffffff",
                        foreground="#152b3a")
        style.configure("TNotebook", background="#edf2f5")
        style.configure("TNotebook.Tab", padding=(11, 6), font=("Segoe UI", 9))
        style.map("TNotebook.Tab", background=[("selected", "#ffffff")],
                  foreground=[("selected", "#096c7b")])
        self.root.title("Camfrog Web Status (prototype)")
        self.root.geometry("560x600")
        self.root.minsize(440, 380)

        self.ttk.Label(self.root, text=(
            "Update status via profiles.camfrog.com. Dry-run is the default; "
            "nothing is sent unless Send live is on. Passwords and cookie values "
            "are never stored, logged, or shown."
        ), wraplength=520).pack(fill="x", padx=12, pady=(12, 8))

        form = self.ttk.Frame(self.root, padding=(12, 0, 12, 8))
        form.pack(fill="x")
        self.ttk.Label(form, text="Nickname").grid(row=0, column=0, sticky="w")
        self.login = self.tk.StringVar(value="Seaza")
        self.ttk.Entry(form, textvariable=self.login).grid(row=0, column=1, sticky="ew", padx=6)
        self.ttk.Label(form, text="Pool (one status per line)").grid(
            row=1, column=0, sticky="nw", pady=(5, 0))
        self.pool_box = self.tk.Text(form, height=5, width=40, undo=True)
        self.pool_box.grid(row=1, column=1, sticky="ew", padx=6, pady=(5, 0))
        pool_btns = self.ttk.Frame(form)
        pool_btns.grid(row=1, column=2, sticky="n", pady=(5, 0))
        self.ttk.Button(pool_btns, text="Save text...",
                        command=self.save_pool_text).pack(fill="x")
        self.ttk.Button(pool_btns, text="Load...",
                        command=self.load_pool_text).pack(fill="x", pady=(4, 0))
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
        self.ttk.Label(timing, text="s").pack(side="left")
        self.ttk.Label(form, text="Cookies file").grid(row=3, column=0, sticky="w", pady=(5, 0))
        self.cookies = self.tk.StringVar(value=cookies_default)
        self.ttk.Entry(form, textvariable=self.cookies).grid(row=3, column=1, sticky="ew", padx=6, pady=(5, 0))
        self.ttk.Button(form, text="Browse...", command=self.browse).grid(
            row=3, column=2, sticky="w", pady=(5, 0))
        self.ttk.Button(form, text="Chrome", command=self.chrome_import).grid(
            row=3, column=3, sticky="w", pady=(5, 0))
        self.ttk.Label(form, text="Password (used once, cleared immediately)").grid(
            row=4, column=0, sticky="w", pady=(5, 0))
        self.password = self.tk.StringVar(value="")
        self.pw_entry = self.ttk.Entry(form, textvariable=self.password, show="\u2022")
        self.pw_entry.grid(row=4, column=1, sticky="ew", padx=6, pady=(5, 0))
        form.columnconfigure(1, weight=1)

        self.live = self.tk.BooleanVar(value=False)
        self.ttk.Checkbutton(form, text="Send live (otherwise dry-run preview only)",
                             variable=self.live).grid(row=5, column=0, columnspan=3,
                                                      sticky="w", pady=(8, 0))

        account = self.ttk.LabelFrame(self.root, padding=(12, 8, 12, 8),
                                      text="Account (stored encrypted)")
        account.pack(fill="x", padx=12, pady=(8, 0))
        self.ttk.Label(account, text=(
            "Saved with Windows DPAPI: the file only decrypts under your Windows "
            "user, so a copy is useless elsewhere. The password is never written "
            "in plain text, logged, or shown."
        ), wraplength=520, foreground="#555").pack(anchor="w", pady=(0, 6))
        row = self.ttk.Frame(account)
        row.pack(fill="x")
        self.ttk.Label(row, text="Nickname").pack(side="left")
        self.acct_user = self.tk.StringVar(value=(os.environ.get("CAMFROG_USER") or "").strip())
        self.ttk.Entry(row, textvariable=self.acct_user, width=18).pack(side="left", padx=6)
        self.ttk.Label(row, text="Password").pack(side="left", padx=(8, 0))
        self.acct_pw = self.tk.StringVar(value="")
        self.acct_pw_entry = self.ttk.Entry(row, textvariable=self.acct_pw,
                                            show="\u2022", width=18)
        self.acct_pw_entry.pack(side="left", padx=6)
        self.ttk.Button(row, text="Save encrypted", command=self.save_account).pack(side="left")
        self.acct_state = self.ttk.Label(account, text="", foreground="#555")
        self.acct_state.pack(anchor="w", pady=(6, 0))
        self.refresh_account_state()

        browser = self.ttk.LabelFrame(self.root, padding=(12, 8, 12, 8),
                                      text="Browser login (no closing, no export)")
        browser.pack(fill="x", padx=12, pady=(8, 0))
        self.ttk.Label(browser, text=(
            "Log in in your browser as usual (it solves the CAPTCHA for you), then "
            "copy the profile cookie from devtools: F12 -> Application -> Cookies "
            "-> profiles.camfrog.com, and paste it below. It is used in memory "
            "only and probed live."
        ), wraplength=520, foreground="#555").pack(anchor="w", pady=(0, 6))
        row2 = self.ttk.Frame(browser)
        row2.pack(fill="x")
        self.ttk.Button(row2, text="Open login page",
                        command=self.open_login_page).pack(side="left")
        self.cookie_paste_var = self.tk.StringVar(value="")
        self.ttk.Entry(row2, textvariable=self.cookie_paste_var,
                       width=34).pack(side="left", padx=6)
        self.ttk.Button(row2, text="Use pasted cookie",
                        command=self.use_pasted_cookie).pack(side="left")
        self.paste_state = self.ttk.Label(browser, text="", foreground="#555")
        self.paste_state.pack(anchor="w", pady=(6, 0))

        actions = self.ttk.Frame(self.root, padding=(12, 0, 12, 8))
        actions.pack(fill="x")
        self.ttk.Button(actions, text="Preview plan", command=self.preview).pack(side="left", padx=5)
        self.ttk.Button(actions, text="Probe session", command=self.probe).pack(side="left")
        self.ttk.Button(actions, text="Login attempt", command=self.login_attempt).pack(side="left", padx=5)
        self.ttk.Button(actions, text="Update", command=self.check_update).pack(side="left", padx=5)
        self.btn_start = self.ttk.Button(actions, text="Start", command=self.start)
        self.btn_start.pack(side="left")
        self.btn_stop = self.ttk.Button(actions, text="Stop", command=self.stop)
        self.btn_stop.pack(side="left", padx=5)
        self.ttk.Button(actions, text="How to capture", command=self.capture).pack(side="right")
        self.note = self.tk.StringVar(value="Dry-run is on. Nothing has been sent.")
        self.ttk.Label(self.root, textvariable=self.note, anchor="w",
                       padding=(12, 0, 12, 10), wraplength=530).pack(fill="x")
        self.root.after(120, self._poll)

    # ---- helpers
    def browse(self):
        from tkinter import filedialog

        path = filedialog.askopenfilename(title="Select Chrome cookies export (cookies.txt)")
        if path:
            self.cookies.set(path)
            self.chrome_mode = False

    def save_pool_text(self):
        from tkinter import filedialog

        path = filedialog.asksaveasfilename(
            title="Save status pool text",
            initialfile=POOL_TEXT_NAME,
            defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if not path:
            return
        try:
            save_pool_text(path, self.pool_box.get("1.0", "end-1c"))
        except OSError as exc:
            self.note.set("Save text failed: {0}".format(exc))
            return
        self.note.set("Saved pool text to {0}.".format(path))

    def load_pool_text(self):
        from tkinter import filedialog

        path = filedialog.askopenfilename(
            title="Load status pool text",
            filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if not path:
            return
        try:
            text = load_pool_text(path)
        except OSError as exc:
            self.note.set("Load text failed: {0}".format(exc))
            return
        self.pool_box.delete("1.0", "end")
        self.pool_box.insert("1.0", text)
        self.note.set("Loaded pool text from {0}.".format(path))

    def chrome_import(self):
        """Auto-import the session from Chrome's store (nothing saved to disk)."""
        def do():
            jar = import_chrome_jar()
            return "loaded session from Chrome: {0}".format(cookie_summary(jar))

        self._run_bg(do, on_done=lambda: setattr(self, "chrome_mode", True))

    def _run_bg(self, fn, force=False, on_done=None):
        if self.busy and not force:
            return
        self.busy = True
        self.note.set("Working...")
        threading.Thread(target=self._worker, args=(fn, on_done), daemon=True).start()

    def _worker(self, fn, on_done):
        try:
            text, ok = fn(), True
        except Exception as exc:  # shown in the GUI, never a traceback window
            text, ok = "failed: {0}: {1}".format(type(exc).__name__, exc), False
        self.q.put((ok, text, on_done))

    def _poll(self):
        try:
            while True:
                ok, text, on_done = self.q.get_nowait()
                self.busy = False
                self.note.set(text)
                if ok and on_done is not None:
                    try:
                        on_done()
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
        pool = parse_pool(self.pool_box.get("1.0", "end"))
        if not pool:
            raise ValueError("Enter at least one status line in the pool.")
        return pool

    def _fields(self):
        return self._login_name(), self._pool()

    # ---- actions (network runs in worker threads; secrets never leave memory)
    def refresh_account_state(self):
        """Show what is stored without ever revealing any value."""
        user = (os.environ.get("CAMFROG_USER") or "").strip()
        if env_enc_path().is_file():
            stored = "encrypted account on disk"
            if user:
                stored += " for {0!r}".format(user)
            self.acct_state.configure(text=stored + " (this Windows user only).")
        else:
            self.acct_state.configure(
                text="No stored account: enter one and press Save encrypted. "
                     "A saved account is all live rotation needs.")
        if user and not self.login.get().strip():
            self.login.set(user)

    def save_account(self):
        ok, message = save_credentials(self.acct_user.get(), self.acct_pw.get())
        if ok:
            self.acct_pw.set("")
            # make the new account visible to this session without re-reading it
            os.environ["CAMFROG_USER"] = self.acct_user.get().strip()
        from tkinter import messagebox
        if ok:
            messagebox.showinfo("Account", message, parent=self.root)
        else:
            messagebox.showerror("Account", message, parent=self.root)
        self.refresh_account_state()

    def open_login_page(self):
        import webbrowser
        webbrowser.open(LOGIN_PAGE_URL)
        self.paste_state.configure(
            text="Login page opened in your browser. After signing in, copy the "
                 "profile cookie and press Use pasted cookie.")

    def use_pasted_cookie(self):
        text = self.cookie_paste_var.get().strip()
        try:
            cookie_from_paste(text)
        except ValueError as exc:
            self.paste_state.configure(text=str(exc), foreground="#a00")
            return
        self.cookie_paste = text
        self.paste_state.configure(
            text="Pasted cookie ready (used in memory only).", foreground="#555")

    def _session_jar(self):
        """The cookie jar for probe/rotation: pasted cookie, Chrome, or a file."""
        if self.cookie_paste:
            return cookie_from_paste(self.cookie_paste)
        if self.chrome_mode:
            return import_chrome_jar()
        return load_cookie_jar(self.cookies.get().strip())

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
        except ValueError as exc:
            self.note.set(str(exc))
            return
        if not (self.cookies.get().strip() or self.cookie_paste):
            self.note.set("Paste a cookie (Browser login) or pick a cookies file "
                          "first (Browse...).")
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

    def login_attempt(self):
        try:
            login = self._login_name()
        except ValueError as exc:
            self.note.set(str(exc))
            return
        password = self.password.get()
        if not password:
            self.note.set("Enter the password first (used once, cleared immediately).")
            return
        timeout = self._timeout_value()
        if timeout is None:
            return

        def do():
            import urllib.request
            from http.cookiejar import CookieJar

            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
            reply = attempt_login(opener, login, password, timeout)
            _code, message = handle_login_reply(reply)
            return message

        self.pw_entry.delete(0, "end")  # main thread: widget cleared before spawn
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
        live = self.live.get()
        if live and not (self.cookies.get().strip() or self.cookie_paste
                         or self.chrome_mode or stored_account()):
            self.note.set("Live needs a cookies file, the Chrome button (Chrome "
                          "closed), or a saved account - save one in the Account "
                          "section above.")
            return
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
        self._cycle(login, pool, interval, timeout, live, 0)

    def stop(self):
        self.switching = False
        self.chrome_mode = False  # Stop also drops an imported Chrome session
        if self.rotate_job is not None:
            try:
                self.root.after_cancel(self.rotate_job)
            except Exception:
                pass
            self.rotate_job = None
        self.note.set("Auto-switch stopped. Nothing further will be sent.")

    def _cycle(self, login, pool, interval, timeout, live, index):
        if not self.switching:
            return
        try:
            pool = parse_pool(self.pool_box.get("1.0", "end")) or pool
            status, _ = next_rotation(pool, index)
        except ValueError as exc:
            self.note.set(str(exc))
            self.stop()
            return
        # main thread: no Tk calls in the worker; the jar is built there

        def do():
            if not live:
                return "cycle #{0}/{1} (dry-run): {2}".format(index + 1, len(pool), status)
            account = stored_account()
            if account is not None:
                user, password = account
                code, message = live_update(user, password, status, timeout, confirm=True)
                return "cycle #{0}/{1}: {2}".format(index + 1, len(pool), message)
            import urllib.request

            try:
                jar = self._session_jar()
            except (OSError, ValueError) as exc:
                return "cycle #{0}/{1} stopped: {2}".format(index + 1, len(pool), exc)
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
            ok, message = perform_update(opener, login, status, timeout, confirm=True)
            return "cycle #{0}/{1}: {2}".format(index + 1, len(pool), message)

        self._run_bg(do, force=True)
        _, nxt = next_rotation(pool, index)
        self.rotate_job = self.root.after(max(1, interval) * 1000,
                                          self._cycle, login, pool, interval, timeout, live, nxt)


# ---------- self-update from the GitHub release ----------
# Read-only GitHub API (no token needed for public repos, stdlib only). Each
# packaged app checks the same repo's latest release and downloads only its
# own executable asset, verified against the release's SHA256SUMS.txt.
APP_VERSION = "2.19.1"
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

