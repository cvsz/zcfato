# Behavior Mapping

| Requested behavior | Client evidence | Existing `control-server/` support | State |
|---|---|---|---|
| Client startup and navigation | No ZChat source or verified UI capture | A browser dashboard is served at `/dashboard` | Existing operator UI only; client behavior blocked |
| Sign-in and session lifecycle | No ZChat login source or approved login contract | Admin bootstrap-token exchange and scoped agent tokens | Control-plane authentication; not Camfrog or ZChat user login |
| Room chat and private messages | No source or runtime capture | No message send/receive or conversation routes | Blocked |
| Contacts and presence | No client behavior source | Sanitized friend/presence snapshots can be ingested and read; source fetching is not wired | Partial control-plane projection only |
| Launch, stop, restart | No reconstructed client | Optional provider controls only its own launched Camfrog child process | Implemented control operation with Windows runtime acceptance open |
| Join room, add friend, open IM | No reconstructed client | Official URI handoff is available; handoff is not proof of completed action | Implemented handoff only |
| Store, Cloud Bot, or premium actions | No client implementation evidence | Catalog/status projections and consent records exist; checkout and sensitive actions are disabled | Projection only; no action executor |
| Recovery and diagnostics | No client source | Agent retries transport failures and the server records control-plane audit events | Control-plane behavior only |

See [the server architecture evidence](../../control-server/docs/architecture.md) for state-separation and integration limits.
