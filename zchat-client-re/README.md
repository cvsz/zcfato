# ZChat Client Reconstruction

## Status

**Blocked: no verifiable ZChat Client source or chat-server contract is present in the repository.** The supplied local `zchat-client/` directory was inventoried but is untracked and is not part of this reconstruction. It contained 99 files (273,396,077 bytes): a packaged Camfrog Video Chat executable, supporting binaries, and help, language, and runtime assets. No source-like files were found in the inspected language extensions.

The user-approved mapping `zchat-server = control-server` is recorded here. The mapped project is a ZChat **control plane** for operator-managed accounts and Windows agents. It is not a chat message server. Its current API does not provide message delivery, room conversations, or a chat WebSocket.

No client executable, UI, login flow, or undocumented protocol has been invented. The existing operator dashboard already lives in `control-server/`; creating a second dashboard would duplicate working functionality without satisfying the missing chat-client contract.

## Documents

- [Architecture and verified boundaries](ARCHITECTURE.md)
- [Reverse engineering report](REVERSE_ENGINEERING_REPORT.md)
- [Implementation status](IMPLEMENTATION_STATUS.md)
- [Behavior mapping](docs/behavior-mapping.md)
- [Protocol analysis](docs/protocol-analysis.md)
- [Control-plane API contract](docs/client-server-contract.md)
- [Compatibility matrix](docs/compatibility-matrix.md)
- [Verification evidence](docs/verification-evidence.md)

The authoritative server implementation and its evidence limits are documented in [control-server/README.md](../control-server/README.md) and [control-server/docs/architecture.md](../control-server/docs/architecture.md).

## What is needed to continue

Provide authorized ZChat Client source or a documented, supported client interface and an approved chat-service contract. Binary-only Camfrog installation files do not establish ZChat application behavior, proprietary network protocol semantics, or permission to reproduce them. Any future work must keep authentication, licensing, CAPTCHA, and service access controls intact.
