"""Root-level pytest configuration.

Prevents pytest collection from crawling Windows-only helper scripts in
``tools/`` and ``windows_tests/`` when run on Linux/macOS.  Those files
import win32gui, winreg, ctypes.windll at module level and raise
ModuleNotFoundError / AttributeError on non-Windows platforms.

CI already scopes collection with ``pytest -q tests``, but bare ``pytest``
from the repo root (e.g. during local development) would otherwise crash.
"""

import sys
from pathlib import Path

# Always exclude these directory globs from collection.
# pytest reads this list before importing any collected module.
collect_ignore_glob: list[str] = []

if sys.platform != "win32":
    collect_ignore_glob += [
        "tools/*.py",
        "windows_tests/*.py",
    ]

# Make the reorganized source layout importable: shared runtime modules in
# src/camfrog and standalone feature modules in src/features keep their
# flat top-level import names (no packages), resolved via these paths.
_REPO_ROOT = Path(__file__).resolve().parent
for _dirname in ("src/camfrog", "src/features"):
    _candidate = str(_REPO_ROOT / _dirname)
    if _candidate not in sys.path:
        sys.path.insert(0, _candidate)
