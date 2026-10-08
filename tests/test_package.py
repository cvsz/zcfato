import hashlib
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import package  # noqa: E402


def test_sha256_matches_hashlib(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"x" * 3_000_000)
    assert package.sha256_file(f) == hashlib.sha256(b"x" * 3_000_000).hexdigest()


def test_sums_format_is_sha256sum_compatible(tmp_path):
    (tmp_path / "app.exe").write_bytes(b"abc")
    out = package.write_sums(tmp_path, "app")
    line = out.read_bytes()
    assert line == (hashlib.sha256(b"abc").hexdigest() + "  app.exe\n").encode()


def test_sums_missing_exe(tmp_path):
    try:
        package.write_sums(tmp_path, "nope")
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError")


def test_zip_contains_files_with_relative_paths(tmp_path):
    d = tmp_path / "dist"
    (d / "sub").mkdir(parents=True)
    (d / "a.exe").write_bytes(b"1")
    (d / "sub" / "b.txt").write_text("2")
    z = package.make_zip(d, tmp_path / "out.zip")
    with zipfile.ZipFile(z) as zf:
        assert sorted(zf.namelist()) == ["a.exe", "sub/b.txt"]
        assert zf.testzip() is None


def test_zip_overwrites_existing(tmp_path):
    d = tmp_path / "dist"
    d.mkdir()
    (d / "a.txt").write_text("1")
    z = tmp_path / "o.zip"
    z.write_text("junk")
    package.make_zip(d, z)
    assert zipfile.is_zipfile(z)


def test_icon_is_valid_multisize():
    import struct
    d = (Path(__file__).resolve().parent.parent / "app.ico").read_bytes()
    reserved, kind, n = struct.unpack("<HHH", d[:6])
    assert (reserved, kind) == (0, 1) and n >= 4


# ---- audit regressions ----
import json  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import camfrog_auto as ca  # noqa: E402


def test_load_cfg_accepts_utf8_bom(tmp_path):
    p = tmp_path / "config.json"
    p.write_bytes(b"\xef\xbb\xbf" + json.dumps({"dry_run": True}).encode())
    assert ca.load_cfg(p)["dry_run"] is True


def test_validate_never_raises_on_bad_types():
    cfg = ca.deep_merge(ca.DEFAULTS, {"status": {"messages": ["x"], "interval_seconds": "300"},
                                      "autoreply": {"delay_range_seconds": [1]}})
    errs, _ = ca.validate(cfg)
    assert errs  # reported as errors, no exception


def test_validate_bad_rule_shape_reported():
    cfg = ca.deep_merge(ca.DEFAULTS, {"status": {"messages": ["x"]},
                                      "autoreply": {"rules": ["not-a-dict"]}})
    assert ca.validate(cfg)[0]


def test_child_env_resets_pyinstaller_when_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("_MEIPASS2", "C:/tmp/_MEI123")
    env = ca.child_env()
    assert env["PYINSTALLER_RESET_ENVIRONMENT"] == "1" and "_MEIPASS2" not in env


def test_child_env_untouched_when_not_frozen(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert "PYINSTALLER_RESET_ENVIRONMENT" not in ca.child_env()


def test_doctor_bat_runs_once_and_matches_build_selection():
    root = Path(__file__).resolve().parent.parent
    doc = (root / "doctor.bat").read_text(encoding="utf-8")
    bld = (root / "build.bat").read_text(encoding="utf-8")
    assert "||" not in doc  # the old `py ... || python ...` ran doctor twice on failure
    cand = "for %%V in (3.12 3.13 3.11 3.14) do ("
    assert cand in doc and cand in bld


def test_missing_window_is_a_clean_error_not_a_traceback(tmp_path, monkeypatch):
    import shutil
    root = Path(__file__).resolve().parent.parent
    cfgp = tmp_path / "config.json"
    shutil.copy(root / "config.json", cfgp)
    monkeypatch.setattr(ca, "BASE", tmp_path)

    def boom(cfg):
        raise RuntimeError("Camfrog window not found (check window_title_regex)")
    monkeypatch.setattr(ca, "get_window", boom)
    assert ca.main(["--config", str(cfgp), "discover"]) == 1
    import logging
    logging.shutdown()
    assert "Traceback" not in (tmp_path / "camfrog_auto.log").read_text(encoding="utf-8")


def test_windows_command_registered():
    assert ca.build_parser().parse_args(["windows"]).cmd == "windows"


class _Info:
    def __init__(self, aid="", name=""):
        self.automation_id, self.name = aid, name


class _Ctl:
    def __init__(self, aid="", name=""):
        self.element_info = _Info(aid, name)


class _Win:
    def __init__(self, items):
        self.items, self.kw = items, None

    def descendants(self, **kw):
        self.kw = kw
        return self.items


def test_find_never_passes_auto_id_or_title_re_to_pywinauto():
    w = _Win([_Ctl("1001"), _Ctl("1002"), _Ctl("1002")])
    c = ca.find(w, {"control_type": "Edit", "auto_id": "1002", "index": 1})
    assert c is w.items[2]
    assert set(w.kw) == {"control_type"}


def test_find_title_re_and_missing_control():
    w = _Win([_Ctl("a", "Hello"), _Ctl("b", "World")])
    assert ca.find(w, {"title_re": "Wor.*"}) is w.items[1]
    try:
        ca.find(w, {"auto_id": "zzz"})
    except LookupError:
        return
    raise AssertionError("expected LookupError")


def test_find_without_filters_keeps_old_behaviour():
    w = _Win([_Ctl(), _Ctl()])
    assert ca.find(w, {"index": 1}) is w.items[1]


def test_sums_include_gui_exe(tmp_path):
    (tmp_path / "app.exe").write_bytes(b"a")
    (tmp_path / "app-gui.exe").write_bytes(b"b")
    lines = package.write_sums(tmp_path, "app").read_text(encoding="utf-8").splitlines()
    assert [ln.split("  ")[1] for ln in lines] == ["app.exe", "app-gui.exe"]


def test_bat_files_are_crlf():
    root = Path(__file__).resolve().parent.parent
    for p in list(root.glob("*.bat")) + list((root / "extras").glob("*.bat")):
        b = p.read_bytes()
        assert b.count(b"\n") == b.count(b"\r\n"), f"{p.name} has bare LF (cmd.exe breaks)"
