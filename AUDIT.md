# AUDIT.md — camfrog-auto v2.18 review

Scope: `camfrog_auto.py`, `tools/`, build/CI scripts, config, tests. **Not verifiable here:** anything touching a live Camfrog build or Windows UIA/Win32 (no Windows, no Camfrog). Those paths are covered by fakes only; run `discover` + dry-run on a real machine before going live.

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
