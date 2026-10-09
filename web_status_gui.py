"""Camfrog web status updater - self-contained (updater logic + GUI inlined, no shared imports)."""
import argparse
import getpass
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import urllib.parse
import urllib.request
from http.cookiejar import Cookie, CookieJar, MozillaCookieJar
import queue
import threading


# ============================================================
# Inlined updater logic (tools/web_status.py), main -> cli_main.
# ============================================================



LOGIN_URL = "https://www.camfrog.com/en/login/check.php"
PROFILE_URL = "https://profiles.camfrog.com/{0}"

LOGIN_URL = "https://www.camfrog.com/en/login/check.php"

# No verified status-update endpoint yet. Keep False until captured from a
# logged-in browser session (see --how-to-capture) and confirmed end to end.
WEB_UPDATE_VERIFIED = False
WEB_UPDATE_URL = ""

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


def next_rotation(pool, index):
    """Round-robin step. Returns (status, next_index). Empty pool -> ValueError."""
    if not pool:
        raise ValueError("status pool is empty; add at least one line.")
    return pool[index % len(pool)], (index + 1) % len(pool)


def perform_update(opener, login, status, timeout):
    """Single gated send point for one rotation tick. Returns (ok, message)."""
    if not WEB_UPDATE_VERIFIED or not WEB_UPDATE_URL:
        return False, ("update refused: no verified status-update endpoint "
                       "(dry-run preview only). Run --how-to-capture.")
    return False, "endpoint gate: update path not implemented yet."

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
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--how-to-capture", action="store_true",
                        help="print how to capture the update endpoint and exit")
    return parser


def build_plan(login, status):
    return ("dry-run: would sign in as {login!r} at {url} and set status "
            "{profile} to {n} chars.".format(
                login=login, url=LOGIN_URL,
                profile=PROFILE_URL.format(login),
                n=len(status)))


