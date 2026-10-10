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
    "SHA256SUMS.txt": DIST / "SHA256SUMS.txt",
}


def app_version():
    src = (ROOT / "camfrog_auto.py").read_text(encoding="utf-8")
    match = re.search(r'^APP_VERSION = "([^"]+)"', src, re.M)
    if not match:
        raise SystemExit("APP_VERSION not found in camfrog_auto.py")
    return match.group(1)


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


def gh_ready():
    result = subprocess.run(["gh", "auth", "status"], capture_output=True)
    return result.returncode == 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--tag", default=None, help="override vX.Y.Z")
    args = parser.parse_args(argv)

    version = app_version()
    tag = args.tag or "v{0}".format(version)
    check_assets()
    assets = [str(path) for path in list(FEATURE_EXES.values()) + list(OTHER_ASSETS.values())]
    notes = release_notes(version)

    print("release : {0}".format(tag))
    print("title   : Camfrog feature apps {0}".format(version))
    print("notes   : {0} chars from CHANGELOG.md".format(len(notes)))
    for name in list(FEATURE_EXES) + list(OTHER_ASSETS):
        print("  asset : {0}".format(name))
    if args.dry_run:
        print("dry-run: nothing was created.")
        return 0
    if not gh_ready():
        print("gh is not authenticated; run `gh auth login` first.")
        return 2
    exists = subprocess.run(["gh", "release", "view", tag], capture_output=True)
    if exists.returncode == 0:
        print("release {0} already exists; uploading with --clobber.".format(tag))
        command = ["gh", "release", "upload", tag] + assets + ["--clobber"]
        return subprocess.run(command).returncode
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                     encoding="utf-8") as handle:
        handle.write(notes)
        notes_path = handle.name
    command = (["gh", "release", "create", tag] + assets
               + ["--title", "Camfrog feature apps {0}".format(version),
                  "--notes-file", notes_path])
    return subprocess.run(command).returncode


if __name__ == "__main__":
    sys.exit(main())
