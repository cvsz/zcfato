# Compatibility Matrix

| Component or behavior | Source/API evidence | Automated coverage | Runtime result |
|---|---|---|---|
| ZChat Client source | No source found in the supplied local package inventory | None | Blocked |
| Control-plane API | FastAPI routes and schemas in `control-server/` | API tests use SQLite; CI applies migrations to PostgreSQL | Code-level checks only; deployment remains open |
| Agent authentication and polling | `control-server/agent.py` and API tests | Unit/API tests | No long-running Windows service acceptance |
| Camfrog process and URI provider | `control-server/windows_client.py` | Mocked provider tests | Windows GUI/URI behavior not accepted |
| Profile/friend/presence projection | Sanitized snapshot schemas and providers | Projection/API tests | Live authenticated fetching is not configured |
| LINE hidden callback error handling | `line/line_status_gui.py` | Regression tests with mocked Tk on Linux/WSL and Windows | Packaged Windows hide-to-tray/Exit smoke passed; callback-error injection and audible-output acceptance remain unverified |

The matrix does not imply compatibility between a reconstructed ZChat Client and a chat server. No such contract is present.