def load_cookie_jar(path):
    """Load a Netscape cookie.txt export. Raises ValueError with a safe message."""
    jar = MozillaCookieJar(path)
    try:
        jar.load(ignore_discard=True, ignore_expires=True)
    except Exception as exc:
        raise ValueError("cannot load cookies file: {0}: {1}".format(
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
            with tempfile.TemporaryDirectory(prefix="camfrog-chrome-") as tmp:
                snapshot = os.path.join(tmp, "Cookies")
                shutil.copyfile(db, snapshot)
                connection = sqlite3.connect(snapshot)
                try:
                    rows = connection.execute(
                        "SELECT host_key, name, value, encrypted_value, path, "
                        "is_secure, expires_utc FROM cookies").fetchall()
                finally:
                    connection.close()
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
    request = urllib.request.Request(PROFILE_URL.format(login))
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
    return ("unconfirmed",
            "no login wall found (page: {0!r}, {1} chars) but login is UNCONFIRMED "
            "without a known signed-in marker; confirm visually before any live "
            "use.".format(title, len(html)))


def _post(opener, url, fields, timeout):
    data = urllib.parse.urlencode(fields).encode("utf-8")
    request = urllib.request.Request(url, data=data)
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
        if not WEB_UPDATE_VERIFIED or not WEB_UPDATE_URL:
            return EXIT_BLOCKED, ("logged in, but no verified status-update endpoint: "
                                  "refusing to guess it. Run --how-to-capture.")
        return EXIT_BLOCKED, "endpoint gate: update path not implemented yet."
    return EXIT_USAGE, "web login failed: unexpected server reply."


def cli_main(argv=None):
    args = build_parser().parse_args(argv)
    if args.how_to_capture:
        print(CAPTURE_STEPS)
        print(COOKIE_STEPS)
        return EXIT_OK
    if not args.login or not args.status:
        build_parser().error("--login and --status are required")
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
        print("no status was changed; updates stay gated until the endpoint is verified.")
        return EXIT_OK
    if not args.live:
        print(build_plan(args.login, args.status))
        return EXIT_OK
    try:
        password = getpass.getpass("Camfrog password for {0!r}: ".format(args.login))
    except (EOFError, KeyboardInterrupt):
        print("password prompt cancelled; nothing was sent.")
        return EXIT_USAGE
    if not password:
        print("empty password; nothing was sent.")
        return EXIT_USAGE
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    try:
        reply = attempt_login(opener, args.login, password, args.timeout)
    except Exception as exc:
        print("web login request failed: {0}: {1}".format(type(exc).__name__, exc))
        return EXIT_USAGE
    finally:
        del password
    code, message = handle_login_reply(reply)
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
        self.root = self.tk.Tk()
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
        self.ttk.Label(form, text="Switch every").grid(row=2, column=0, sticky="w", pady=(5, 0))
        timing = self.ttk.Frame(form)
        timing.grid(row=2, column=1, sticky="w", padx=6, pady=(5, 0))
        self.interval = self.tk.StringVar(value=str(ROTATE_INTERVAL_DEFAULT))
        self.ttk.Spinbox(timing, textvariable=self.interval,
                         from_=ROTATE_INTERVAL_MIN, to=ROTATE_INTERVAL_MAX,
                         increment=30, width=6).pack(side="left")
        self.ttk.Label(timing, text="s (min 30)").pack(side="left", padx=(4, 0))
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

        actions = self.ttk.Frame(self.root, padding=(12, 0, 12, 8))
        actions.pack(fill="x")
        self.ttk.Button(actions, text="Preview plan", command=self.preview).pack(side="left", padx=5)
        self.ttk.Button(actions, text="Probe session", command=self.probe).pack(side="left")
        self.ttk.Button(actions, text="Login attempt", command=self.login_attempt).pack(side="left", padx=5)
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
    def preview(self):
        try:
            login, pool = self._fields()
        except ValueError as exc:
            self.note.set(str(exc))
            return
        live = self.live.get()
        self.note.set(build_plan(login, pool[0])
                      + (" LIVE ARMED (still gated)." if live else ""))

    def probe(self):
        try:
            login = self._login_name()
        except ValueError as exc:
            self.note.set(str(exc))
            return
        path = self.cookies.get().strip()
        if not path:
            self.note.set("Pick a Chrome cookies export first (Browse...).")
            return

        def do():
            import urllib.request

            jar = load_cookie_jar(path)
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
            html = fetch_profile(opener, login, 20.0)
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

        def do():
            import urllib.request
            from http.cookiejar import CookieJar

            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
            reply = attempt_login(opener, login, password, 20.0)
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
        except ValueError as exc:
            self.note.set(str(exc))
            return
        live = self.live.get()
        if live and not (self.cookies.get().strip() or self.chrome_mode):
            self.note.set("Live rotation needs a cookies file or the Chrome button "
                          "(passwords are never stored for background use).")
            return
        self.switching = True
        self._cycle(login, pool, interval, live, 0)

    def stop(self):
        self.switching = False
        if self.rotate_job is not None:
            try:
                self.root.after_cancel(self.rotate_job)
            except Exception:
                pass
            self.rotate_job = None
        self.note.set("Auto-switch stopped. Nothing further will be sent.")

    def _cycle(self, login, pool, interval, live, index):
        if not self.switching:
            return
        try:
            pool = parse_pool(self.pool_box.get("1.0", "end")) or pool
            status, _ = next_rotation(pool, index)
        except ValueError as exc:
            self.note.set(str(exc))
            self.stop()
            return
        cookies_path = self.cookies.get().strip()  # main thread: no Tk calls in worker
        chrome_mode = self.chrome_mode

        def do():
            if not live:
                return "cycle #{0}/{1} (dry-run): {2}".format(index + 1, len(pool), status)
            import urllib.request

            try:
                jar = import_chrome_jar() if chrome_mode else load_cookie_jar(cookies_path)
            except (OSError, ValueError) as exc:
                return "cycle #{0}/{1} stopped: {2}".format(index + 1, len(pool), exc)
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
            ok, message = perform_update(opener, login, status, 20.0)
            return "cycle #{0}/{1}: {2}".format(index + 1, len(pool), message)

        self._run_bg(do, force=True)
        _, nxt = next_rotation(pool, index)
        self.rotate_job = self.root.after(max(1, interval) * 1000,
                                          self._cycle, login, pool, interval, live, nxt)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

