"""Post-build packaging (stdlib only, no PowerShell required).

  python tools/package.py NAME            hashes dist/ executables and writes NAME-windows.zip
  python tools/package.py NAME --hash-only
  python tools/package.py NAME --executables-only  excludes local app data from the zip

Package names must be simple path-safe names. Archives are written atomically,
so a failed archive write preserves any existing output.

Replaces PowerShell's Get-FileHash / Compress-Archive, which are missing on
Windows 7 / PowerShell < 4-5 or when PSModulePath is broken.
"""

import argparse
import hashlib
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
PACKAGE_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
FEATURE_EXECUTABLES = (
    "chat-im-private/chat-im-private.exe",
    "im-autoreply/im-autoreply.exe",
    "music-dj/music-dj.exe",
    "room-control/room-control.exe",
    "status-marquee/status-marquee.exe",
    "status-random/status-random.exe",
    "status-changer/status-changer.exe",
    "web-status/web-status.exe",
)


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_package_name(name: str) -> str:
    if not isinstance(name, str) or PACKAGE_NAME_RE.fullmatch(name) is None:
        raise ValueError(
            "package name must be 1-64 ASCII letters, numbers, dots, underscores, "
            "or hyphens and start with a letter or number"
        )
    return name


def write_sums(dist: Path | str, name: str) -> Path:
    dist = Path(dist)
    name = validate_package_name(name)
    if name == "camfrog-features":
        expected = set(FEATURE_EXECUTABLES)
        actual = {
            p.relative_to(dist).as_posix()
            for p in dist.rglob("*.exe")
            if p.is_file() and not p.is_symlink()
        }
        if actual != expected:
            missing = sorted(expected - actual)
            unexpected = sorted(actual - expected)
            raise ValueError(
                f"Unexpected Camfrog executable set; missing={missing}, extra={unexpected}"
            )
        exes = [dist / relative for relative in FEATURE_EXECUTABLES]
    else:
        primary = dist / f"{name}.exe"
        candidates = sorted(p for p in dist.rglob("*.exe") if p.is_file())
        symlinks = [p for p in candidates if p.is_symlink()]
        if symlinks:
            raise ValueError(
                f"Refusing to checksum symbolic link: {symlinks[0].relative_to(dist)}"
            )
        if primary.is_file():
            exes = [primary] + sorted(p for p in dist.glob("*.exe") if p != primary)
        else:
            exes = candidates
    if not exes:
        raise FileNotFoundError(f"No executable files found in {dist}")
    out = Path(dist) / "SHA256SUMS.txt"
    content = "".join(
        f"{sha256_file(p)}  {p.relative_to(dist).as_posix()}\n" for p in exes
    )
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            prefix=".SHA256SUMS.",
            suffix=".tmp",
            dir=out.parent,
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(content)
        os.replace(temporary_path, out)
    except BaseException:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise
    return out


def make_zip(
    dist: Path | str, zip_path: Path | str, executables_only: bool = False
) -> Path:
    dist, zip_path = Path(dist), Path(zip_path)
    dist_root = dist.resolve()
    archive_path = zip_path.resolve()
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{zip_path.name}.",
            suffix=".tmp",
            dir=zip_path.parent,
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
        with zipfile.ZipFile(temporary_path, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(dist.rglob("*")):
                include = p.suffix.lower() == ".exe" or p.name in (
                    "SHA256SUMS.txt",
                    "app.ico",
                )
                if not p.is_file() or (executables_only and not include):
                    continue
                if p.is_symlink():
                    raise ValueError(
                        f"Refusing to package symbolic link: {p.relative_to(dist)}"
                    )
                resolved = p.resolve()
                try:
                    resolved.relative_to(dist_root)
                except ValueError as exc:
                    raise ValueError(
                        f"Package input escapes dist/: {p.relative_to(dist)}"
                    ) from exc
                if resolved == archive_path:
                    continue
                z.write(p, p.relative_to(dist).as_posix())
        os.replace(temporary_path, zip_path)
    except BaseException:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise
    return zip_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "name", nargs="?", help="package name used for the checksum and zip filenames"
    )
    parser.add_argument(
        "--hash-only",
        action="store_true",
        help="write checksums without creating a zip",
    )
    parser.add_argument(
        "--executables-only",
        action="store_true",
        help="include only executables, checksums, and app.ico in the zip",
    )
    args = parser.parse_args(argv)
    if args.name is None:
        parser.print_help()
        return 2
    try:
        name = validate_package_name(args.name)
    except ValueError as exc:
        parser.error(str(exc))
    try:
        sums = write_sums(DIST, name)
        print(f"wrote {sums.name}: {sums.read_text(encoding='utf-8').strip()}")
        if not args.hash_only:
            executables_only = (
                args.executables_only or not (DIST / f"{name}.exe").is_file()
            )
            z = make_zip(
                DIST, ROOT / f"{name}-windows.zip", executables_only=executables_only
            )
            print(f"wrote {z.name} ({z.stat().st_size} bytes)")
    except (OSError, ValueError, zipfile.LargeZipFile) as e:
        print(f"package failed: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
