"""Offline tests for the browser-login harvester (fake CDP server)."""
import base64
import hashlib
import json
import socket
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import browser_login as bl  # noqa: E402

_COOKIES = [
    {"name": "PHPSESSID", "value": "abc123", "domain": ".camfrog.com"},
    {"name": "lang", "value": "th", "domain": "profiles.camfrog.com"},
    {"name": "_ga", "value": "x", "domain": ".google.com"},
]


def _frame(payload):
    n = len(payload)
    head = bytearray([0x81])
    if n < 126:
        head.append(n)
    elif n < 1 << 16:
        head.append(126)
        head += n.to_bytes(2, "big")
    else:
        head.append(127)
        head += n.to_bytes(8, "big")
    return bytes(head) + payload


@pytest.fixture
def fake_cdp():
    """A CDP-shaped WebSocket server that answers Network.getAllCookies."""
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    received = []

    def serve():
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        try:
            req = b""
            while b"\r\n\r\n" not in req:
                block = conn.recv(4096)
                if not block:
                    return
                req += block
            key = [ln.split(b": ", 1)[1] for ln in req.split(b"\r\n")
                   if b"Sec-WebSocket-Key" in ln][0]
            accept = base64.b64encode(hashlib.sha1(
                key + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest())
            conn.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
                         b"Connection: Upgrade\r\nSec-WebSocket-Accept: " + accept
                         + b"\r\n\r\n")
            raw = conn.recv(65536)
            length = raw[1] & 0x7F
            mask = raw[2:6]
            received.append(json.loads(
                bytes(b ^ mask[i % 4] for i, b in enumerate(raw[6:6 + length]))))
            conn.sendall(_frame(json.dumps(
                {"id": 1, "result": {"cookies": _COOKIES}}).encode()))
            conn.close()
        except OSError:
            pass
        finally:
            srv.close()

    threading.Thread(target=serve, daemon=True).start()
    return SimpleNamespace(port=srv.getsockname()[1], received=received)


def _connect(fake_cdp):
    return bl._WebSocket("ws://127.0.0.1:{0}/devtools/page/1".format(fake_cdp.port))


def test_websocket_sends_cdp_request_and_parses_reply(fake_cdp):
    ws = _connect(fake_cdp)
    message = bl._cdp_call(ws, "Network.getAllCookies")
    assert fake_cdp.received == [{"id": 1, "method": "Network.getAllCookies"}]
    assert any(c["name"] == "PHPSESSID"
               for c in message.get("result", {}).get("cookies", []))
    ws.close()


def test_cookies_are_filtered_to_camfrog(fake_cdp):
    ws = _connect(fake_cdp)
    message = bl._cdp_call(ws, "Network.getAllCookies")
    text = bl._cookies_to_string(message.get("result", {}).get("cookies", []))
    assert "PHPSESSID=abc123" in text
    assert "lang=th" in text
    assert "_ga" not in text, "foreign-domain cookies must be dropped"
    ws.close()


def test_cookies_without_camfrog_raises():
    with pytest.raises(ValueError):
        bl._cookies_to_string([{"name": "_ga", "value": "x", "domain": ".google.com"}])


def test_find_browser_returns_none_off_windows():
    if sys.platform == "win32":
        pytest.skip("browser present on Windows")
    assert bl.find_browser() is None


def test_websocket_rejects_non_ws_urls():
    with pytest.raises(ValueError):
        bl._WebSocket("http://example.test")
