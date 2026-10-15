from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_local_updater_accepts_the_current_https_and_ssh_remote() -> None:
    text = (ROOT / "update-local.ps1").read_text(encoding="utf-8")
    match = re.search(r"\$remote -notmatch '([^']+)'", text)
    assert match is not None
    remote_pattern = re.compile(match.group(1))

    for remote in (
        "https://github.com/cvsz/zchat.git",
        "git@github.com:cvsz/zchat.git",
        "https://github.com/cvsz/zchat",
    ):
        assert remote_pattern.search(remote)
    assert not remote_pattern.search("https://github.com/cvsz/zcfato.git")


def test_application_update_defaults_use_the_current_repository() -> None:
    source_files = (
        "camfrog_auto.py",
        "camfrog_music_gui.py",
        "chat_im_private_gui.py",
        "im_autoreply_gui.py",
        "room_control_gui.py",
        "status_changer_gui.py",
        "status_marquee_gui.py",
        "status_random_gui.py",
        "web_status_gui.py",
    )
    for source_file in source_files:
        text = (ROOT / source_file).read_text(encoding="utf-8")
        assert 'CAMFROG_UPDATE_REPO", "cvsz/zchat"' in text, source_file
        assert 'CAMFROG_UPDATE_REPO", "cvsz/zcfato"' not in text, source_file


def test_client_reconstruction_directory_is_not_ignored() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    ignored_paths = [line.strip() for line in gitignore.splitlines() if line.strip()]
    assert "zchat-client-re/" not in ignored_paths


def test_python_dependency_manifests_are_covered_by_dependabot_and_ci_audit() -> None:
    dependabot = (ROOT / ".github/dependabot.yml").read_text(encoding="utf-8")
    for directory in ("/", "/control-server", "/line"):
        assert f"directory: {directory}" in dependabot
    assert "package-ecosystem: pip" in dependabot

    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "pip_audit -r line/requirements-build.txt" in workflow
