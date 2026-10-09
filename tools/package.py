"""Post-build packaging / แพ็กเกจหลัง build  (stdlib only, no PowerShell needed)

  python tools/package.py NAME            hashes dist/ executables and writes NAME-windows.zip
  python tools/package.py NAME --hash-only
  python tools/package.py NAME --executables-only  excludes local app data from the zip

Replaces PowerShell's Get-FileHash / Compress-Archive, which are missing on
Windows 7 / PowerShell < 4-5 or when PSModulePath is broken.
"""
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
FEATURE_EXECUTABLES = (
    "chat-im-private/chat-im-private.exe",
    "im-autoreply/im-autoreply.exe",
    "music-dj/music-dj.exe",
    "room-control/room-control.exe",
    "status-marquee/status-marquee.exe",
    "status-random/status-random.exe",
    "web-status/web-status.exe",
)


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_sums(dist, name):
    dist = Path(dist)
    if name == "camfrog-features":
        expected = set(FEATURE_EXECUTABLES)
        actual = {p.relative_to(dist).as_posix() for p in dist.rglob("*.exe") if p.is_file()}
        if actual != expected:
            missing = sorted(expected - actual)
            unexpected = sorted(actual - expected)
            raise ValueError(f"Unexpected Camfrog executable set; missing={missing}, extra={unexpected}")
        exes = [dist / relative for relative in FEATURE_EXECUTABLES]
    else:
        primary = dist / f"{name}.exe"
        if primary.is_file():
            exes = [primary] + sorted(p for p in dist.glob("*.exe") if p != primary)
        else:
            exes = sorted(p for p in dist.rglob("*.exe") if p.is_file())
    if not exes:
        raise FileNotFoundError(f"No executable files found in {dist}")
    out = Path(dist) / "SHA256SUMS.txt"
    out.write_text("".join(
        f"{sha256_file(p)}  {p.relative_to(dist).as_posix()}\n" for p in exes),
        encoding="utf-8", newline="\n")
    return out


def make_zip(dist, zip_path, executables_only=False):
    dist, zip_path = Path(dist), Path(zip_path)
    zip_path.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(dist.rglob("*")):
            include = (p.suffix.lower() == ".exe" or p.name == "SHA256SUMS.txt")
            if p.is_file() and (not executables_only or include):
                z.write(p, p.relative_to(dist).as_posix())
    return zip_path


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    name = args[0]
    if name == "camfrog-features":
        (DIST / "SHA256SUMS.txt").unlink(missing_ok=True)
        (ROOT / f"{name}-windows.zip").unlink(missing_ok=True)
        (ROOT / "camfrog-auto-windows.zip").unlink(missing_ok=True)
    try:
        sums = write_sums(DIST, name)
        print(f"wrote {sums.name}: {sums.read_text(encoding='utf-8').strip()}")
        if "--hash-only" not in argv:
            executables_only = ("--executables-only" in argv or
                                not (DIST / f"{name}.exe").is_file())
            z = make_zip(DIST, ROOT / f"{name}-windows.zip",
                         executables_only=executables_only)
            print(f"wrote {z.name} ({z.stat().st_size} bytes)")
    except Exception as e:
        print(f"package failed: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
