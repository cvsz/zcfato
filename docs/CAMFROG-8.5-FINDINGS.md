# Camfrog 8.5 UI findings / ผลวิเคราะห์ UI Camfrog 8.5

> **Correction (v2.12):** the static-analysis rows below that say RichEdit/Chromium for the *room* were wrong. A real room dump shows the log and input are embedded **IE/MSHTML** panes (see the last section). `libcef.dll` is used elsewhere in the app, not for the room log.

Source: static inspection of `Camfrog Video Chat.exe` 8.5.0.51219 (x64, Camfrog LLC), the **UI structure only**
(window classes, control kinds, resources). No network protocol, licensing or code-patching work was done.
**Not verified on a live Windows 11 session** — run `python camfrog_auto.py detect` once to confirm on your machine.

Related historical artifact: [static reverse-engineering notes for Camfrog Status 2009](CAMFROG-STATUS-2009-RE.md). That separate VB6 utility does not provide selectors or verified command IDs for Camfrog 8.5.

| Finding | Evidence in the binary | Consequence for this tool |
|---|---|---|
| Native Win32/WTL shell, custom skin, 64-bit | PE32+ GUI; imports COMCTL32, GDI+; only 3 stub `RT_DIALOG`s; controls are created from skin ids at runtime | Win32 control IDs are **not** static, so the old `auto_id 1002` default was a guess. Selectors are now class-based |
| Chat input = RichEdit | WTL `CRichEditTS`, window class `RICHEDIT50W` | `autoreply.input = {class_name: RICHEDIT50W}`; `write_text` falls back to `WM_SETTEXT` when UIA ValuePattern is missing |
| Custom status = combo box | `CComboBoxTS` / `CComboBoxHistoryTS`, skin ids `custom_status_combo`, `custom_status_text`, `menu_status_*` | `status.edit = {class_name: Edit}` (the combo's inner Edit); detect falls back to the ComboBox itself |
| Room log = embedded Chromium | imports `libcef.dll`; chat lines are HTML (`<a class='username'>`…); `camfrog://` scheme handler | The log is a UIA **Document** whose Name is the page title → new `read_chat()` reads its TextPattern (never `window_text()`) |
| Not elevated | manifest `asInvoker`, `uiAccess=false` | Run Python and Camfrog at the same (non-admin) level |
| Skin ids are not UIA ids | `mt_status_text`, `send_button`, … come from the skin | Don't rely on them as `auto_id`; check `controls.txt` |

## Verify on your PC (2 minutes)
1. Open Camfrog and **join a room** (stay visible, not in tray).
2. `python camfrog_auto.py detect` (or Room Control → Setup → *Auto-detect*). It prints the three selectors and writes `detect_report.txt`
   (structure only, no chat text). `python camfrog_auto.py detect --apply` writes them to the source CLI `config.json`.
3. Run `python camfrog_auto.py check`, then `python camfrog_auto.py status "test"` with `dry_run: true`, then `python camfrog_auto.py run`.

## Known risks
- If Chromium accessibility is off the Document may be empty → no replies are generated (it fails safe: nothing is sent).
- Lines must still look like `nick: message` (the tool ignores anything else).
- Camfrog updates can rename classes; re-run `detect`. Send `detect_report.txt` back to refine the heuristics.

## Verified on a real PC (buddy-list window, Windows 11)
- Main window = `#32770 "Camfrog Video Chat"` (316x659). **Custom status box = `Edit` id `1001` inside `CComboBoxTS` id `1436`.**
  Selector: `{"class_name":"Edit","auto_id":"1001","index":0}`. Buttons are `CButtonTS`; the contact/room list is `CTreeViewTS`.
- The chat room is **not** in this window: rooms open as separate windows of the same process. v2.11 scans every window of
  the Camfrog process and attaches to the room automatically (`autoreply.window_title_regex` narrows it, blank = auto).
- Still unverified: the room window's input/history classes (`RICHEDIT50W` / Chromium `Document` are from static analysis).
  Open a room and run `python camfrog_auto.py detect`, then send `detect_report.txt`.
- `controls.txt` / `detect_report.txt` no longer include contact or chat text (tree/list items are redacted).

## Verified on a real PC (chat-room window, "<Room>: Video Chat Room")
- Room = separate `#32770` window. **Log** = `AtlAxWinLic140` id `1002` (index 0) > Shell Embedding > Shell DocObject View >
  `Internet Explorer_Server` named `camfrog://wb-log-room-data.inside/`. **Input** = second `AtlAxWinLic140` id `1002` (index 1) >
  `Internet Explorer_Server` named `camfrog://wb-edit-data.inside/` > Pane id `edit` (a web editable box, no Edit/RichEdit control).
- Private-message windows have the same two panes but `wb-log-im-data`; `autoreply.log_kind: "room"` (default) refuses to attach to them.
- Older UIA captures expose `Image` (avatar), `Hyperlink` (nick), and `Text` (time/message), which `parse_web_log()` can read.
  A current private-message pane instead exposed only `Text` UIA nodes and no `Hyperlink`, so this UIA-only path returned no
  messages. The reader now gets the embedded MSHTML document with `WM_HTML_GETOBJECT` and extracts message rows from
  `span.msg-user` (`nickname-field`, `msg-time`, and `msgid`); it retains the older UIA parser as a fallback.
- Sending: no text control exists, so the tool brings the room to front, clicks the box, pastes (clipboard restored), presses Enter,
  and aborts if the room is not the foreground window at any step.
- Still unverified: whether UIA exposes element **names** for the web text (the dumps redact names). Run `python camfrog_auto.py chat-probe`:
  it prints the last parsed lines; lines marked `OK` are ones the bot could answer.

## Verified Live Windows 11 UI Runtime Integration (Camfrog 8.5.0.51219)

Verified on a live Windows 11 system with Python 3.14, psutil 7.2.2, pywinauto 0.6.9, and the genuine installed Camfrog 8.5 client:

1. **Process Discovery (`WindowsCamfrogProcessDiscovery`):**
   - Main client process: `Camfrog Video Chat.exe` (PID matched, creation time matched, PE `FileVersion` 8.5.0.51219).
   - Authenticode signature: verified valid with `WinVerifyTrust` (`wintrust.dll`), Signer Subject confirmed as `Camfrog LLC` via `CryptQueryObject` / `CertGetNameStringW` (`crypt32.dll`).
   - Exclusion: CEF helper subprocesses (`camfrog_cef.exe` with `--type=renderer`, `--type=gpu-process`, `--type=utility`) and ZChat's own automation processes (`os.getpid()`, GUI titles) are strictly filtered out.
   - Anti-targeting: fail-closed if multiple Camfrog processes exist and no explicit PID is provided.

2. **Structural Window Classification (`WindowsCamfrogWindowClassifier`):**
   - **IM history window:** identified by embedded `Internet Explorer_Server` pane `camfrog://wb-log-im-data.inside/` and native edit input (`CEditTS`/`Edit`), without `VideoViewport`.
   - **Room window:** identified by `VideoViewport` control and `Internet Explorer_Server` pane `camfrog://wb-log-room-data.inside/`.
   - **Main client / directory:** identified by `CTreeViewTS` (buddy list / contact directory) and `CComboBoxTS` (status selector, id 1436).
   - Ambiguous or unrecognized windows fail-closed to `UNKNOWN` role.

3. **Read-Only Attachment & Ownership Rules:**
   - Safe read-only attachment to an existing running client via `attach_to_camfrog_client()`.
   - Process and window identity revalidated before any interaction (`revalidate_process_identity`, `revalidate_window_identity`).
   - Strict ownership protection: client processes not launched by the agent are never terminated (`terminate_client_process` raises `PermissionError`).

4. **Evidence Boundary State Separation (`ClientRuntimeState`):**
   - `process_running`: verified executable, PID, creation timestamp, and valid `Camfrog LLC` signature.
   - `ui_visible`: confirmed visible top-level windows of the verified process.
   - `account_authenticated`: confirmed main directory window active with `CTreeViewTS` and status `CComboBoxTS`. Process running alone does not establish authentication.
   - `room_member`: room window presence alone does not establish membership. Live testing verified that a user kicked due to inactivity still has a visible room window, but `room_member` evaluates to `False`.
   - Privacy guarantee: no message bodies or sensitive credentials are collected or persisted during window discovery or diagnostic generation.

