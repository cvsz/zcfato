# Contributing

Thanks for contributing to projects created from this template.

## Development workflow

1. Fork or create a feature branch from `main`.
2. Keep changes focused and reviewable.
3. Add or update tests for behavior changes.
4. Run the repository's formatting, linting, test, build, and security checks.
5. Update documentation and `CHANGELOG.md` when relevant.
6. Open a pull request and complete the checklist.

## Branch naming

Use concise prefixes such as `feat/`, `fix/`, `docs/`, `chore/`, `refactor/`, `test/`, or `security/`.

## Commit guidance

Prefer Conventional Commits, for example:

- `feat: add project scaffolding`
- `fix: handle empty configuration`
- `security: harden token validation`
- `docs: update deployment guide`

## Pull requests

Pull requests should explain the problem, implementation, testing, security impact, compatibility impact, and rollback plan where applicable. Do not bypass quality or security checks to make a pull request green.

## Security

Do not report exploitable vulnerabilities in public issues. Follow `SECURITY.md`.


## Repository validation

Before opening or updating a pull request, run the repository validator when your change affects template structure or documentation:

```bash
make validate-template
```

Do not merge from an older green commit after the PR head changes. Required checks must pass for the current exact head.

Windows-only integration checks live in `windows_tests/` and run from `build.bat`. The native MCI duration test verifies WAV duration when a compatible waveform output device is available. On headless Windows runners without one, it verifies that MCI reports the expected unavailable-device error and the application handles it gracefully. Run the test on a Windows desktop with audio output to verify the successful duration path; the portable suite uses mocked MCI commands.

Repository-administration changes require an authenticated admin identity and read-back verification. Supply the exact target repository, branch, and each required status-check name; the helper deliberately has no built-in repository or check defaults:

```bash
python3 scripts/github_admin.py --repo OWNER/REPOSITORY --branch DEFAULT_BRANCH \
  --required-check "EXACT_CHECK_NAME" --verify
```

Configuration intent alone is not evidence.
