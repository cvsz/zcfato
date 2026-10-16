"""Reject fully elevated Windows tokens before invoking PyInstaller."""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes


TOKEN_QUERY = 0x0008
TOKEN_ELEVATION_TYPE = 18


def _token_elevation_type() -> int:
    if os.name != "nt":
        raise OSError("Windows token inspection is only available on Windows.")

    advapi32 = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32.dll", use_last_error=True)
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    advapi32.OpenProcessToken.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    )
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    )
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    process = kernel32.GetCurrentProcess()

    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(process, TOKEN_QUERY, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        elevation_type = ctypes.c_int()
        returned_length = ctypes.c_uint32()
        if not advapi32.GetTokenInformation(
            token,
            TOKEN_ELEVATION_TYPE,
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
