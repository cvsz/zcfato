# AUDIT.md — Source Audit (2026-10-11)

## Current review

Scope: application and helper source, GUI split modules, repository administration, Windows process shutdown, build/CI definitions, tests, and user/operator documentation. Existing uncommitted user work was preserved.

### Findings fixed

| Area | Finding | Correction |
|---|---|---|
| Template validation | `make validate-template` discovered every test with `unittest`; pytest-only modules failed to import, while pytest function tests were not run by unittest. | The target now runs the repository/link validator and only the isolated bootstrap unittest module. A regression test protects the command. |
| GitHub administration | The helper had a hard-coded repository and stale required-check names that did not match this checkout; dry-run also required authentication. | Repo, branch, and exact check names are explicit arguments; checks are required for mutation/verification, dry-run stays offline, and branch names are URL-encoded. |
| Windows process shutdown | Multiple applications resolved `taskkill` through command search, allowing a same-named executable in the current directory or PATH to intercept shutdown. | Calls now resolve `taskkill.exe` using `GetSystemDirectoryW`; an AST regression check rejects bare command lookup. |
| CI and docs | Core CI used movable action tags, omitted template validation and the separate LINE executable build, and related docs described old validation/admin behavior. | Workflow actions are SHA-pinned, template validation runs in CI, the Windows job runs the full build, and docs describe the executable-only LINE artifact and explicit administration inputs. |
| IM reply visibility | A successful local outgoing echo was easy to read as recipient delivery, and later messages could leave the echo above the visible history viewport. | IM Auto-reply locates the exact local echo and scrolls it into view; logs and manuals now say local UI evidence does not confirm recipient delivery. A failed-before-submit message remains pending; an ambiguous send is not repeated. |
| IM Auto-reply Activity Log | GUI actions were visible only as transient status text; log-file changes in settings did not reconfigure the GUI logger. | Added a live Activity Log tab with action results and bounded, credential-redacted error details; saving config now reconfigures the logger. Worker events continue to use the configured chat-text privacy switch. |
| Worker PID reuse and mutex diagnostics | A stale PID could identify the current launcher or an unrelated Python process after PID reuse; mutex acquisition logging also referenced undefined names. | PID identity now includes process creation time and uses the per-app mutex to establish liveness; the mutex logging no longer references missing variables. Stop remains cooperative unless executable identity and process creation time match. |
| SHA-1 static warning | Bandit flagged SHA-1 in the WebSocket accept calculation. | The RFC WebSocket handshake explicitly marks this protocol-mandated SHA-1 use as `usedforsecurity=False`, which also permits FIPS-mode runtimes. |
| Build provenance | The batch `FOR /F` parser could miss dirty `git status` output and write `clean=true` for artifacts built from modified source. | `full-build.bat` now captures status into a temporary file and marks the tree clean only after `git status` succeeds and the file is empty; status-check errors retain the fail-closed `clean=false` default. The release gate also requires the recorded commit to match. A regression test covers this contract. |

### Verification evidence

- `make validate-template`: repository structure/links valid; **5 bootstrap tests passed**.
- Windows CPython **3.12.10** `full-build.bat`: **BUILD OK** for all eight Camfrog executables and LINE Status Changer. Gates passed: root **638 passed, 2 skipped, 3 subtests**, isolated private-chat GUI **5 passed**, and LINE **49 passed**. The ZIP was created and all eight executable hashes were independently verified; the ZIP contains exactly those eight feature executables.
- Build-source read-back matches HEAD `fe5904c16488aaa8af56157245403e007a7e0d3d` and correctly says `clean=false` while the worktree contains **73** changed/untracked entries. No release was published; the release gate therefore cannot mistake these dirty artifacts for a clean checkout.
- The exact batch status-capture block was also run under `cmd.exe` against a temporary committed repository: it returned `clean=true` for the clean checkout and `clean=false` after modifying a tracked file.
- Packaged IM Auto-reply opened on Windows 11 and its window responded. A read-only MSHTML inspection found the outgoing local echo in chat history; the new helper scrolled it into the viewport. No new message was sent during this smoke check, and this does not confirm remote delivery or pixel-level visibility when another window covers Camfrog.
- After the package build, the existing source worker (PID 24584) was stopped through the app's guarded stop command. Windows confirmed that PID exited and both its PID and STOP files were removed. The packaged GUI remained visible, enabled, responsive, and exposed 31 UI Automation descendants; no worker was started and no message was sent during this check.
- `pip-audit` on Windows CPython 3.12: **No known vulnerabilities found** for root runtime/development requirements or `line/requirements-build.txt`.
- Bandit scan of all **66 tracked/untracked Python source and test files**: **0 high, 27 medium, 1,557 low heuristics**. The remaining B310 reports are three GitHub release URL opens copied across the standalone apps; the API endpoint is fixed, and download/checksum URLs are allowlisted before use with final-response validation. B102 is suppressed only on the test call that executes a compiled AST method from this repository to isolate background-thread error handling; it does not execute user input. The large low-severity count consists of heuristic subprocess, exception-handling, and pseudo-random-use reports rather than confirmed defects.
- CI YAML parsed successfully; checkout/setup-python/upload-artifact refs were checked against their upstream tags and pinned to immutable commits.
- `git diff --check` passed.

### Limits and remaining verification

