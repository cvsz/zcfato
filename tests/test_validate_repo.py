"""Tests for the repository validator that do not need the real tree."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import validate_repo  # noqa: E402


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


def test_build_and_dist_exclusions(tmp_path, monkeypatch):
    _skeleton(tmp_path)
    for folder in ("build", "dist", ".ruff_cache", ".pytest_cache"):
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
    assert ret == 0
    out, _ = capsys.readouterr()
    assert "Auto-fix not yet implemented" in out


def test_ci_workflow_required(tmp_path, monkeypatch):
    _skeleton(tmp_path)
    ci_file = tmp_path / ".github" / "workflows" / "ci.yml"
    if ci_file.exists():
        ci_file.unlink()
    monkeypatch.setattr(validate_repo, "ROOT", tmp_path)
    errors = validate_repo.validate_required_paths()
    assert any(".github/workflows/ci.yml" in e for e in errors)

