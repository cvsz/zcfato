"""Release-integrity regression tests."""
import hashlib
import json

import pytest
from tools import release
from line.config_store import default_config


def test_public_line_config_is_generic_default_not_local_settings(tmp_path):
    local_config = tmp_path / "line_config.json"
    local_config.write_text('{"last_text":"private local status"}', encoding="utf-8")
    public_config = tmp_path / "release" / "line_config.json"

    release.write_public_line_config(public_config)

    data = json.loads(public_config.read_text(encoding="utf-8"))
    assert data == default_config()
    assert "private local status" not in public_config.read_text(encoding="utf-8")


def test_verify_feature_hashes_accepts_all_expected_files(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    files = {}
    lines = []
    for name in ("room-control", "chat-im-private", "status-random",
                 "status-marquee", "im-autoreply", "music-dj", "web-status"):
        path = dist / name / (name + ".exe")
        path.parent.mkdir()
        path.write_bytes(("test-" + name).encode())
        files[name + ".exe"] = path
        lines.append(hashlib.sha256(path.read_bytes()).hexdigest()
                     + "  " + name + "/" + name + ".exe")
    (dist / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n")
    monkeypatch.setattr(release, "DIST", dist)
    monkeypatch.setattr(release, "FEATURE_EXES", files)
    release.verify_feature_hashes()
    files["music-dj.exe"].write_bytes(b"tampered")
    with pytest.raises(SystemExit, match="checksum mismatch"):
        release.verify_feature_hashes()


def test_verify_feature_hashes_rejects_missing_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(release, "DIST", tmp_path)
    with pytest.raises(SystemExit, match="missing dist/SHA256SUMS"):
        release.verify_feature_hashes()


def test_release_rejects_existing_tag_without_upload(monkeypatch, tmp_path):
    monkeypatch.setattr(release, "DIST", tmp_path)
    monkeypatch.setattr(release, "app_version", lambda: "2.99.0")
    monkeypatch.setattr(release, "check_assets", lambda: None)
    monkeypatch.setattr(release, "verify_feature_hashes", lambda: None)
    monkeypatch.setattr(release, "flat_sums", lambda pairs: "abc\n")
    monkeypatch.setattr(release, "release_notes", lambda ver: "notes")
    monkeypatch.setattr(release, "release_target", lambda: "a" * 40)
    monkeypatch.setattr(release, "gh_ready", lambda: True)
    class Completed:
        returncode = 0
    calls = []
    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return Completed()
    monkeypatch.setattr(release.subprocess, "run", fake_run)
    assert release.main([]) == 3
    assert calls == [["gh", "release", "view", "v2.99.0"]]


def test_release_pins_tag_to_verified_commit(monkeypatch, tmp_path):
    target = "a" * 40
    monkeypatch.setattr(release, "DIST", tmp_path)
    monkeypatch.setattr(release, "app_version", lambda: "2.19.2")
    monkeypatch.setattr(release, "check_assets", lambda: None)
    monkeypatch.setattr(release, "verify_feature_hashes", lambda: None)
    monkeypatch.setattr(release, "FEATURE_EXES", {})
    monkeypatch.setattr(release, "OTHER_ASSETS", {})
    monkeypatch.setattr(release, "flat_sums", lambda pairs: "abc\n")
    monkeypatch.setattr(release, "release_notes", lambda ver: "notes")
    monkeypatch.setattr(release, "release_target", lambda: target)
    monkeypatch.setattr(release, "gh_ready", lambda: True)

    class Completed:
        def __init__(self, returncode):
            self.returncode = returncode

    calls = []
    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return Completed(1 if cmd[:3] == ["gh", "release", "view"] else 0)
    monkeypatch.setattr(release.subprocess, "run", fake_run)

    assert release.main([]) == 0
    create = next(command for command in calls if command[:3] == ["gh", "release", "create"])
    target_index = create.index("--target")
    assert create[target_index + 1] == target


def test_release_rejects_mismatched_tag(monkeypatch):
    monkeypatch.setattr(release, "app_version", lambda: "2.99.0")
    with pytest.raises(SystemExit, match="must match APP_VERSION"):
        release.main(["--tag", "v0.0.1"])