- Follow-up validation on Windows CPython 3.12.10: the focused IM/GUI/PID suites passed (**178 passed**); `py_compile` and `git diff --check` passed. The current `full-build.bat` passed: root **640 passed, 2 skipped, 3 subtests**, isolated private-chat GUI **5 passed**, LINE **49 passed**, all eight Camfrog executables and the LINE executable built, and the feature ZIP/checksum set verified. `dist/BUILD_SOURCE.txt` records HEAD `fe5904c16488aaa8af56157245403e007a7e0d3d` with `clean=false` because the worktree is dirty. No GitHub release was published.
- The source IM GUI smoke confirmed the five-tab layout and Activity Log entry. The newly built IM Auto-reply executable was opened and restored visibly; its Tk notebook labels were not exposed through Windows UI Automation, so packaged tab rendering was not independently inspected. No worker was started and no Camfrog message was sent during this check.

- Live testing confirmed only local UI echo presence and viewport scrolling. Recipient delivery, every Camfrog build/control, sound behavior, hidden/minimized-window operation, and Windows lock/disconnect behavior remain outside the verified evidence.
- GitHub administration was not applied or verified against a live repository; no remote settings or release were changed.
- PyInstaller emitted its administrator-context warning in this environment. The build succeeded; normal builds should run from a non-administrator terminal.

## Archived audit notes (v2.18)

The following review notes describe an earlier snapshot and are retained as history only; they are not current validation evidence.

Historical scope: `camfrog_auto.py`, `tools/`, build/CI scripts, config, tests. At the time, live Camfrog and Windows UIA/Win32 behavior had not been verified; this is not a statement about the current test environment.

## Fixed (each has a regression test in `tests/test_audit_fixes.py`)
| # | Sev | Defect | Fix |
|---|---|---|---|
| 1 | High | `stop` could `taskkill /F` an **unrelated process** if the PID in a stale `camfrog_auto.pid` had been reused | `pid_is_ours()` checks the process image (camfrog*/python*/own exe name) in `start`, `stop`, `state`, single-instance guard |
| 2 | High | Shipped defaults made `status.edit` and `autoreply.history` the **same control**; going live without `discover` would type statuses into the chat-history box | selector clash = warning (dry-run) / error (live); empty selectors = error |
| 3 | High | Foreground was checked, then `set_focus()`, then Enter: focus stolen in between sent the keystroke to another app | foreground re-checked immediately before Enter |
| 4 | Med | Room switch / history reload dumped old lines that were then answered (up to the hourly cap) | >25 fresh lines in one poll = reset, not answered |
| 5 | Med | Status history stopped learning at `max_items`: the newcomer (count 0) was the eviction victim | newcomer is never evicted |
| 6 | Med | Shipped `skip_patterns` used `\b` around Thai (`\bเว็บพนัน\b`): never matched Thai inside a sentence | pattern fixed; documented in CONFIG.md |
| 7 | Med | `poll_seconds <= 0`, `max_length 0`, etc. were accepted (busy loop / negative sleep crash) | numeric range validation |
| 8 | Low | `text[:limit]` could cut a Thai leading vowel/mark from its consonant (status, reply, marquee frames) | cluster-aware `clip()` |
| 9 | Low | Hot reload reset rule cooldowns; `sender_last` grew unbounded | cooldowns carried over; pruned |

## v2.16: private-message (IM) auto-reply (offline-tested only)
- Separate `autoreply_im` section; room auto-reply is unchanged and still refuses IM windows (`log_kind: room`).
- Enabling it while `autoreply.log_kind` is `im`/`any` is a validation error: room rules must never answer a private chat.
- Matching code is shared with the room path (`evaluate_message` via `im_view`), so `test-rules --im` shows exactly what the live loop does.
- Open: the IM send path and the `wb-log-mtim-data` pane kind are **unverified on a live Camfrog**; `answer_first_message` relies on a new IM window showing only the opening line, which a live session must confirm.
- Open: a friend's multi-line message can forge a `Nick: text` line (same caveat as rooms); the allowlist and per-friend caps bound the effect.
- v2.17: `im-probe` diagnostic; optional `autoreply_im.log_kinds: ["im", "mtim"]` (mtim = unverified, off by default); startup/no-window log hints.

## v2.18: code quality & build hardening
- **Type hints** added to ~30 public functions in `camfrog_auto.py` for better IDE support and maintainability.
- **All `.bat` files** now use CRLF line endings (required by `cmd.exe`); CI test `test_bat_files_are_crlf` passes.
- **GPG commit signing** configured with new ECDSA (nistp256) key; full history resigned and force-pushed.
- **Test coverage**: 170 passing tests (1 skipped for GUI smoke test requiring display), including all audit fix regressions.
- **Flaky clipboard test** hardened with retry + skip logic.

## Open / by design (not changed)
- **Untested against live Camfrog**: default selectors are guesses.
- Multi-line chat messages can contain a forged `Nick: text` line; the bot may answer that nick (rate limits apply). Cannot be distinguished from UIA text alone.
- `active_hours` with `start == end` matches one minute only.
- `log.log_message_text` defaults to `true`: chat text is written to the log (privacy). Switch off in Advanced.
- Windows cannot type into another app without focusing it; each send briefly takes focus. Check Camfrog's terms and room rules before enabling automation.
- `docs/CODEX-MASTER-PROMPTS.md` audits a different repo (`cvsz/zcsc`), not this code.
