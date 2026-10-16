# Client and Server Contract

## Existing control-plane contract

The user-approved server mapping points to `control-server/`. The current documented API uses these principal boundaries:

| Principal | Authentication | Supported operations |
|---|---|---|
| Operator dashboard | Bootstrap bearer token exchanged for a short-lived admin JWT | Manage agents and accounts, assign accounts, queue and inspect commands, read audit and sanitized snapshots |
| Windows agent | Scoped one-time bearer token | Heartbeat, claim a leased command, report its result, submit sanitized account snapshots |
| Official Camfrog client | Local Windows process/URI handler | Optional launch/stop/restart and `join_room`, `add`, or `im` URI handoff |

The server does not expose a ZChat conversation protocol. This document therefore records the existing control-plane contract only; it is not a client chat API specification.

## Compatibility and security rules

- Do not send Camfrog passwords, browser cookies, CSRF values, CAPTCHA answers, payment credentials, or room keys through a reconstructed client.
- Keep admin and agent credentials separate and preserve their existing scopes.
- Treat URI success as operating-system handoff only.
- Do not add chat routes or transport until an approved service contract and server implementation exist.

For exact routes and deployment limits, see [control-server/README.md](../../control-server/README.md).
