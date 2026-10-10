# Camfrog User Manual

Thai version: `USER-MANUAL-TH.md`.

Six apps, one manual.

Apps: `room-control`, `chat-im-private`, `status-random`, `status-marquee`, `im-autoreply`, `music-dj`, `web-status`. All are Windows-only and need Camfrog open, except `web-status` which works through the website.

**Updates.** Every app checks the project's GitHub release when it starts (a banner appears only when something newer exists) and each has a **Check for updates** button; the CLI equivalent is `<app> update`. An update downloads only that app's own file, verifies it against the release's `SHA256SUMS.txt`, and installs it the next time you close the app (`<app>.new` + `camfrog-update.cmd` do the swap). No account, no token, nothing is uploaded. Releases are published with `python tools/release.py`.

## 1. Install

1. Install 64-bit Python 3.12 or 3.13.
2. Run `doctor.bat` first. It checks your Python, flags bad setups, and tests the `pywin32` download.
3. Double-click `build.bat` (or `full-build.bat` for everything including the LINE app). Executables land in `dist\<app>\`.
4. If the build says `pywin32 ... no matching distribution`, your Python has no wheel: install 64-bit Python 3.13, delete `.venv`, rerun.

## 2. First run

1. Open Camfrog and join a room (not tray-minimized).
2. Open the app and use **Setup → Auto-detect** (room/im apps) or **Discover controls** (status/private-chat/web apps). This fills the control selectors automatically.
3. Keep `dry_run` ON while checking behavior. Dry-run only logs what *would* be sent.
4. Turn live mode on only when ready: **LIVE** checkbox / **Send statuses live to Camfrog** / **Send live**.

## 3. Room Control

- Set your nickname (`My nickname`) — required for live mode.
- **Window title regex** picks which Camfrog window to drive.
- Auto-reply rules: pattern (regex), reply text, per-sender cooldown, mention-only, language (`th`/`en`). Test offline with **Test rule** before going live.
- **Save & Start** runs the hidden background bot; **Stop** ends it. Closing the window does NOT stop the bot.
- Spam guard: links are ignored by default (`ignore_links`), plus `skip_patterns`.

## 4. IM Auto-reply

- Separate app, separate `config.json`, separate rules. Room auto-reply never touches private chats.
- **Mandatory friend allowlist** (`only_nicknames`): only listed nicknames are ever answered.
- Stricter limits by default (one reply per friend per hour, 3 per day, 10 per hour). Every reply starts with `[auto] `, and such lines are never answered.
- Windows already open when the bot starts are never answered.

## 5. Chat IM Private

- Lists private-chat windows already open in Camfrog. **Refresh** reloads, double-click or **Activate selected** focuses one. It never reads or sends messages.
- **Window title filter** (regex) + **Max windows** limit the list; **Save filters** stores them in this app's own config.
- **Discover controls** dumps the control tree to `controls.txt` for selector setup.

## 6. Status Random

- Ten message slots. The active status is picked from these entries.
- **Switch every** (seconds, minimum 0.3): how long each status stays before switching. Saved to `status.interval_seconds`.
- **Start** rotates immediately (first status goes out at once), **Stop** ends rotation. Pools live in `random-data\`, separate from Marquee.

## 7. Status Marquee

- Long statuses scroll across a window of `width` characters: **Step** (seconds per frame, min 0.5), **Stride** (clusters per frame), **Loop** (repeat without settling). With **Scroll** off (default), each pool line is applied whole, one per tick, rotating 1..N and wrapping.
- Every frame is a real status change on Camfrog, so keep frames slow and few. Start with dry-run.
- Thai-safe: never splits vowel/tone clusters, never emits a blank frame.

## 8. Status history, schedules, language

- Every status you set is saved to history; with `use_as_source` the next status is picked from it (`rotate`/`random`/`most_used`).
- `status.schedules` uses different pools by time of day; entries need `start`/`end` as `HH:MM`.
- `status.language_cycle: ["th","en"]` alternates Thai/English on each change. Status items can be `{th, en}` pairs.
- `"language": "auto"` follows the Windows UI language.

## 9. Music DJ

- A room bot that also plays music: it answers song requests from chat and announces what is playing. It needs Camfrog open and `autoreply` enabled (the DJ reuses the chat plumbing); set `dj.enabled`.
- Chat commands, prefix `!` by default: `!request <song>` (or `!req`, `!song`), `!queue`, `!current` (or `!np`), `!skip`, `!help`. The queue view in the app mirrors the file, with **Skip current** / **Clear queue** owner buttons.
- The first request starts playing immediately; each extra song is queued (`max_per_user` per person, duplicates and the currently playing song refused). `!skip` works for the requester or you (the bot owner).
- Music folder: use **Browse** to choose it; `!request` matches supported audio filenames (substring, case-insensitive). The app searches common audio extensions including WAV, MP3, WMA, AAC/M4A, AIFF/AU, FLAC, OGG/Opus, and MIDI.
- **Audio backend** `chat` (default) only announces in the chat. `local` additionally plays audio files that Windows MCI can open on this PC and starts the next song automatically when playback finishes — for the room to hear it, route this PC's output into Camfrog's input with a virtual cable or "Stereo Mix". Playback support depends on Windows MCI extension mappings and installed codecs. Set the sound output back to your speakers afterwards if you no longer want the room to hear it.
- Start with dry-run: the bot then only logs the announcements it would send. Requests still queue, and nothing is typed into the room.

## 10. Web Status (prototype)

Status: login flow mapped; the status-update endpoint was captured from a logged-in `profiles.camfrog.com/home.php` session (POST `{status, csrf}` to `/ajax/update_status.php`) and stays gated. CLI live sends need `--confirm-update`; GUI live Start asks for confirmation.

- No args opens the GUI; any args use the CLI (`web-status.exe --login Seaza --status "..."`). Dry-run is default — no network at all.
- In Setup, enter up to ten statuses in the numbered single-line fields. **Save to webtext.db** saves each slot beside the app; **Start** also saves the current values and rotates through non-empty slots every N seconds.
- Turn on **Marquee** to scroll each status one frame every 5 seconds, then move to the next populated slot. **Infinity Loop** is on by default; after the last populated slot it starts again at slot 1. Turn it off to stop after one pass. With Marquee off, the existing **Switch every** rotation remains in effect.
- **Activity Log** shows and appends fixed activity events to `web_status.log` beside the app. It does not record status text, passwords, or cookies.
- In **Account & Session**, press **Open login page**, sign in in your browser, then copy `PHPSESSID=...` from the `profiles.camfrog.com/home.php` request in DevTools and paste it into the session field. Press **Login** to verify the current cookie; a signed-in result arms automation. The cookie stays in memory only.
- With **Send live** enabled, **Start** verifies the current cookie if Login has not already armed the session, asks for confirmation, and begins rotation. **Stop** cancels the loop and disarms the session, so the next Start verifies again. Dry-run remains the default.
- CLI password login can be blocked by CAPTCHA; the tool does not bypass it. For CLI use, `--probe` is read-only and `--cookies-file` accepts a Netscape cookie export. Never paste passwords or cookie values into chat, issues, or files.

## 11. Background mode, logs, files

- Room/IM: GUI **Save & Start** / **Stop**, or CLI `start` / `state` / `stop` (hidden, no window). Status apps: own **Start**/**Stop** + bundled worker.
- Each app writes logs beside its own config (`camfrog_auto.log` for source CLI). Hot reload: editing `config.json` while running applies valid changes in ~3 s; invalid edits are rejected and logged.
- Safety: every send briefly focuses Camfrog, presses Enter, then restores your previous window. Camfrog must be open (minimized is OK only if controls are still reachable — verify with Discover).

## 12. Troubleshooting

| Symptom | Fix |
|---|---|
| `pywin32 ... no matching distribution` | 64-bit Python 3.13, delete `.venv`, rerun `build.bat`. |
| Auto-detect finds nothing | Open a chat room (not tray-minimized) and retry; then Discover controls. |
| Old `requirements.txt (line 1)` pywinauto-only error | You run an older copy — extract the newest zip into a new empty folder. |
| Status never sends (status apps) | Enable **Send statuses live to Camfrog**; dry-run is default. |
| Error sound on every status change | Try **combo Enter (test)**; verify with Apply Now before marquee use. |
| Wrong/old window driven | Fix **Window title regex**, re-run Auto-detect. |
| Explorer shows old icon after rebuild | Windows icon cache: rename/move the exe or restart Explorer. |

## 13. Safety

- `dry_run` is on by default; replies are rate-limited (per-sender cooldown, global gap, hourly cap).
- Lines not in `name: message` form are ignored; replies starting with `/` are blocked; there is no auto-kick.
- Never commit passwords, cookies, tokens, or personal data. Cookie exports stay outside the repo.
- Check Camfrog's terms and your room's rules before enabling automation. Report vulnerabilities privately per `SECURITY.md`, never in public issues.
