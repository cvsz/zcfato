# Development

This repository contains the Windows feature apps and the separate ZChat Control Server. Keep local credentials and runtime data outside Git.

## Desktop apps

- Build on Windows with Python 3.12 x64: run `build.bat` for the eight feature apps, or `full-build.bat` / `full-build.ps1` for the feature apps and LINE app.
- The Windows packaging job runs from the exact pull-request head. A successful local test suite alone does not prove Camfrog UI or live-room behavior.
- On Linux, `make build` exits with a clear Windows-only message; do not treat it as a successful package build.

## ZChat Control Server local setup

The local Compose stack runs PostgreSQL in a persistent Docker volume and binds the API to `127.0.0.1:8000`. It does not use an external database.

PowerShell:

```powershell
Set-Location control-server
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test,lint]"
python -m camfrog_control_server.local_setup
docker compose --env-file "$env:USERPROFILE\.config\zchat-control\.env" up --build
```

Bash:

```bash
cd control-server
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test,lint]'
python -m camfrog_control_server.local_setup
docker compose --env-file "$HOME/.config/zchat-control/.env" up --build
```

Run `local_setup` only when creating a new local stack. It creates local credentials and refuses to overwrite an existing file. For an existing stack, reuse its existing secret file and PostgreSQL volume; do not create replacement credentials for that database. `/healthz` reports process health, `/readyz` checks PostgreSQL, and `/dashboard` serves the local UI. Detailed API and security boundaries are in [`../control-server/README.md`](../control-server/README.md).

## Validation

Install root and server development dependencies with `make setup`, then run `make ci`. This runs repository/link validation, server format/lint, both Python test suites, and dependency audits. Package validation is separate and must run on Windows.

Windows-only tests (tkinter GUI, DPAPI, Chrome store) skip on Linux; run them
on the configured Windows host instead (SSH authentication required):

   ```bash
   python3 tools/run_remote_tests.py tests/test_web_status_gui.py -v
   ```

## Quality expectations

- Keep changes small and reviewable.
- Read `AGENTS.md` and narrower subtree instructions before editing.
- Add tests for behavior changes.
- Prefer deterministic/reproducible tooling.
- Keep CI permissions least privilege.
- Pin Actions/dependencies according to the project's supply-chain policy.
- Do not commit secrets or local credentials.
- Do not weaken security/CI gates to obtain a passing build.
- Fix the root cause of failed validation rather than excluding relevant checks.

## Pull-request validation

Before merge, capture exact-head evidence for the checks that apply to the change. Do not rely on a previously green commit after the PR head has changed.

For repository administration changes, use the read-back verifier:

```bash
python3 scripts/github_admin.py --repo OWNER/REPOSITORY --branch DEFAULT_BRANCH --required-check "EXACT_CHECK_NAME" --verify
```

Pass `--branch DEFAULT_BRANCH` and one `--required-check "EXACT_CHECK_NAME"` per actual status-check context. The helper requires these explicit target values before it can verify GitHub state.

## Documentation

Update architecture, development, release, governance, security, ADRs, and operational docs when their assumptions change.

Documentation must distinguish intended configuration from verified effective state.
