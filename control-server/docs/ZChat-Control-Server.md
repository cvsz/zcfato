\# ZChat Control Server — Deep Audit, Refactoring \& Real Runtime Integration



\## ROLE



Act as a Principal Software Architect, Senior Full-Stack Engineer, Windows Runtime Engineer, Security Auditor, QA Automation Engineer, and Production Reliability Engineer.



Your target is the entire ZChat Control Server repository, including its Camfrog provider integration, FastAPI backend, dashboard, PostgreSQL persistence, Windows agent, command processing, configuration, packaging, security, and operational workflows.



\*\*Primary objective:\*\* Establish a fully functional, verifiable, secure, maintainable system using real implementation and runtime evidence, not simulated success.



\## MANDATORY OPERATING RULES



1\. Inspect the existing repository before changing it.

2\. Preserve working functionality and backward-compatible contracts unless a documented migration is required.

3\. Investigate root causes instead of applying superficial workarounds.

4\. Never fabricate completed actions, tests, deployment results, runtime captures, or integration evidence.

5\. Separate implementation status from verification status.

6\. Use official, authorized integration mechanisms.

7\. Never bypass CAPTCHA, authentication, access control, account restrictions, or third-party platform protections.

8\. Never invent Camfrog API endpoints or undocumented request/response behavior.

9\. No destructive database operations or production deployment without explicit authorization.

10\. Keep Windows background operation silent without suppressing security warnings, error logs, or operational alerts.



\## PHASE 1 — FULL REPOSITORY INVENTORY



Inspect all relevant first-party source files and configurations.



Identify:



\- Entrypoints, services, modules, dependencies, and runtime execution paths

\- API routes, schemas, authentication, authorization, and middleware

\- Windows agent lifecycle and Camfrog provider adapters

\- Command queue, leases, retries, acknowledgements, and idempotency

\- Database migrations, models, constraints, indexes, and retention

\- Dashboard state management, polling, error handling, and API integration

\- Tests, CI/CD, secrets, deployment configuration, and observability



Produce:



\- Architecture dependency map

\- System component inventory

\- Critical data-flow diagrams

\- Endpoint and command inventory

\- Verified-versus-unverified implementation matrix

\- Prioritized P0/P1/P2 findings



\## PHASE 2 — EVIDENCE-BOUNDARY AUDIT



Enforce independent state models:



\- AgentRuntimeState

\- AccountProcessState

\- AccountAuthenticationState

\- RoomMembershipState

\- HumanPresenceState

\- CloudBotState

\- CommandExecutionState



Each runtime observation must have an explicit source, timestamp, freshness policy, and verification status.



Unknown must remain UNKNOWN until authoritative evidence exists.



A successful HTTP response, process launch, Windows URI handoff, DOM selector match, or accepted command must never be reported as proof of completed Camfrog behavior unless independently verified.



Document whether each statement is:



\- VERIFIED\_RUNTIME

\- VERIFIED\_SOURCE

\- IMPLEMENTED\_UNVERIFIED

\- INFERRED

\- UNKNOWN

\- BLOCKED



\## PHASE 3 — SECURITY AND CONTROL-PLANE HARDENING



Audit and repair:



\- Admin bootstrap and JWT lifecycle

\- RBAC and resource-level authorization

\- Account-to-agent binding

\- Agent token rotation and revocation

\- Command claim-token validation

\- Lease fencing and replay resistance

\- Command idempotency and reconciliation

\- Input validation and output encoding

\- CORS, CSRF applicability, and browser security headers

\- Shared rate limiting

\- Audit trail integrity

\- Logging redaction

\- Encryption, secret management, and database access

\- Retention and deletion policies



Do not store Camfrog passwords, cookies, CSRF token values, CAPTCHA answers, payment credentials, or unauthorized session material.



Add negative tests for cross-account and cross-tenant access.



\## PHASE 4 — WINDOWS AGENT RUNTIME REPAIR



Audit and implement a reliable Windows background agent.



Requirements:



\- Explicit opt-in before Camfrog provider launch

\- Verify executable path and process ownership

\- Track PID plus creation time and executable identity

\- Never terminate unrelated Camfrog processes

\- Detect ambiguous process/window matches and fail safely

\- Support startup, restart, graceful shutdown, and crash recovery

\- Report verified process state independently of account login or room membership

\- Handle interactive Windows sessions correctly

\- Avoid session-zero GUI automation assumptions

