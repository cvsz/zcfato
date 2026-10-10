"""Run pytest on the Windows host over SSH (stdlib only).

Tests that need Windows (tkinter GUI, DPAPI, Chrome store, named mutex) skip
on Linux. This script runs them where they pass instead:

  python tools/run_remote_tests.py                          # web-status GUI tests
  python tools/run_remote_tests.py tests/test_update.py -q  # any pytest args

Host/user/repo are env-configurable; the default is the dev Windows box:
  CAMFROG_WINDOWS_HOST=192.168.1.85  CAMFROG_WINDOWS_USER=cvsz
  CAMFROG_WINDOWS_DIR=D:\\data\\camfrog
  CAMFROG_WINDOWS_PYTHON=.venv\\Scripts\\python.exe

Authentication reuses your existing SSH setup (keys/agent or an already-open
`ssh -M` control socket). No passwords or tokens are handled here.
"""
import os
import subprocess
import sys

HOST = os.environ.get("CAMFROG_WINDOWS_HOST", "192.168.1.85")
USER = os.environ.get("CAMFROG_WINDOWS_USER", "cvsz")
REMOTE_DIR = os.environ.get("CAMFROG_WINDOWS_DIR", r"D:\data\camfrog")
REMOTE_PY = os.environ.get("CAMFROG_WINDOWS_PYTHON", r".venv\Scripts\python.exe")
CONTROL_SOCK = "/tmp/opencode/win.sock"


def build_command(pytest_args):
    """ssh argv that runs pytest with the given args on the Windows host."""
    remote = "cd {0}; {1} -m pytest {2}".format(
        REMOTE_DIR, REMOTE_PY, " ".join(pytest_args))
    cmd = ["ssh"]
    if os.path.exists(CONTROL_SOCK):
        cmd += ["-S", CONTROL_SOCK]
    cmd += ["{0}@{1}".format(USER, HOST), remote]
    return cmd


def main(argv=None):
    pytest_args = list(argv) if argv else ["tests/test_web_status_gui.py", "-v"]
    cmd = build_command(pytest_args)
    print("+ {0}".format(" ".join(cmd)))
    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
