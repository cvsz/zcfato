# Implementation Status

| Area | State | Evidence |
|---|---|---|
| User mapping `zchat-server = control-server` | Verified | User instruction and the checked-in `control-server/` project. |
| ZChat client source discovery | Blocked | The supplied local directory contained packaged Camfrog binaries and assets, with no inspected source-like files; it is not checked into the repository. |
| Existing server discovery | Verified | FastAPI control plane, same-origin dashboard, PostgreSQL persistence, scoped Windows agent, and documented routes. |
| Chat server/client protocol | Blocked | No message relay, chat transport, or chat-session API exists in the inspected control-server contract. |
| Existing account and agent workflows | Implemented in control-server | See [control-server/README.md](../control-server/README.md); this status does not imply live client integration. |
| Reconstructed ZChat Client UI or executable | Not implemented | No verified behavior or contract supports a faithful implementation. |
| Background-modal repair | Implemented | Hidden LINE GUI callback errors remain logged without opening a modal; visible-window behavior is retained. |
| Windows package and tray lifecycle | Verified | Native `line/build.bat` succeeded, the packaged executable passed the hide-to-tray/Exit smoke, and all 51 LINE tests passed on Windows. Callback-error injection and audible-output acceptance remain unverified. |
| Production readiness | Not established | The control server documents open Windows, deployment, scaling, backup, restore, and soak gates. |

This status distinguishes checked-in control-plane capabilities from client reconstruction, integration, Windows validation, deployment, and production readiness.
