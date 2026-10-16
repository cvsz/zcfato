# Verification Evidence

## Repository and source evidence

- Change branch is based on `b51b8d3821bb5524da1ea6a4f9135bdf72a1a151` (`main` at the time of this work).
- The control server's route inventory, token scopes, polling behavior, provider operations, and limitations were read from checked-in source and documentation.
- The supplied local `zchat-client/` package was untracked, contained 99 packaged files, and was not modified or committed.
- The regression change prevents a hidden or minimized LINE app from showing a callback-error dialog while retaining the file-log record.

## Automated verification

On 2026-10-15 in the isolated worktree based on `b51b8d3821bb5524da1ea6a4f9135bdf72a1a151`:

- `python -m unittest discover -s tests -v` from `line/`: 51 tests passed on Linux/WSL and 51 passed on native Windows.
- `make ci PYTHON=/tmp/zcfato-cs-audit-venv/bin/python`: repository validation passed; 26 control-server files passed format checks; Ruff reported no issues; root tests reported 710 passed and 3 skipped; control-server tests reported 40 passed; both pip-audit checks reported no known vulnerabilities. The editable control-server distribution was explicitly skipped by the installed-package audit.
- `git diff --check`: passed.

- `line/build.bat` completed successfully in a native Windows worktree and produced `line-status-changer.exe`.
- `line/tools/smoke_line_x.py` passed against the packaged executable: title-bar X hid the window to the tray, and tray Exit closed the process cleanly.
- The Windows smoke did not inject a callback failure or capture audio; audible-output acceptance remains unverified.

## Limits

Automated tests and the targeted Windows smoke do not establish audible behavior, Windows notification center behavior beyond the tested tray lifecycle, live Camfrog action completion, or a client/server chat integration. No deployment or production acceptance was performed.
