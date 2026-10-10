# GUI split: one module per feature exe

Every packaged feature app is built from exactly **one self-contained Python
module**. A module may not import another project module (no `camfrog_auto`, no
`camfrog_gui`, no `tools.web_status`, no `clipboard_support`). Logic that several
apps need is inlined into each of them; that duplication is deliberate — each
`.exe` must be shippable alone and must break alone.

## Modules and where their blocks come from

| Module (entry point) | Inlined engine | Inlined GUI | Notes |
|---|---|---|---|
| `room_control_gui.py` (`room_control_entry.py`) | `camfrog_auto.py`, profile `room` | `camfrog_gui.py`, room profile | `ClipboardController` from `clipboard_support.py` |
| `im_autoreply_gui.py` (`im_autoreply_entry.py`) | `camfrog_auto.py`, profile `im_reply` | `camfrog_gui.py`, im_reply profile | `ClipboardController` from `clipboard_support.py` |
| `camfrog_music_gui.py` (`music_dj_entry.py`) | `camfrog_auto.py`, profile `music` | `camfrog_gui.py`, profile `music` | Adds the DJ tab (queue view + owner actions); reuses the `dj` engine section |
| `status_random_gui.py` (`status_random_entry.py`) | `camfrog_auto.py`, profile `status` | `camfrog_status_gui.py`, mode `random` | `SingleInstanceGuard`, pool helpers, `--worker` commands and `ClipboardController` kept; `cmd_start` / `cmd_stop` are the app's DATA_DIR versions (the engine copies are not carried) |
| `status_marquee_gui.py` (`status_marquee_entry.py`) | `camfrog_auto.py`, profile `status` | `camfrog_status_gui.py`, mode `marquee` | Same as above; keeps marquee-only widgets |
| `chat_im_private_gui.py` (`chat_im_private_entry.py`) | `camfrog_auto.py` | `camfrog_private_chat_gui.py` | Renamed from `camfrog_private_chat_gui.py` |
| `web_status_gui.py` (`web_status_entry.py`) | — | merged in place | `tools/web_status.py` logic inlined (`main` → `cli_main`); `tools/web_status.py` stays for the source CLI and its tests |

## Engine changes forced by the inlining

- `APP_PROFILE` is a constant per module (not an env read); entry points no
  longer switch profiles or modes through the environment.
- The engine's `main` is renamed `cli_main` so each module can keep its own GUI
  `main` (also what `start` relaunches and what `--worker run` uses in the
  status apps).
- `RUN_VALUE` for the status profile is mode-specific
  (`CamfrogStatusRandom` / `CamfrogStatusMarquee`) so the two exes get separate
  autostart entries.
- The status apps' `PROFILE_COMMANDS` set drops `marquee` in the random exe.
- `DEFAULTS` in the status apps keep their own file names
  (`camfrog_status_changer.*`) plus the `dj` section the engine validator reads.

## Combined sources (unchanged, still the lineage)

`camfrog_auto.py`, `camfrog_gui.py`, `camfrog_status_gui.py`,
`camfrog_private_chat_gui.py`, `tools/web_status.py`, and `clipboard_support.py`
remain in the tree: the source-only CLI and their test suites keep using them,
and they document where each split module came from.

## Releases and self-update

`full-build.bat` records the source commit and whether the working tree was clean in ignored `dist/BUILD_SOURCE.txt`. `tools/release.py` publishes a GitHub release from those outputs: one asset per app (stable names — `room-control.exe`, `music-dj.exe`, …), the all-features zip, a generated generic LINE config, and `SHA256SUMS.txt`. It requires the artifact marker to match a clean `main` checkout that exactly matches `origin/main`, rejects an existing release tag that points elsewhere (including annotated tags), and pins new tags to that commit. It never uploads the build machine's saved LINE settings. Notes come from the matching `CHANGELOG.md` section; version comes from `APP_VERSION` in `camfrog_auto.py` (kept in sync in every split module).

Each app carries the same inlined self-update block: check `releases/latest` (read-only, no token) -> compare `APP_VERSION` -> download only its own asset -> verify against the release `SHA256SUMS.txt` -> stage `<app>.new` -> swap via `camfrog-update.cmd` after exit. `tests/test_update.py` covers the flow; a fresh `--dry-run` of `tools/release.py` shows what a publish would upload.

## Change policy

1. Fix behavior in the combined source first when it is engine-level
   (`camfrog_auto.py`, `tools/web_status.py`), then port the fix into the split
   modules that inline it.
2. App-specific behavior (selectors, worker commands, queue handling, mode
   branches) is edited directly in the split module.
3. Never re-introduce an import between split modules to "share" a fix — copy
   the block instead. `tests/test_split_guis.py` fails the build if a split
   module imports a sibling.
