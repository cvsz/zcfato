"""Root-level pytest configuration.

Prevents pytest collection from crawling Windows-only helper scripts in
``tools/`` and ``windows_tests/`` when run on Linux/macOS.  Those files
import win32gui, winreg, ctypes.windll at module level and raise
ModuleNotFoundError / AttributeError on non-Windows platforms.

CI already scopes collection with ``pytest -q tests``, but bare ``pytest``
from the repo root (e.g. during local development) would otherwise crash.
"""

import sys

# Always exclude these directory globs from collection.
# pytest reads this list before importing any collected module.
collect_ignore_glob: list[str] = []

if sys.platform != "win32":
    collect_ignore_glob += [
        "tools/*.py",
        "windows_tests/*.py",
    ]
