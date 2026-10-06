"""Build-environment doctor / ตรวจสภาพแวดล้อมก่อน build  (stdlib only)

  python tools/doctor.py            full check (also tries to download the pywin32 wheel)
  python tools/doctor.py --quick    interpreter checks only (no network); exit 1 if unusable
"""
import os
import platform
import struct
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def interpreter_info():
    return {
        "version": sys.version_info[:3],
        "bits": struct.calcsize("P") * 8,
        "machine": platform.machine(),
        "impl": platform.python_implementation(),
        "free_threaded": bool(sysconfig.get_config_var("Py_GIL_DISABLED")),
        "windows": os.name == "nt",
    }


def diagnose(info):
    """Return a list of (EN, TH) problems that make pywin32 wheels unavailable."""
    out, v = [], info["version"]
    if not info["windows"]:
        out.append(("This tool targets Windows; run build.bat on Windows.",
                    "เครื่องมือนี้สำหรับ Windows เท่านั้น"))
    if info["impl"] != "CPython":
        out.append((f"{info['impl']} is not supported by pywin32 wheels. Use CPython.",
                    f"{info['impl']} ไม่มี pywin32 wheel ให้ใช้ CPython"))
    if info["free_threaded"]:
        out.append(("Free-threaded Python (the 't' build) has no pywin32 wheels. Install the normal build.",
                    "Python แบบ free-threaded (รุ่น 't') ไม่มี pywin32 wheel ให้ติดตั้งรุ่นปกติ"))
    if info["bits"] == 32 and (3, 9) <= v[:2] <= (3, 13):
        out.append(("32-bit Python 3.9-3.13 has no pywin32 wheel (only 64-bit/ARM64). Install 64-bit Python.",
                    "Python 32-bit รุ่น 3.9-3.13 ไม่มี pywin32 wheel ให้ติดตั้ง Python 64-bit"))
    if v[:2] < (3, 8):
        out.append((f"Python {v[0]}.{v[1]} is too old. Install Python 3.13 (64-bit).",
                    f"Python {v[0]}.{v[1]} เก่าเกินไป ให้ติดตั้ง Python 3.13 (64-bit)"))
    if v[:2] >= (3, 16):
        out.append((f"Python {v[0]}.{v[1]} is newer than the pywin32 wheels known to exist (up to 3.15). Use Python 3.13.",
                    f"Python {v[0]}.{v[1]} ใหม่กว่า pywin32 ที่มี (ถึง 3.15) ให้ใช้ Python 3.13"))
    return out


def stale_files():
    """Detect an old, partially-updated project folder."""
    out = []
    req = ROOT / "requirements.txt"
    if req.exists():
        lines = [x.strip() for x in req.read_text(encoding="utf-8").splitlines()
                 if x.strip() and not x.strip().startswith("#")]
        if lines and lines[0].lower().startswith("pywinauto"):
            out.append(("requirements.txt is an OLD version (pywinauto first, no pywin32 pin). Re-extract the latest zip into a clean folder.",
                        "requirements.txt เป็นไฟล์เก่า ให้แตก zip ล่าสุดลงโฟลเดอร์ใหม่"))
    bat = ROOT / "build.bat"
    if bat.exists() and "Using Python" not in bat.read_text(encoding="utf-8", errors="ignore"):
        out.append(("build.bat is an OLD version (no Python auto-selection). Re-extract the latest zip.",
                    "build.bat เป็นไฟล์เก่า ให้แตก zip ล่าสุด"))
    return out


def icon_problem():
    """app.ico must exist and be a real multi-size .ico, or the exe gets no icon."""
    ico = ROOT / "app.ico"
    if not ico.exists():
        return ("app.ico not found: exe will be built WITHOUT an icon.",
                "ไม่พบ app.ico: exe จะไม่มีไอคอน")
    d = ico.read_bytes()
    if len(d) < 22 or d[:4] != b"\x00\x00\x01\x00":
        return ("app.ico is not a valid .ico file (renamed PNG?). Re-export it as a real .ico.",
                "app.ico ไม่ใช่ไฟล์ .ico จริง (อาจแค่เปลี่ยนนามสกุลจาก PNG) ให้ export ใหม่")
    return None


def try_download():
    with tempfile.TemporaryDirectory() as d:
        r = subprocess.run([sys.executable, "-m", "pip", "download", "pywin32>=311",
                            "--only-binary=:all:", "--no-deps", "-d", d, "-q"],
                           capture_output=True, text=True)
        return r.returncode == 0, (r.stderr or r.stdout).strip().splitlines()[-3:]


def main(argv):
    quick = "--quick" in argv
    info = interpreter_info()
    v = info["version"]
    print(f"Python      : {v[0]}.{v[1]}.{v[2]}  {info['impl']}  {info['bits']}-bit  ({info['machine']})")
    print(f"Executable  : {sys.executable}")
    print(f"Free-thread : {info['free_threaded']}")
    problems = diagnose(info) + ([] if quick else stale_files())
    if not quick:
        ip = icon_problem()
        if ip:
            problems.append(ip)
    for en, th in problems:
        print(f"\n[PROBLEM] {en}\n          {th}")
    if quick:
        return 1 if diagnose(info) else 0
    if not diagnose(info) and info["windows"]:
        ok, tail = try_download()
        print("\npywin32 wheel download:", "OK" if ok else "FAILED")
        if not ok:
            print("\n".join("  " + x for x in tail))
            print("[PROBLEM] pip could not fetch a pywin32 wheel for this interpreter (offline? proxy? mirror without wheels?).\n"
                  "          pip โหลด pywin32 ไม่ได้ (ออฟไลน์/proxy/mirror?) ลอง: python -m pip install --upgrade pip")
            problems.append(("download", "download"))
    if problems:
        print("\nFIX / วิธีแก้:  winget install Python.Python.3.13   (64-bit)  then delete the .venv folder and run build.bat")
        return 1
    print("\nNo problems found / ไม่พบปัญหา")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
