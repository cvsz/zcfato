"""Log in through the real browser and harvest the session cookie (stdlib only).

Camfrog's login page answers `captcha` to scripted POSTs and stores its
session cookie as HttpOnly (so copying it out of devtools is the only manual
way). This module drives a private Chrome/Edge profile over the DevTools
Protocol: the user logs in as usual - CAPTCHA included - and the resulting
cookies (including HttpOnly) are read back.

Flow: spawn <browser> --user-data-dir=<temp> --remote-debugging-port=PORT
with the login URL in a new window, poll /json/list for the page target, open
a DevTools WebSocket, wait until the camfrog session cookie appears, then read
all cookies and return them as `name=value; ...` for cookie_from_paste().

No network beyond localhost and camfrog.com. No third-party packages.
"""
import base64
import json
import random
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

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
