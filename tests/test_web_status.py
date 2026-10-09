"""Tk-free tests for the prototype web status updater (no network)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import web_status as ws  # noqa: E402


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


class FakeOpener:
    def __init__(self, body):
        self.body = body
        self.calls = []

    def open(self, request, timeout=None):
        self.calls.append(request)
        return FakeResponse(self.body)


def _patch_opener(monkeypatch, body):
    fake = FakeOpener(body)
    monkeypatch.setattr(ws.urllib.request, "build_opener", lambda *args: fake)
    return fake


def test_dry_run_touches_nothing(monkeypatch, capsys):
    monkeypatch.setattr(ws.urllib.request, "build_opener", lambda *a: (_ for _ in ()).throw(
        AssertionError("no network in dry-run")))
    monkeypatch.setattr(ws.getpass, "getpass", lambda *a: (_ for _ in ()).throw(
        AssertionError("no password prompt in dry-run")))
    assert ws.main(["--login", "Seaza", "--status", "hello"]) == 0
    out = capsys.readouterr().out
    assert "profiles.camfrog.com/Seaza" in out


def test_how_to_capture_exit_ok(capsys):
    assert ws.main(["--login", "Seaza", "--status", "x", "--how-to-capture"]) == 0
    out = capsys.readouterr().out
    assert "cookies.txt" in out


def test_empty_status_refused(capsys):
    assert ws.main(["--login", "Seaza", "--status", "   "]) == 2


def test_live_captcha_blocks_without_bypass(monkeypatch, capsys):
    monkeypatch.setattr(ws.getpass, "getpass", lambda *a: "s3cret-pw")
    _patch_opener(monkeypatch, b"captcha")
    assert ws.main(["--login", "Seaza", "--status", "hi", "--live"]) == 3
    out = capsys.readouterr().out
    assert "CAPTCHA" in out
    assert "s3cret-pw" not in out


def test_live_wrong_password_reports_auth_failure(monkeypatch, capsys):
    monkeypatch.setattr(ws.getpass, "getpass", lambda *a: "wrong")
    _patch_opener(monkeypatch, b"password")
    assert ws.main(["--login", "Seaza", "--status", "hi", "--live"]) == 2
    assert "incorrect" in capsys.readouterr().out


def test_live_login_success_still_gated(monkeypatch, capsys):
    monkeypatch.setattr(ws.getpass, "getpass", lambda *a: "pw")
    _patch_opener(monkeypatch, b"https://profiles.camfrog.com/en/")
    assert ws.main(["--login", "Seaza", "--status", "hi", "--live"]) == 3
    assert "no verified status-update endpoint" in capsys.readouterr().out


def test_live_prompt_cancel_sends_nothing(monkeypatch, capsys):
    def cancel(*args):
        raise EOFError

    monkeypatch.setattr(ws.getpass, "getpass", cancel)
    assert ws.main(["--login", "Seaza", "--status", "hi", "--live"]) == 2
    assert "nothing was sent" in capsys.readouterr().out


def test_live_network_failure_returns_int_code(monkeypatch, capsys):
    import urllib.error

    monkeypatch.setattr(ws.getpass, "getpass", lambda *a: "pw")

    class DeadOpener:
        def open(self, request, timeout=None):
            raise urllib.error.URLError("no route to host")

    monkeypatch.setattr(ws.urllib.request, "build_opener", lambda *a: DeadOpener())
    code = ws.main(["--login", "Seaza", "--status", "hi", "--live"])
    assert code == 2 and isinstance(code, int)
    out = capsys.readouterr().out
    assert "web login request failed" in out
    assert "pw" not in out


def _cookie_file(tmp_path, value="s3cret-value"):
    path = tmp_path / "camfrog-cookies.txt"
    path.write_text("# Netscape HTTP Cookie File\n"
                    ".camfrog.com\tTRUE\t/\tTRUE\t0\tsess\t{0}\n".format(value),
                    encoding="utf-8")
    return str(path)


def test_probe_missing_cookie_file(capsys):
    assert ws.main(["--login", "Seaza", "--status", "hi",
                    "--cookies-file", "/nonexistent/x.txt", "--probe"]) == 2


def test_probe_bad_cookie_file(tmp_path, capsys):
    bad = tmp_path / "bad.txt"
    bad.write_text("not a cookie file\n", encoding="utf-8")
    assert ws.main(["--login", "Seaza", "--status", "hi",
                    "--cookies-file", str(bad), "--probe"]) == 2


def test_probe_detects_logged_out_session(tmp_path, monkeypatch, capsys):
    fake = _patch_opener(monkeypatch, b"<title>Camfrog - Login Page</title>Sign On")
    assert ws.main(["--login", "Seaza", "--status", "hi",
                    "--cookies-file", _cookie_file(tmp_path), "--probe"]) == 0
    assert fake.calls, "probe must hit the network"
    out = capsys.readouterr().out
    assert "NOT signed in" in out
    assert "s3cret-value" not in out
    assert "no status was changed" in out


def test_probe_never_claims_verified_blindly(tmp_path, monkeypatch, capsys):
    _patch_opener(monkeypatch, b"<title>Camfrog - Profile Page</title>hello")
    assert ws.main(["--login", "Seaza", "--status", "hi",
                    "--cookies-file", _cookie_file(tmp_path), "--probe"]) == 0
    assert "UNCONFIRMED" in capsys.readouterr().out


def test_probe_requires_cookies_file():
    with pytest.raises(SystemExit) as exc:
        ws.main(["--login", "Seaza", "--status", "hi", "--probe"])
    assert exc.value.code == 2

def test_parse_pool_drops_blanks():
    assert ws.parse_pool("  hi\n\n  hello world  \n") == ["hi", "hello world"]
    assert ws.parse_pool("   \n ") == []


def test_next_rotation_wraps_around():
    pool = ["a", "b"]
    assert ws.next_rotation(pool, 0) == ("a", 1)
    assert ws.next_rotation(pool, 1) == ("b", 0)
    assert ws.next_rotation(pool, 5) == ("b", 0)


def test_next_rotation_empty_pool_refused():
    with pytest.raises(ValueError):
        ws.next_rotation([], 0)


def test_parse_rotate_interval_clamps_and_rejects():
    assert ws.parse_rotate_interval("300") == 300
    assert ws.parse_rotate_interval("5") == ws.ROTATE_INTERVAL_MIN
    assert ws.parse_rotate_interval("999999") == ws.ROTATE_INTERVAL_MAX
    for bad in ("", "abc", "nan", "inf", None):
        with pytest.raises(ValueError):
            ws.parse_rotate_interval(bad)


def test_perform_update_refused_until_endpoint_verified():
    ok, message = ws.perform_update(None, "Seaza", "hi", 1.0)
    assert ok is False
    assert "no verified status-update endpoint" in message


def _chrome_profile(tmp_path, name="Default", rows=((".camfrog.com", "sess", "plain", b""),)):
    import sqlite3

    profile = tmp_path / "chrome" / name
    profile.mkdir(parents=True)
    db = profile / "Cookies"
    connection = sqlite3.connect(db)
    connection.execute("CREATE TABLE cookies(host_key TEXT, name TEXT, value TEXT, "
                       "encrypted_value BLOB, path TEXT, is_secure INTEGER, expires_utc INTEGER)")
    for host, cookie, value, encrypted in rows:
        connection.execute("INSERT INTO cookies VALUES(?,?,?,?,?,?,?)",
                           (host, cookie, value, encrypted, "/", 0, 0))
    connection.commit()
    connection.close()
    return tmp_path / "chrome"


def test_find_chrome_profiles_only_standard_dirs(tmp_path):
    base = _chrome_profile(tmp_path)
    (base / "Profile 1").mkdir()
    import sqlite3
    connection = sqlite3.connect(base / "Profile 1" / "Cookies")
    connection.execute("CREATE TABLE cookies(a)")
    connection.commit()
    connection.close()
    (base / "Other").mkdir()
    found = ws.find_chrome_profiles(str(base))
    assert [name for name, _db in found] == ["Default", "Profile 1"]
    assert ws.find_chrome_profiles(str(tmp_path / "nope")) == []


def test_import_plain_values_and_redacts_summary(tmp_path):
    jar = ws.import_chrome_jar(str(_chrome_profile(tmp_path)))
    assert len(jar) == 1
    summary = ws.cookie_summary(jar)
    assert ".camfrog.com" in summary
    assert "plain" not in summary


def test_import_skips_foreign_and_evil_domains(tmp_path):
    base = _chrome_profile(tmp_path, rows=(
        ("other.com", "a", "x", b""),
        ("evilcamfrog.com", "b", "y", b""),
        ("profiles.camfrog.com", "c", "z", b"")))
    jar = ws.import_chrome_jar(str(base))
    assert sorted(c.name for c in jar) == ["c"]


def test_import_decrypts_blobs_without_values(tmp_path, monkeypatch):
    seen = []

    def fake_decrypt(blob, user_data=""):
        seen.append((blob, user_data))
        return "decrypted!"

    monkeypatch.setattr(ws, "decrypt_chrome_value", fake_decrypt)
    base = _chrome_profile(tmp_path, rows=((".camfrog.com", "s", "", b"\x01\x02"),))
    jar = ws.import_chrome_jar(str(base))
    assert [c.value for c in jar] == ["decrypted!"]
    assert seen and seen[0][0] == b"\x01\x02"


def test_import_reports_bad_decrypt_without_values(tmp_path, monkeypatch, capsys):
    def boom(blob, user_data=""):
        raise ValueError("DPAPI could not decrypt this cookie")

    monkeypatch.setattr(ws, "decrypt_chrome_value", boom)
    base = _chrome_profile(tmp_path, rows=((".camfrog.com", "s", "", b"\x01"),))
    with pytest.raises(ValueError) as exc:
        ws.import_chrome_jar(str(base))
    assert "no usable camfrog.com cookies" in str(exc.value)
    assert "\x01" not in str(exc.value)


def test_import_missing_store_is_a_clean_error(tmp_path):
    with pytest.raises(ValueError) as exc:
        ws.import_chrome_jar(str(tmp_path / "nothing"))
    assert "no Chrome cookie store" in str(exc.value)


def test_dpapi_needs_windows():
    with pytest.raises(ValueError) as exc:
        ws.dpapi_unprotect(b"\x01\x02")
    assert "Windows" in str(exc.value)


def test_aes_cookie_without_library_is_a_clean_error():
    import importlib.util

    if importlib.util.find_spec("cryptography") is not None:
        pytest.skip("cryptography installed; error path not applicable")
    with pytest.raises(ValueError) as exc:
        ws.decrypt_chrome_value(b"v10" + b"\x00" * 30, "")
    assert "cryptography" in str(exc.value)


def test_probe_chrome_flag_conflicts_with_file():
    with pytest.raises(SystemExit) as exc:
        ws.main(["--login", "Seaza", "--status", "hi", "--probe",
                 "--chrome", "--cookies-file", "x.txt"])
    assert exc.value.code == 2


def test_probe_chrome_missing_store(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(ws.CHROME_ENV_OVERRIDE, str(tmp_path / "nothing"))
    assert ws.main(["--login", "Seaza", "--status", "hi", "--probe", "--chrome"]) == 2
    assert "no Chrome cookie store" in capsys.readouterr().out


def test_probe_chrome_reports_verdict(tmp_path, monkeypatch, capsys):
    base = _chrome_profile(tmp_path)
    monkeypatch.setenv(ws.CHROME_ENV_OVERRIDE, str(base))
    fake = FakeOpener(b"<title>Camfrog - Login Page</title>Sign On")
    monkeypatch.setattr(ws.urllib.request, "build_opener", lambda *a: fake)
    assert ws.main(["--login", "Seaza", "--status", "hi", "--probe", "--chrome"]) == 0
    out = capsys.readouterr().out
    assert "from Chrome" in out and "NOT signed in" in out
    assert "plain" not in out


def test_data_blob_pins_backing_buffer():
    blob = ws._data_blob(b"abc")
    assert blob.cbData == 3
    assert blob._backing.value == b"abc"
    import ctypes
    assert ctypes.string_at(blob.pbData, blob.cbData) == b"abc"


@pytest.mark.parametrize("content", [
    "{not json",
    "[]",
    '{"os_crypt": "nope"}',
    '{"os_crypt": {}}',
    '{"os_crypt": {"encrypted_key": "!!!not-base64!!!"}}',
])
def test_chrome_aes_key_malformed_local_state(tmp_path, content):
    local_state = tmp_path / "Local State"
    local_state.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        ws.chrome_aes_key(str(tmp_path))
    assert "Local State" in str(exc.value)


def test_chrome_aes_key_missing_file(tmp_path):
    with pytest.raises(ValueError):
        ws.chrome_aes_key(str(tmp_path / "nothing"))
