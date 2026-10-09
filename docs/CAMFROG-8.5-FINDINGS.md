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
- Log items in UIA: `Image` (avatar), `Hyperlink` (nick, with a `Text` child), `Text` (time), `Text` (message). `parse_web_log()`
  turns them into `nick: message`; join/leave notices (no Hyperlink) are ignored.
- Sending: no text control exists, so the tool brings the room to front, clicks the box, pastes (clipboard restored), presses Enter,
  and aborts if the room is not the foreground window at any step.
- Still unverified: whether UIA exposes element **names** for the web text (the dumps redact names). Run `python camfrog_auto.py chat-probe`:
  it prints the last parsed lines; lines marked `OK` are ones the bot could answer.
