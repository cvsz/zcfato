"""Small, per-user Windows integrations used by the LINE Status Changer."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "LINEStatusChanger"
APP_NAME = "LINE Status Changer"
MAX_PROFILE_IMAGE_BYTES = 25 * 1024 * 1024
PROFILE_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}


def startup_command(executable=None, script_path=None, config_path=None, frozen=None):
    """Build a quoted per-user startup command; testable without editing registry."""
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    if frozen:
        command = [str(executable or sys.executable)]
    else:
        python = str(executable or sys.executable)
        if os.name == "nt" and python.casefold().endswith("python.exe"):
            python = python[:-10] + "pythonw.exe"
        command = [python, str(script_path or Path(__file__).with_name("line_status_gui.py"))]
    if config_path:
        command.extend(("--config", str(config_path)))
    return subprocess.list2cmdline(command)


def set_startup(enabled, config_path=None):
    """Enable or remove the current-user Run entry. Does not require elevation."""
    if os.name != "nt":
        raise OSError("Start with Windows is available only on Windows.")
    import winreg

    command = startup_command(config_path=config_path)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                        winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, RUN_VALUE)
            except FileNotFoundError:
                pass
    return command if enabled else None


def validate_profile_image(path):
    """Return a resolved image path after basic local safety/format checks."""
    image = Path(path).expanduser().resolve(strict=True)
    if not image.is_file():
        raise ValueError("Choose an image file.")
    if image.suffix.casefold() not in PROFILE_IMAGE_EXTENSIONS:
        raise ValueError("Choose a PNG, JPG, JPEG, BMP, or GIF image.")
    size = image.stat().st_size
    if size <= 0:
        raise ValueError("The selected image file is empty.")
    if size > MAX_PROFILE_IMAGE_BYTES:
        raise ValueError("The image is larger than the 25 MB helper limit.")
    with image.open("rb") as stream:
        header = stream.read(12)
    signatures = {
        ".png": header.startswith(b"\x89PNG\r\n\x1a\n"),
        ".jpg": header.startswith(b"\xff\xd8\xff"),
        ".jpeg": header.startswith(b"\xff\xd8\xff"),
        ".bmp": header.startswith(b"BM"),
        ".gif": header.startswith((b"GIF87a", b"GIF89a")),
    }
    if not signatures[image.suffix.casefold()]:
        raise ValueError("The file contents do not match its image extension.")
    return image
