# Background Runtime and Silent Behavior Audit

## Scope

This audit covers the tracked Windows application entry points, worker launch paths, notification and sound APIs, the LINE Status Changer scheduler, and the ZChat Control Server agent. The source baseline is `b51b8d3821bb5524da1ea6a4f9135bdf72a1a151`. A local untracked `zchat-client/` directory was inventoried separately and was not modified or included in this change.

## Findings

| Status | Location | Finding | Action |
|---|---|---|---|
| Fixed | `line/line_status_gui.py`, `LineStatusChanger.report_callback_exception` | An unhandled Tk callback exception was logged and then always shown in a modal dialog. The LINE app continues running scheduled callbacks while hidden in the tray, so a background callback failure could interrupt the user. | Keep the error in the file log; suppress the dialog while the window is minimized or withdrawn. Retain the dialog while the window is visible. Regression tests cover both states. |
| Verified, inactive path | `line/line_tray.py`, `LineTrayIcon.notify` | The helper can request a Windows tray balloon, but a repository-wide call search found no caller. It is not an active notification path. | No settings or behavior change made for dead code. Any future caller must add an explicit notification policy. |
| Verified, intentional media | `dj_play` in the Camfrog DJ applications | `winsound.PlaySound` plays a selected local WAV as DJ media. It is not an error alert or desktop notification. | Preserve this user-requested media behavior. |
| Partial | `control-server/src/camfrog_control_server/agent.py`, `main` | The polling agent requests its scoped token through an interactive, non-echoing prompt and prints sanitized transport errors. It is documented as a foreground terminal process, not a Windows service. | Keep the authentication prompt visible. Non-interactive service installation and Windows secret-store integration remain unsupported. |
| Verified | Windows GUI worker launchers | Several GUI applications start their background worker processes with `CREATE_NO_WINDOW`, redirect worker standard streams, and keep worker state in logs or status files. GUI builds use windowed packaging; the explicit Camfrog Auto CLI retains a console entry point. | No broad process-launch rewrite was justified by this audit. |

The repository-wide source search found no direct `winsound.Beep`, `MessageBeep`, Windows toast package, Qt notification sound, or console bell implementation. Windows notification-area icon registration exists in several applications; registering an icon is distinct from sending a balloon notification.

## Implementation detail

`LineStatusChanger.report_callback_exception` now checks Tk's window state before opening a dialog. States `iconic` and `withdrawn` are treated as background execution. The exception is logged before this check, and the status label is updated so the failure is visible when the user restores the window. If Tk cannot report its state or show the dialog, a debug record is written and the callback handler does not raise another UI exception.

The change is scoped to the confirmed background-modal path. A shared `APP_*` configuration was not added because the audited applications have no active desktop notification caller to wire into such a setting; adding unused environment switches would not suppress an existing behavior. It does not mute Windows, alter system notification settings, or change selected WAV playback.

## Evidence and remaining gates

- `line/tests/test_core.py`: 51 unit tests passed on Linux/WSL and 51 passed on native Windows. Callback-error tests mock Tk state and dialogs; tray retry tests assert captured warning records.
- `make ci` on the candidate code: repository validation passed; formatting and lint passed; root tests reported 710 passed and 3 skipped; control-server tests reported 40 passed; both dependency audits reported no known vulnerabilities (the editable control-server distribution is excluded from the installed-package audit).
- Static inspection found no active caller of `LineTrayIcon.notify`.
- `line/build.bat` completed successfully in a native Windows worktree and produced `line-status-changer.exe`.
- `line/tools/smoke_line_x.py` passed against the packaged executable: title-bar X hid the window to the tray, and tray Exit closed the process cleanly.
- The Windows smoke did not inject a callback failure or capture audio; audible-output acceptance remains unverified.
- The control server explicitly documents that its Windows process/URI behavior lacks Windows runtime acceptance and that the service is not production-ready. See [control-server/README.md](../control-server/README.md).
- The requested client reconstruction remains blocked by the absence of client source and a chat-server contract. See [the reconstruction status](../zchat-client-re/IMPLEMENTATION_STATUS.md).

No production-readiness or deployment claim is made by this audit.
