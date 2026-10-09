"""Tests for the repository validator that do not need the real tree."""
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
