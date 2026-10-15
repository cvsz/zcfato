"""Reject fully elevated Windows tokens before invoking PyInstaller."""

from __future__ import annotations

import ctypes
import os
import sys


def _token_elevation_type() -> int:
    if os.name != "nt":
        raise OSError("Windows token inspection is only available on Windows.")

    advapi32 = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32.dll", use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    process = kernel32.GetCurrentProcess()

    token = ctypes.c_void_p()
    if not advapi32.OpenProcessToken(process, 8, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        elevation_type = ctypes.c_int()
        returned_length = ctypes.c_uint32()
        if not advapi32.GetTokenInformation(
            token,
            18,
            ctypes.byref(elevation_type),
            ctypes.sizeof(elevation_type),
            ctypes.byref(returned_length),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return elevation_type.value
    finally:
        kernel32.CloseHandle(token)


def main() -> int:
    try:
        elevation_type = _token_elevation_type()
    except OSError as exc:
        print(f"ERROR: Could not verify Windows token elevation: {exc}", file=sys.stderr)
        return 1

    if elevation_type == 2:
        print(
            "ERROR: Run Windows builds from a non-elevated terminal. "
            "PyInstaller does not support administrator builds.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
