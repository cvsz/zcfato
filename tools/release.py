"""Publish a GitHub release from the built dist/ artifacts.

Usage:
  python tools/release.py              # tag from camfrog_auto.APP_VERSION, upload assets
  python tools/release.py --dry-run    # print the plan, change nothing

Run full-build.bat first. The release is created with the authenticated `gh`
CLI (no token is stored in this repo); `gh auth status` must succeed.

Assets: every feature exe (stable names so the apps' self-update can find their
own file), the line-status-changer exe + config, the all-features zip, and
SHA256SUMS.txt (the self-update verifies downloads against it).
"""
import argparse
import hashlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

FEATURE_EXES = {
    "room-control.exe": DIST / "room-control" / "room-control.exe",
    "chat-im-private.exe": DIST / "chat-im-private" / "chat-im-private.exe",
    "status-random.exe": DIST / "status-random" / "status-random.exe",
    "status-marquee.exe": DIST / "status-marquee" / "status-marquee.exe",
    "im-autoreply.exe": DIST / "im-autoreply" / "im-autoreply.exe",
    "music-dj.exe": DIST / "music-dj" / "music-dj.exe",
    "web-status.exe": DIST / "web-status" / "web-status.exe",
}
OTHER_ASSETS = {
    "line-status-changer.exe": ROOT / "line" / "dist" / "line-status-changer.exe",
    "line_config.json": ROOT / "line" / "dist" / "line_config.json",
    "camfrog-features-windows.zip": ROOT / "camfrog-features-windows.zip",
}


def app_version():
    src = (ROOT / "camfrog_auto.py").read_text(encoding="utf-8")
    match = re.search(r'^APP_VERSION = "([^"]+)"', src, re.M)
    if not match:
        raise SystemExit("APP_VERSION not found in camfrog_auto.py")
    return match.group(1)


def flat_sums(assets):
    """SHA256SUMS.txt with flat basenames.

    The dist-relative sums (room-control/room-control.exe) do not match the
    flat asset names, and v2.19.0 clients only accept exact names, so the
    release carries this basename form: both old and new clients verify it.
    """
    import hashlib

    lines = []
    for name, path in assets:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append("{0}  {1}".format(digest, name))
    return "\n".join(lines) + "\n"


def release_notes(version):
    """The CHANGELOG section for this version, or a short default."""
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    marker = "## [{0}]".format(version)
    if marker in text:
        body = text.split(marker, 1)[1]
        body = body.split("\n## [", 1)[0].strip()
        if body:
            return body
    return "Camfrog feature apps v{0}.\n\nSee CHANGELOG.md for details.".format(version)


def check_assets():
    missing = [name for name, path in list(FEATURE_EXES.items()) + list(OTHER_ASSETS.items())
               if not path.is_file()]
    if missing:
        raise SystemExit("missing build outputs (run full-build.bat): {0}".format(
            ", ".join(sorted(missing))))


def verify_feature_hashes():
    """Verify the seven packaged EXEs against the build-produced SHA256SUMS."""
    manifest = DIST / "SHA256SUMS.txt"
    if not manifest.is_file():
        raise SystemExit("missing dist/SHA256SUMS.txt; run a full build first")
    expected = {str(path.relative_to(DIST)).replace("\\", "/"): path
                for path in FEATURE_EXES.values()}
    found = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or not re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            raise SystemExit("invalid SHA256SUMS.txt entry")
        name = parts[1].lstrip("*").replace("\\", "/")
        if name in found or name not in expected:
            raise SystemExit("unexpected or duplicate SHA256SUMS entry: " + name)
        found[name] = parts[0].lower()
    if set(found) != set(expected):
        raise SystemExit("SHA256SUMS.txt does not cover exactly seven feature EXEs")
    for name, path in expected.items():
        h = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                h.update(chunk)
        if h.hexdigest() != found[name]:
            raise SystemExit("artifact checksum mismatch: " + name)


def gh_ready():
    result = subprocess.run(["gh", "auth", "status"], capture_output=True)
    return result.returncode == 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--tag", default=None, help="override vX.Y.Z (must match APP_VERSION)")
    args = parser.parse_args(argv)

    version = app_version()
    tag = args.tag or "v{0}".format(version)
    if tag != "v{0}".format(version):
        raise SystemExit("release tag must match APP_VERSION to prevent mismatched releases")
    check_assets()
    verify_feature_hashes()
    pairs = list(FEATURE_EXES.items()) + list(OTHER_ASSETS.items())
    sums_path = DIST / "release-SHA256SUMS.txt"
    sums_path.write_text(flat_sums(pairs), encoding="utf-8", newline="\n")
    pairs.append(("SHA256SUMS.txt", sums_path))
    assets = [str(path) for _name, path in pairs]
    asset_names = [name for name, _path in pairs]
    notes = release_notes(version)

    print("release : {0}".format(tag))
    print("title   : Camfrog feature apps {0}".format(version))
    print("notes   : {0} chars from CHANGELOG.md".format(len(notes)))
    for name in asset_names:
        print("  asset : {0}".format(name))
    if args.dry_run:
        print("dry-run: nothing was created.")
        return 0
    if not gh_ready():
        print("gh is not authenticated; run `gh auth login` first.")
        return 2
    exists = subprocess.run(["gh", "release", "view", tag], capture_output=True)
    if exists.returncode == 0:
        print("release {0} already exists; refusing to overwrite published assets.".format(tag))
        return 3
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                     encoding="utf-8") as handle:
        handle.write(notes)
        notes_path = handle.name
    try:
        command = (["gh", "release", "create", tag] + assets
                   + ["--title", "Camfrog feature apps {0}".format(version),
                      "--notes-file", notes_path])
        return subprocess.run(command).returncode
    finally:
        Path(notes_path).unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