\- Prevent duplicate agent instances where applicable

\- Ensure background operation does not produce unnecessary Windows notification sounds

\- Do not disable Windows Defender, security alerts, global system audio, or unrelated application notifications

\- Preserve structured operational logs and visible failure reporting



Implement real Windows integration tests where an authorized interactive test environment is available.



\## PHASE 5 — CAMFROG PROVIDER INTEGRATION



Inventory observed provider capabilities:



\- Official client launch and shutdown

\- Official URI dispatch

\- Account authentication observations

\- Profile and friend-list projections

\- Human presence observations

\- Room state verification

\- Cloud Bot status observations

\- Account settings and premium features



For every capability:



1\. Identify the authoritative evidence source.

2\. Document the exact observed request/response contract when available.

3\. Create sanitized contract fixtures.

4\. Implement adapters only where the integration is authorized and validated.

5\. Keep unsupported actions disabled.

6\. Validate success through actual provider-side observations.

7\. Report inconclusive outcomes as UNKNOWN, not SUCCESS.



Do not infer undocumented protocol behavior from frontend source alone.



\## PHASE 6 — COMMAND EXECUTION RELIABILITY



Introduce durable command lifecycle handling:



PENDING → CLAIMED → EXECUTING → SUCCEEDED / FAILED / UNKNOWN / RECONCILIATION\_REQUIRED



Requirements:



\- Persistent command ID

\- Server-side idempotency key

\- Lease expiry

\- Monotonic fencing generation

\- Bounded retries with backoff

\- Agent crash recovery

\- Stale-worker rejection

\- Duplicate-effect prevention where supported

\- Operator reconciliation for indeterminate external effects

\- Append-only audit history



Never automatically retry potentially non-idempotent external actions when their outcome is unknown.



\## PHASE 7 — DATABASE AND DASHBOARD



Validate:



\- PostgreSQL migrations and rollback compatibility

\- Foreign keys, unique constraints, and transaction boundaries

\- Atomic agent reassignment and token rotation

\- Data minimization and retention

\- Backup and restore

\- Consistent dashboard error states

\- Polling freshness indicators

\- Operator-visible UNKNOWN and BLOCKED states

\- Accurate audit timelines



Do not display synthetic or stale account state as verified live activity.



\## PHASE 8 — AUTOMATED VERIFICATION



Build and run the available tests:



\- Unit tests

\- API integration tests

\- Database integration tests

\- Security regression tests

\- Command concurrency tests

\- Lease expiration and replay tests

\- Windows process lifecycle tests

\- Camfrog provider contract tests

\- Dashboard E2E tests

\- Packaging and installation tests

\- Backup/restore tests



Use mocks and fixtures only for deterministic tests. Clearly distinguish mocked test results from real Windows/Camfrog acceptance evidence.



If the necessary runtime, credentials, or permissions are unavailable, mark the applicable acceptance test BLOCKED. Never fabricate a pass.



\## PHASE 9 — DEPLOYMENT AND PRODUCTION GATES



Verify:



\- Environment validation

\- Secret injection and rotation

\- Shared rate limiting

\- PostgreSQL readiness

\- Least-privilege service configuration

\- Windows startup and recovery

\- Health and readiness checks

\- Metrics and structured logs

\- Backup/restore drill

\- Rollback procedure

\- Resource and load testing

\- Windows long-running stability

\- Authorized Camfrog live integration acceptance



No production-ready claim is permitted until all mandatory gates have verified evidence.



\## PHASE 10 — DELIVERY



Provide:



1\. Executive summary

2\. Architecture and dependency findings

3\. P0/P1/P2 security and reliability issues

4\. Root cause and implemented changes

5\. Changed file list and commit references

6\. Verification commands and actual results

7\. Windows runtime acceptance evidence

8\. Camfrog integration evidence matrix

9\. Remaining blockers and risks

10\. Production readiness verdict



Use these final classifications:



\- VERIFIED

\- IMPLEMENTED\_NOT\_VERIFIED

\- BLOCKED

\- NOT\_IMPLEMENTED

\- NOT\_APPLICABLE



Final rule:



\*\*Never confuse source discovery, successful code execution, command dispatch, or simulated tests with a verified external provider outcome.\*\*



Proceed autonomously with repository inspection, safe implementation, tests, and evidence collection within the available environment. Stop at authorization or production-impact boundaries requiring explicit operator approval.

