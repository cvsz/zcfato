# Changelog — camfrog-auto

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/);
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Music DJ app** (`music-dj`): room bot that answers `!request` / `!queue` / `!current` / `!skip` / `!help` in chat, keeps a persistent `dj_queue.json`, and can play `.wav` files locally (`dj.audio_backend: "local"`) with automatic next-song advance. New `dj` config section; needs `autoreply.enabled` for chat plumbing. GUI has a queue view with owner Skip/Clear buttons.
- `--chrome` CLI flag and GUI **Chrome** button: import the Camfrog session straight from Chrome's cookie store (nothing written to disk; DPAPI / AES-GCM decrypted in memory; clear error points to the cookies.txt fallback when the `cryptography` package is missing).
- Chrome 127+ keeps its cookie DB under `<profile>/Network/Cookies`; the finder now prefers it over the legacy `<profile>/Cookies`.
- `https://profiles.camfrog.com/home.php` session probe with real signed-in markers (`nav-user-logged`, `_user_id`, `nick`), plus the captured status-update endpoint (`/ajax/update_status.php`, POST `{status, csrf}`) implemented behind the `--confirm-update` gate.
- `status.marquee.scroll` (default `false`): one whole pool line per tick, lines rotate 1..N and wrap; `true` keeps the old frame-scrolling behavior.

### Added
- Encrypted account store for web-status: the GUI's **Account (stored encrypted)** section seals the nickname/password with Windows DPAPI into `.env.enc` (git-ignored, decrypts only under the same Windows user); the CLI then needs no `--login` and no password prompt. Plaintext `.env` still works as a legacy fallback.

### Changed
- **GUI split: one self-contained module per feature exe.** `room_control_gui.py`, `im_autoreply_gui.py`, `camfrog_music_gui.py`, `status_random_gui.py`, `status_marquee_gui.py`, `chat_im_private_gui.py` (renamed from `camfrog_private_chat_gui.py`), and `web_status_gui.py` (now includes the former `tools/web_status.py` logic) each inline the engine and clipboard helpers they need; no module imports another project module. Entry points no longer switch profiles/modes through environment variables. See `docs/gui-split.md`.

### Fixed
- `Runner.__init__` initializes resolve targets so the resolve-retry loop degrades to warnings instead of crashing.
- Chrome DPAPI decryption no longer reads freed memory (`_data_blob` pins the backing buffer).

## [2.18.0] - 2026-10-07

### Added
- Type hints on ~30 public functions in `camfrog_auto.py` for better IDE support.
- CRLF line endings on all `.bat` files; CI test `test_bat_files_are_crlf` added.
- GPG commit signing with ECDSA (nistp256) key; full history resigned.
- Retry + skip logic for flaky clipboard test in `tests/test_gui.py`.

### Fixed
- IM sender last-seen pruning now uses `per_sender_cooldown_seconds` (was `max(cooldown, 86400)`).
- `log_kind()` returns `None` instead of `""` on failure for clearer semantics.
- Added clarifying comment about `NICK_RE` vs `LINE_RE` Unicode handling.

### Changed
- Build script `build.bat` and all helper `.bat` files use CRLF.
- All 170 tests pass (1 skipped for GUI smoke test requiring display).

## [2.17.0] - 2026-10-07

### Added
- `camfrog-auto im-probe` command: diagnostic for IM auto-reply configuration and window classification.
- Optional `autoreply_im.log_kinds: ["im", "mtim"]` (mtim = unverified, off by default).
- Startup summary and "no private-chat window found" log hints for IM.

### Fixed
- IM auto-reply now properly refuses to run when `autoreply.own_nickname` is empty even in dry-run.

## [2.16.0] - 2026-10-07

### Added
- Private-message (IM) auto-reply: separate `autoreply_im` section with own rules, allowlist, and limits.
- Mandatory `autoreply_im.only_nicknames` (non-empty allowlist).
- Per-sender cooldown, daily cap, hourly cap, and global gap for IM.
- Reply prefix `[auto] ` to prevent bot-to-bot loops.
- `answer_first_message` for new IM windows with a single line from a listed friend.
- Shared matching code via `im_view()` so `test-rules --im` mirrors live behavior.
- Validation: empty allowlist, empty own_nickname, `log_kind` must be `room` when room auto-reply is on.

### Changed
- `log_kind()` now returns `"mtim"` for tabbed IM windows (previously only `room`/`im`).

## [2.15.0] - 2026-10-07

### Fixed
- Selector clash detection: warns in dry-run, errors in live mode.
- PID reuse guard: `stop` verifies process image before killing.
- Foreground re-check immediately before Enter to prevent focus-stealing.
- Burst detection: >25 new lines in one poll = reset, not answered.
- Status history eviction: newcomer (count 0) never evicted.
- Thai skip patterns: removed `\b` word boundaries (Thai has none).
- Numeric range validation for all config values.
- Thai cluster-aware `clip()` prevents cutting vowels/marks.
- Hot reload preserves rule cooldowns; `sender_last` pruned.

## [2.14.0] - 2026-10-07

### Added
- Marquee (scrolling status): `status.marquee` with width, stride, step_seconds, cycles, max_frames.
- Status history as source: `status.history.use_as_source` with modes rotate/random/most_used.
- Language cycle: `status.language_cycle` alternates TH/EN on each status change.
- TH/EN auto-detection from Windows UI language.

### Changed
- Default `status.interval_seconds` lowered to 300 (was 600).
- Marquee defaults: 2 Thai-safe clusters every 0.5 seconds.

## [2.13.0] - 2026-10-07

### Added
- GUI: `camfrog-auto-gui.exe` with tabs for Dashboard, Setup, Status, Auto-reply, History, Advanced.
- Offline rule tester: `test-rules` command and GUI tester.
- `discover` command dumps full control tree to `controls.txt`.
- `detect` command auto-proposes selectors for Camfrog 8.x.
- `check` command validates config with bilingual error messages.
- Background mode: `start`/`stop`/`state`/`autostart-on`/`autostart-off`.

### Fixed
- Atomic config writes with retry loop for AV/indexer locks.
- Single-instance guard with PID file.
- Rotating log with `log_message_text` toggle for privacy.

## [2.12.0] - 2026-10-07

### Fixed
- Room log parsing: corrected from RichEdit/Chromium to embedded IE/MSHTML panes.
- Chat input is web editable box (no native Edit/RichEdit).
- `read_chat()` uses UIA TextPattern on Document control.

## [2.11.0] - 2026-10-07

### Added
- Multi-window support: Camfrog opens each room/IM as separate window of same process.
- Automatic room attachment via `get_chat_window()` scanning process windows.
- `autoreply.window_title_regex` to narrow room selection.

## [2.10.0] - 2026-10-07

### Added
- Status rotation with schedules (`status.schedules`).
- Random/sequential message selection.
- Per-sender cooldown, global gap, hourly cap for auto-reply.

## [2.9.0] - 2026-10-07

### Added
- Auto-reply with regex rules, bilingual replies, mention filter.
- Skip patterns and link ignore.

## [2.8.0] - 2026-10-07

### Added
- Custom status setting via UIA.
- One-shot `status` command.

## [2.7.0] - 2026-10-07

### Added
- Initial release: status rotation + auto-reply for Camfrog on Windows using UIA.
