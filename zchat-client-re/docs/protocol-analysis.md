# Protocol Analysis

## Verified protocol

The available protocol is the control-plane HTTP API under `/api/v1`, implemented by FastAPI. Admin routes use a short-lived dashboard JWT obtained from the bootstrap token. Agent routes use a one-time agent bearer token; commands use a lease-bound claim token. The polling reference agent uses HTTPS for remote origins, restricts plain HTTP to loopback, rejects redirects, does not persist its token, and applies jittered exponential backoff to transport failures.

## Not present in the inspected contract

The control API does not define chat message delivery, room membership events, private-message streams, client presence heartbeats, or a chat WebSocket/TCP framing protocol. A URI callback to the installed Camfrog client is not evidence of a chat protocol or a successful action.

No traffic was sent to Camfrog or any public service for this analysis. Do not infer wire behavior from filenames, HTML help, URI handoff, or the server's profile-projection helpers.

## Source references

- `control-server/src/camfrog_control_server/agent.py`: URL validation, HTTP transport, token prompt, polling, and retry loop.
- `control-server/src/camfrog_control_server/api.py`: admin and agent routes.
- `control-server/src/camfrog_control_server/windows_client.py`: opt-in process and official URI handoff.
- `control-server/docs/architecture.md`: evidence boundaries and unverified provider contracts.
