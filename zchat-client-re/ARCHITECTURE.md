# Architecture and Verified Boundaries

## Reconstructed client

No ZChat Client architecture can be verified from the available source. This repository does not contain a ZChat desktop or web client source tree, dependency manifest, client test suite, or client build configuration. Accordingly, this document does not propose or claim an implemented client architecture.

## Existing control-plane architecture

The verified system is an operator dashboard and agent control plane:

```text
Operator browser
      │ same-origin dashboard and admin API
      ▼
FastAPI control plane ─── PostgreSQL
      ▲                       │
      │ scoped agent token    │ account, command, and audit state
      └── Windows agent ──────┘
                │
                └── optional official Camfrog process or URI handoff
```

The server's static dashboard is served by `control-server/src/camfrog_control_server/app.py`. The API is split across `api.py` and `domain_api.py`; persistence is provided by the SQLAlchemy models and Alembic migrations. The Windows agent polls the control API and optionally delegates a small allowlist of actions to an installed official Camfrog client.

## Boundary

The control plane supports operator-managed accounts, agent lifecycle, leased commands, sanitized snapshots, and audit data. It does not relay chat messages or implement a chat-session protocol. A room URI being accepted by Windows does not prove that Camfrog joined the room. The current architecture and its operational limits are described in [control-server/docs/architecture.md](../control-server/docs/architecture.md).
