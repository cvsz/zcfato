"""Post-build packaging / แพ็กเกจหลัง build  (stdlib only, no PowerShell needed)

  python tools/package.py NAME            writes dist/SHA256SUMS.txt and NAME-windows.zip
  python tools/package.py NAME --hash-only

Replaces PowerShell's Get-FileHash / Compress-Archive, which are missing on
Windows 7 / PowerShell < 4-5 or when PSModulePath is broken.
"""
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_sums(dist, name):
    exe = Path(dist) / f"{name}.exe"
    if not exe.is_file():
        raise FileNotFoundError(f"{exe} not found")
    out = Path(dist) / "SHA256SUMS.txt"
    exes = [exe] + sorted(p for p in Path(dist).glob("*.exe") if p != exe)  # e.g. the -gui exe too
    out.write_text("".join(f"{sha256_file(p)}  {p.name}\n" for p in exes), encoding="utf-8", newline="\n")
    return out


def make_zip(dist, zip_path):
    dist, zip_path = Path(dist), Path(zip_path)
    zip_path.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(dist.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(dist).as_posix())
    return zip_path


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    name = args[0]
    try:
        sums = write_sums(DIST, name)
        print(f"wrote {sums.name}: {sums.read_text(encoding='utf-8').strip()}")
        if "--hash-only" not in argv:
            z = make_zip(DIST, ROOT / f"{name}-windows.zip")
            print(f"wrote {z.name} ({z.stat().st_size} bytes)")
    except Exception as e:
        print(f"package failed: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
