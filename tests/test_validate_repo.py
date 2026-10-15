"""Tests for the repository validator that do not need the real tree."""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import validate_repo


def _skeleton(root):
    for rel in validate_repo.REQUIRED_PATHS:
        p = root / rel
        if p.suffix:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("ok\n", encoding="utf-8")
        else:
            p.mkdir(parents=True, exist_ok=True)


def test_unreadable_markdown_is_an_error_not_a_crash(tmp_path, monkeypatch):
    _skeleton(tmp_path)
    bad = tmp_path / "docs" / "BAD.md"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_bytes(b"# t\xff\xfe\n")
    monkeypatch.setattr(validate_repo, "ROOT", tmp_path)
    errors = validate_repo.validate_markdown_links()
    assert any("BAD.md" in e and "cannot read" in e for e in errors)


def test_broken_link_still_reported(tmp_path, monkeypatch):
    _skeleton(tmp_path)
    (tmp_path / "README.md").write_text("[x](docs/missing.md)\n", encoding="utf-8")
    monkeypatch.setattr(validate_repo, "ROOT", tmp_path)
    assert any("missing.md" in e for e in validate_repo.validate_markdown_links())


def test_make_target_runs_only_template_checks_without_pytest_tree_discovery():
    makefile = validate_repo.ROOT / "Makefile"
    text = makefile.read_text(encoding="utf-8")
    target = text.split("validate-template:\n", 1)[1].split("\n\n", 1)[0]
    assert "python3 scripts/validate_repo.py" in target
    assert "-p 'test_bootstrap.py'" in target
    assert "unittest discover -s tests -v" not in target


def test_clean_prunes_generated_directories_before_recursive_scans():
    makefile = validate_repo.ROOT / "Makefile"
    text = makefile.read_text(encoding="utf-8")
    clean_target = text.split("clean:\n", 1)[1].split("\n\nci:", 1)[0]
    commands = [
        line.strip()
        for line in clean_target.splitlines()
        if line.startswith("\tfind .")
    ]

    assert len(commands) == 3
    assert "-name .pytest_cache -o" in commands[0]
    assert "-name .ruff_cache -o" in commands[0]
    assert (
        "\\) -prune -o -type d -name '__pycache__' -prune -exec rm -rf"
        in commands[0]
    )
    assert "-type d -name '.pytest_cache' -prune -exec rm -rf" in commands[1]
    assert "-type d -name '.ruff_cache' -prune -exec rm -rf" in commands[2]
    assert all("2>/dev/null" not in command and "|| true" not in command for command in commands)


def test_clean_returns_failure_when_a_filesystem_scan_fails(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_find = fake_bin / "find"
    fake_find.write_text(
        "#!/bin/sh\nprintf 'simulated-find-failure\\n' >&2\nexit 73\n",
        encoding="utf-8",
    )
    fake_find.chmod(0o755)
    if os.name == "nt":
        (fake_bin / "find.cmd").write_text(
            "@echo simulated-find-failure 1>&2\r\n@exit /b 73\r\n", encoding="utf-8"
        )
    environment = os.environ.copy()
    environment["PATH"] = os.pathsep.join((str(fake_bin), environment["PATH"]))

    result = subprocess.run(
        ["make", "-f", str(validate_repo.ROOT / "Makefile"), "clean"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "simulated-find-failure" in result.stdout + result.stderr


def test_build_and_dist_exclusions(tmp_path, monkeypatch):
    _skeleton(tmp_path)
    for folder in (
        "build",
        "dist",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "node_modules",
    ):
        d = tmp_path / folder
        d.mkdir(parents=True, exist_ok=True)
        (d / "bad.md").write_text("[broken](missing.md)\n", encoding="utf-8")
    monkeypatch.setattr(validate_repo, "ROOT", tmp_path)
    errors = validate_repo.validate_markdown_links()
    assert not any("bad.md" in e for e in errors)


def test_changelog_with_version_heading(tmp_path, monkeypatch):
    _skeleton(tmp_path)
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## [1.0.0] - 2026-01-01\n\nInitial\n", encoding="utf-8")
    monkeypatch.setattr(validate_repo, "ROOT", tmp_path)
    assert validate_repo.validate_changelog() == []


def test_changelog_missing_version_heading(tmp_path, monkeypatch):
    _skeleton(tmp_path)
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\nNo version heading here\n", encoding="utf-8")
    monkeypatch.setattr(validate_repo, "ROOT", tmp_path)
    errors = validate_repo.validate_changelog()
    assert any("CHANGELOG.md" in e and "version heading" in e for e in errors)


def test_json_flag_output_format(tmp_path, monkeypatch, capsys):
    _skeleton(tmp_path)
    (tmp_path / "CHANGELOG.md").write_text("## [0.1.0]\n", encoding="utf-8")
    monkeypatch.setattr(validate_repo, "ROOT", tmp_path)
    ret = validate_repo.main(["--json"])
    assert ret == 0
    out, err = capsys.readouterr()
    assert err == ""
    assert json.loads(out) == []

    (tmp_path / "CHANGELOG.md").write_text("missing heading\n", encoding="utf-8")
    ret = validate_repo.main(["--json"])
    assert ret == 1
    out, err = capsys.readouterr()
    assert err == ""
    errors = json.loads(out)
    assert isinstance(errors, list)
    assert any("CHANGELOG.md" in e for e in errors)


def test_fix_flag_stub(capsys):
    ret = validate_repo.main(["--fix"])
    assert ret == 2
    out, err = capsys.readouterr()
    assert out == ""
    assert "--fix is not implemented" in err


def test_markdown_scan_permission_error_fails_closed(tmp_path, monkeypatch):
    _skeleton(tmp_path)

    def fail_walk(_root, onerror):
        onerror(PermissionError("simulated access denial"))
        return iter(())

    monkeypatch.setattr(validate_repo, "ROOT", tmp_path)
    monkeypatch.setattr(validate_repo.os, "walk", fail_walk)
    errors = validate_repo.validate_markdown_links()
    assert errors == ["repository scan failed: simulated access denial"]


def test_ci_workflow_required(tmp_path, monkeypatch):
    _skeleton(tmp_path)
    ci_file = tmp_path / ".github" / "workflows" / "ci.yml"
    if ci_file.exists():
        ci_file.unlink()
    monkeypatch.setattr(validate_repo, "ROOT", tmp_path)
    errors = validate_repo.validate_required_paths()
    assert any(".github/workflows/ci.yml" in e for e in errors)


def test_root_under_excluded_named_directory(tmp_path, monkeypatch):
    nested_root = tmp_path / "build" / "project"
    nested_root.mkdir(parents=True, exist_ok=True)
    _skeleton(nested_root)
    (nested_root / "README.md").write_text("[broken](missing.md)\n", encoding="utf-8")
    monkeypatch.setattr(validate_repo, "ROOT", nested_root)
    errors = validate_repo.validate_markdown_links()
    assert any("missing.md" in e for e in errors)


