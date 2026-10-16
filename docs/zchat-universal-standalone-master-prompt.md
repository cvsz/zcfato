# ตรวจสอบเอกสาร Architecture

**User:** Anonymous  
**Created:** 10/16/2026 22:02:25  
**Updated:** 10/17/2026 3:52:40  
**Exported:** 10/17/2026 4:43:17  
**Link:** [https://chatgpt.com/c/6ad23c80-de50-83ec-8af2-165f9a7d6a00](https://chatgpt.com/c/6ad23c80-de50-83ec-8af2-165f9a7d6a00)  

## Prompt:
10/16/2026, 10:02:34 PM

check prompt " # ZChat Control Server: Architecture and Evidence Boundaries

ZChat Control Server keeps Camfrog-specific behavior behind its provider integration. This document records the current implementation against the supplied browser and source observations. Research summaries are not substitutes for source artifacts or sanitized runtime captures. The implementation keeps these evidence levels separate.

## State separation

`Agent.runtime_state` describes only the polling agent process (`unknown`, `starting`, `running`, `error`, or `disconnected`). It does not mean a Camfrog account is logged in, online, in a room, or that a Cloud Bot is running.

`AccountRuntimeSnapshot.process_state` is account-scoped and reported by the agent. The current Windows adapter can report only the specific process handle it launched; it cannot discover pre-existing Camfrog processes. Reports older than 30 seconds are returned as `unknown`. `room_state` stays `unknown` until a verified live room-status source is available; accepting a deep link does not establish room membership.

The account auth-state detector uses the observed `.nav-user-logged` marker and `external_data.type` values `profile`/`settings`; `public` is kept separate. A CSRF field is reduced to a boolean-presence observation. The server never receives its value. Profile, friends, auth, and human presence are stored as separate snapshots. Public image-based presence remains `UNKNOWN` until it is calibrated against controlled account states, and stale presence becomes `UNKNOWN` after ten minutes.

## Report findings and implementation status

| Report finding | Evidence limit | Current treatment |
|---|---|---|
| Login selectors and authenticated-state marker | UI trace confirms selectors; the added login drill confirms `.nav-user-logged` plus `external_data.type`; login POST fields and redirect chain remain unknown | Bootstrap admin uses a short-lived dashboard JWT. Agent snapshots store only derived auth state, page type, and CSRF-presence boolean; no Camfrog login API or session storage |
| Profile and friend AJAX endpoint inventory | Source confirms `/ajax/get_friend_list.php`, `/ajax/get_recently_added_list.php`, and other profile endpoints; uploaded HARs still do not contain these runtime calls | Allowlisted `external_data` projection, friend-entry normalization, and snapshot APIs exist. No authenticated fetcher is wired |
| Human presence strings | Structured `online`, `away`, `busy`, and `offline` are known; public image semantics are uncalibrated | Snapshot APIs expose normalized state. HTTP 200 or status-image presence never implies ONLINE |
| Store purchase handler and CSRF field | Frontend source maps the request shape; no captured runtime response validates the server envelope | Operator-imported catalog and consent-only purchase intents exist. There is no checkout or purchase executor |
| Cloud Bot RPC helper and visible state strings | Client source describes request/poll behavior; a real `/bot/ajax/` response is still required | Request/response projection, status mapping, registry, and snapshots exist. Live authenticated transport is not configured |
| Official Camfrog URI patterns | URI strings were observed; Windows runtime behavior has not passed acceptance | Opt-in provider launches/stops only the process it created and dispatches official room/add-friend/IM URIs. It does not prove Camfrog completed the action |
| Gold/premium nickname settings UI | Exact request, eligibility, timing, and price response remain unvalidated | Subscription baseline and temporary overlays are modeled. No nickname-change command exists |

The captured HARs documented by the reports were dominated by third-party traffic and did not validate Camfrog login, profile AJAX, Store purchase, or Cloud Bot runtime contracts. Do not treat source-level endpoint discovery as a successful live integration.

## Control-plane slice

```text
Same-origin operator dashboard
        │ bootstrap token → short-lived JWT
        ▼
FastAPI control plane ─── PostgreSQL
        ▲                    │
        │ scoped agent token │ account / command / chat / audit state
        └── Windows agent ───┘
                 │
                 └── optional official client process/URI provider
```

An agent token is rotated and bound to the current account assignment; reassignment invalidates the previous and replacement agents' prior tokens. An administrator can rotate an active token without changing its assignment; the replacement is returned once. The database stores account nicknames and internal assignments, plus plaintext internal chat bodies. It does not store login passwords, browser profiles, cookies, CSRF values, CAPTCHA answers, payment credentials, or room access keys. Auth-state snapshots contain only a derived state, page type, and whether a CSRF field was present. Agent and command claim tokens are returned once and stored as hashes; claim tokens are single-use and bounded by a lease. Chat-body retention, backup access, and deletion policy remain deployment gates.

The API rate limiter is bounded and per process. It is suitable for local/single-instance development only; it does not coordinate across multiple workers or replicas. Structured request logs include only method, path, status, request id, and duration. Query strings, headers, and bodies are omitted.

Commands are delivered at least once if a lease expires. A provider action may have completed just before an agent lost its lease, so providers must define idempotency and operator reconciliation. Windows URI success means the operating system accepted the handoff, not that the client completed it.

## Current implementation and remaining gates

1. **Control API and dashboard:** core account/agent/command/audit routes, health, JWT sessions, in-process rate limiting, and operator views are implemented.
2. **Windows agent:** launch/stop/restart of an agent-owned process and official URI dispatch are implemented behind an opt-in provider. Account runtime heartbeats report process state, while room state remains unknown. Windows GUI/runtime/session isolation still needs acceptance.
3. **Profile/friends/presence projection:** allowlisted data projection, friend normalization, snapshot ingestion, and stale-aware presence reads are implemented. Live authenticated fetching and status updates remain disabled pending an authorized local browser provider and request/response validation.
4. **Cloud Bot:** status mapping, request construction, response projection, and snapshots are implemented. Authenticated transport and action routes remain disabled until a real runtime envelope is captured.
5. **Store and premium account actions:** operator-imported catalog and consent-only purchase intents exist. No checkout, purchase, nickname change, or security mutation is executed.
6. **Production gates:** exact login network contract, Windows/VM isolation, runtime captures, shared rate limiting, PostgreSQL deployment, backup/restore, secret rotation, and soak evidence remain open.
 "

## Response:
10/16/2026, 10:02:43 PM · gpt-6-thinking

## Review: ZChat Control Server - Architecture and Evidence Boundaries

**ผลการตรวจสอบ\:** เอกสารนี้มีโครงสร้างที่ดีสำหรับการกำหนด Architecture, Security Boundaries และ Evidence-Based Development แต่ยังไม่ใช่ **Execution Prompt** ที่เพียงพอให้ AI Agent ตรวจสอบ แก้ไข และทำระบบ ZChat ให้ทำงานได้จริงแบบ End-to-End

การประเมินนี้เป็น **Document Review** จากข้อความที่ให้มา ยังไม่ได้ตรวจ Source Code, Runtime Logs หรือ Repository จริง ดังนั้นคำว่า `implemented` ในเอกสารยังถือเป็นสถานะที่ต้องพิสูจน์

**Architecture / Evidence Design** (Strong Foundation)

**Security &amp; Reliability** (Needs Hardening)

**Real Camfrog Integration** (Unverified)

**Production Readiness** (Not Established)

## 1\. Critical Findings

| Priority | Finding | Required Action |
|--------|--------|--------|
| P0 | Bootstrap admin authentication ไม่ระบุ Replay Protection, Token Revocation และ Session Lifecycle ครบถ้วน | ตรวจ JWT validation, admin bootstrap, revocation และ RBAC |
| P0 | Agent อาจรายงาน Process State โดยไม่ผูกกับ OS Process Identity | ตรวจ PID, process creation time, executable path และ ownership |
| P0 | Command แบบ at-least-once อาจทำให้เกิด Duplicate Side Effects | เพิ่ม Idempotency Key, Fencing Token และ Reconciliation |
| P0 | ยังไม่มี Verified Camfrog Login/Session Integration | ตรวจสอบ Authorized Runtime Captures และทำ Contract Tests |
| P1 | Per-process Rate Limiter ไม่รองรับ Multi-instance | ใช้ Shared Rate Limiting เช่น Redis |
| P1 | Agent Snapshot อาจเป็น Stale หรือถูกปลอมแปลง | ใช้ Schema Validation, Timestamp, Sequence Number และ Token Scope |
| P1 | Windows GUI Isolation ยังไม่ผ่าน Acceptance | ทดสอบ Interactive Session, Multiple Processes, Restart และ Crash Recovery |
| P1 | Chat Bodies เป็น Plaintext | กำหนด Encryption at Rest, Retention, Redaction และ Access Control |
| P1 | ไม่มี End-to-End Test Evidence | เพิ่ม Windows Integration Tests, Contract Tests และ Soak Tests |

### ข้อขัดแย้งที่ต้องแก้ในเอกสาร

**1\. `Agent.runtime_state` กับ `AccountRuntimeSnapshot.process_state`**

ควรระบุอย่างชัดเจนว่าเป็นสอง State Machine ที่แยกจากกัน และต้องมี `observed_at`, `expires_at`, `source` และ `confidence` หรือ verification status ประกอบ

**2\. Process ownership**

การติดตามเฉพาะ process ที่ Agent เปิดเองเป็นข้อจำกัดที่เหมาะสม แต่การใช้ PID อย่างเดียวไม่เพียงพอ เพราะ Windows สามารถนำ PID กลับมาใช้ใหม่ได้

ควรตรวจ Process Identity และหลีกเลี่ยงการปิด process ที่ไม่ได้เป็นเจ้าของ

**3\. Command acknowledgement**

`at-least-once` ไม่รับประกันว่า provider action จะเกิดเพียงครั้งเดียว การมี Claim Token แบบ single-use เพียงอย่างเดียวไม่ป้องกัน Duplicate Effect หลัง Lease Expiration

**4\. Authentication state**

`.nav-user-logged` เป็น UI Observation ไม่ใช่ Cryptographic Proof ว่าผู้ใช้ผ่าน Authentication แล้ว ควรจัดเป็น `observed_authenticated` และไม่ยกระดับเป็น `verified_authenticated` โดยไม่มีหลักฐานที่เชื่อถือได้เพิ่มเติม

**5\. Production readiness**

การมี API, Dashboard และ Windows Agent Implementation ไม่เท่ากับระบบพร้อมใช้งาน ต้องทดสอบบน Windows Runtime จริง รวมถึงกรณีที่ Camfrog เปิดอยู่ก่อนแล้วหรือมีหลาย instance

---

## 2\. Recommended Master Execution Prompt

ด้านล่างเป็น Prompt สำหรับนำไปใช้กับ Codex, Claude Code, Kilo CLI หรือ AI Engineering Agent เพื่อเปลี่ยน Architecture Document ให้เป็นงานตรวจสอบและพัฒนาที่วัดผลได้

**document: **

# ZChat Control Server - Deep Audit, Refactoring & Real Runtime Integration

## ROLE

Act as a Principal Software Architect, Senior Full-Stack Engineer, Windows Runtime Engineer, Security Auditor, QA Automation Engineer, and Production Reliability Engineer.

Your target is the entire ZChat Control Server repository, including its Camfrog provider integration, FastAPI backend, dashboard, PostgreSQL persistence, Windows agent, command processing, configuration, packaging, security, and operational workflows.

**Primary objective:** Establish a fully functional, verifiable, secure, maintainable system using real implementation and runtime evidence, not simulated success.

## MANDATORY OPERATING RULES

1. Inspect the existing repository before changing it.
2. Preserve working functionality and backward-compatible contracts unless a documented migration is required.
3. Investigate root causes instead of applying superficial workarounds.
4. Never fabricate completed actions, tests, deployment results, runtime captures, or integration evidence.
5. Separate implementation status from verification status.
6. Use official, authorized integration mechanisms.
7. Never bypass CAPTCHA, authentication, access control, account restrictions, or third-party platform protections.
8. Never invent Camfrog API endpoints or undocumented request/response behavior.
9. No destructive database operations or production deployment without explicit authorization.
10. Keep Windows background operation silent without suppressing security warnings, error logs, or operational alerts.

## PHASE 1 - FULL REPOSITORY INVENTORY

Inspect all relevant first-party source files and configurations.

Identify:

- Entrypoints, services, modules, dependencies, and runtime execution paths
- API routes, schemas, authentication, authorization, and middleware
- Windows agent lifecycle and Camfrog provider adapters
- Command queue, leases, retries, acknowledgements, and idempotency
- Database migrations, models, constraints, indexes, and retention
- Dashboard state management, polling, error handling, and API integration
- Tests, CI/CD, secrets, deployment configuration, and observability

Produce:

- Architecture dependency map
- System component inventory
- Critical data-flow diagrams
- Endpoint and command inventory
- Verified-versus-unverified implementation matrix
- Prioritized P0/P1/P2 findings

## PHASE 2 - EVIDENCE-BOUNDARY AUDIT

Enforce independent state models:

- AgentRuntimeState
- AccountProcessState
- AccountAuthenticationState
- RoomMembershipState
- HumanPresenceState
- CloudBotState
- CommandExecutionState

Each runtime observation must have an explicit source, timestamp, freshness policy, and verification status.

Unknown must remain UNKNOWN until authoritative evidence exists.

A successful HTTP response, process launch, Windows URI handoff, DOM selector match, or accepted command must never be reported as proof of completed Camfrog behavior unless independently verified.

Document whether each statement is:

- VERIFIED_RUNTIME
- VERIFIED_SOURCE
- IMPLEMENTED_UNVERIFIED
- INFERRED
- UNKNOWN
- BLOCKED

## PHASE 3 - SECURITY AND CONTROL-PLANE HARDENING

Audit and repair:

- Admin bootstrap and JWT lifecycle
- RBAC and resource-level authorization
- Account-to-agent binding
- Agent token rotation and revocation
- Command claim-token validation
- Lease fencing and replay resistance
- Command idempotency and reconciliation
- Input validation and output encoding
- CORS, CSRF applicability, and browser security headers
- Shared rate limiting
- Audit trail integrity
- Logging redaction
- Encryption, secret management, and database access
- Retention and deletion policies

Do not store Camfrog passwords, cookies, CSRF token values, CAPTCHA answers, payment credentials, or unauthorized session material.

Add negative tests for cross-account and cross-tenant access.

## PHASE 4 - WINDOWS AGENT RUNTIME REPAIR

Audit and implement a reliable Windows background agent.

Requirements:

- Explicit opt-in before Camfrog provider launch
- Verify executable path and process ownership
- Track PID plus creation time and executable identity
- Never terminate unrelated Camfrog processes
- Detect ambiguous process/window matches and fail safely
- Support startup, restart, graceful shutdown, and crash recovery
- Report verified process state independently of account login or room membership
- Handle interactive Windows sessions correctly
- Avoid session-zero GUI automation assumptions
- Prevent duplicate agent instances where applicable
- Ensure background operation does not produce unnecessary Windows notification sounds
- Do not disable Windows Defender, security alerts, global system audio, or unrelated application notifications
- Preserve structured operational logs and visible failure reporting

Implement real Windows integration tests where an authorized interactive test environment is available.

## PHASE 5 - CAMFROG PROVIDER INTEGRATION

Inventory observed provider capabilities:

- Official client launch and shutdown
- Official URI dispatch
- Account authentication observations
- Profile and friend-list projections
- Human presence observations
- Room state verification
- Cloud Bot status observations
- Account settings and premium features

For every capability:

1. Identify the authoritative evidence source.
2. Document the exact observed request/response contract when available.
3. Create sanitized contract fixtures.
4. Implement adapters only where the integration is authorized and validated.
5. Keep unsupported actions disabled.
6. Validate success through actual provider-side observations.
7. Report inconclusive outcomes as UNKNOWN, not SUCCESS.

Do not infer undocumented protocol behavior from frontend source alone.

## PHASE 6 - COMMAND EXECUTION RELIABILITY

Introduce durable command lifecycle handling:

PENDING → CLAIMED → EXECUTING → SUCCEEDED / FAILED / UNKNOWN / RECONCILIATION_REQUIRED

Requirements:

- Persistent command ID
- Server-side idempotency key
- Lease expiry
- Monotonic fencing generation
- Bounded retries with backoff
- Agent crash recovery
- Stale-worker rejection
- Duplicate-effect prevention where supported
- Operator reconciliation for indeterminate external effects
- Append-only audit history

Never automatically retry potentially non-idempotent external actions when their outcome is unknown.

## PHASE 7 - DATABASE AND DASHBOARD

Validate:

- PostgreSQL migrations and rollback compatibility
- Foreign keys, unique constraints, and transaction boundaries
- Atomic agent reassignment and token rotation
- Data minimization and retention
- Backup and restore
- Consistent dashboard error states
- Polling freshness indicators
- Operator-visible UNKNOWN and BLOCKED states
- Accurate audit timelines

Do not display synthetic or stale account state as verified live activity.

## PHASE 8 - AUTOMATED VERIFICATION

Build and run the available tests:

- Unit tests
- API integration tests
- Database integration tests
- Security regression tests
- Command concurrency tests
- Lease expiration and replay tests
- Windows process lifecycle tests
- Camfrog provider contract tests
- Dashboard E2E tests
- Packaging and installation tests
- Backup/restore tests

Use mocks and fixtures only for deterministic tests. Clearly distinguish mocked test results from real Windows/Camfrog acceptance evidence.

If the necessary runtime, credentials, or permissions are unavailable, mark the applicable acceptance test BLOCKED. Never fabricate a pass.

## PHASE 9 - DEPLOYMENT AND PRODUCTION GATES

Verify:

- Environment validation
- Secret injection and rotation
- Shared rate limiting
- PostgreSQL readiness
- Least-privilege service configuration
- Windows startup and recovery
- Health and readiness checks
- Metrics and structured logs
- Backup/restore drill
- Rollback procedure
- Resource and load testing
- Windows long-running stability
- Authorized Camfrog live integration acceptance

No production-ready claim is permitted until all mandatory gates have verified evidence.

## PHASE 10 - DELIVERY

Provide:

1. Executive summary
2. Architecture and dependency findings
3. P0/P1/P2 security and reliability issues
4. Root cause and implemented changes
5. Changed file list and commit references
6. Verification commands and actual results
7. Windows runtime acceptance evidence
8. Camfrog integration evidence matrix
9. Remaining blockers and risks
10. Production readiness verdict

Use these final classifications:

- VERIFIED
- IMPLEMENTED_NOT_VERIFIED
- BLOCKED
- NOT_IMPLEMENTED
- NOT_APPLICABLE

Final rule:

**Never confuse source discovery, successful code execution, command dispatch, or simulated tests with a verified external provider outcome.**

Proceed autonomously with repository inspection, safe implementation, tests, and evidence collection within the available environment. Stop at authorization or production-impact boundaries requiring explicit operator approval.

## 3\. Acceptance Criteria ที่ควรใช้ตัดสินผล

| Component | Acceptance Evidence |
|--------|--------|
| FastAPI | Real HTTP integration tests + authentication/authorization regression tests |
| PostgreSQL | Migration, transaction, restore และ rollback evidence |
| Windows Agent | Real process lifecycle บน Windows พร้อม identity verification |
| Camfrog Provider | Authorized runtime evidence ว่า action สำเร็จจริง |
| Command Queue | Concurrency, lease-expiry, replay และ crash-recovery tests |
| Dashboard | E2E tests พร้อม error/unknown/stale-state coverage |
| Security | Auth boundary tests, dependency scan, secret scan และ audit evidence |
| Deployment | Clean installation, restart, observability, rollback และ soak test |

## 4\. ลำดับดำเนินการสำหรับ ZChat

แนะนำเริ่มจาก **P0 Runtime Correctness** ก่อนเพิ่ม Feature ใหม่ เพราะปัญหาที่สำคัญที่สุดคือการแยกให้ออกว่า Agent ทำงาน, Camfrog Process ทำงาน, Account Login สำเร็จ และ Room Membership เกิดขึ้นจริงหรือไม่

ลำดับคือ\:

1. **Audit actual repository** เพื่อยืนยันว่าข้อความ `implemented` ตรงกับ Source Code จริง
2. **Repair Windows process/window matching** โดยเฉพาะกรณี `Multiple or unverifiable Camfrog processes`
3. **Hardening authentication and command execution** ก่อนเปิด live actions
4. **Validate authorized Camfrog integration** ด้วยหลักฐานจาก runtime จริง
5. **Run End-to-End acceptance** แล้วจึงกำหนด Production Readiness

**ข้อสรุป\:** ควรเก็บเอกสารต้นฉบับไว้เป็น `ARCHITECTURE_AND_EVIDENCE_BOUNDARIES.md` และใช้ Master Execution Prompt ด้านบนเป็นคำสั่งทำงานสำหรับ Engineering Agent โดยให้ทุกข้อกล่าวอ้างเกี่ยวกับความสำเร็จมี Test Result หรือ Runtime Evidence รองรับเสมอ

## Prompt:
10/16/2026, 10:06:33 PM

if rea client and camfrog.com

## Response:
10/16/2026, 10:06:38 PM · gpt-6-thinking

> **ค้นหา 1 เว็บไซต์แล้ว**
>
> 
>
> ประมวลผล 5s

ถ้าต้องการให้ **ZChat Control Server ทำงานร่วมกับ Camfrog Client ตัวจริงบน Windows และเว็บไซต์ `camfrog.com` จริง** ควรเปลี่ยนจากระบบที่ทำเพียง Snapshot/Simulation เป็น **Real Client + Real Website Integration** โดยยังคงแยกสถานะและหลักฐานอย่างชัดเจน

ตรวจสอบแล้ว Camfrog มี Windows Client อย่างเป็นทางการ รองรับ Windows 10/11 พร้อมความสามารถเข้าห้องสนทนา, Private Chat และ User Directory \[[Download Camfrog and start chatting online with strangers](https://download.camfrog.com/en/windows/?utm_source=chatgpt.com)\]

## Proposed Architecture

```text
ZChat Dashboard (zchat.zeaz.dev)
            |
      FastAPI Server
            |
       PostgreSQL
            |
   Windows Control Agent
            |
       Provider Layer
         /       \
        /         \
Real Camfrog    camfrog.com
Windows Client  Official Website
        \         /
         \       /
     Verified State
            |
    ZChat Dashboard
```

## สิ่งที่ต้องพัฒนาและทดสอบจริง

| Capability | Real Windows Client | camfrog.com |
|--------|--------|--------|
| Launch / Stop | Process Control | ไม่เกี่ยวข้อง |
| Login Status | ตรวจจาก Client UI | ตรวจจาก Web Session ที่ได้รับอนุญาต |
| Account Profile | UI Observation | Authenticated Profile |
| Friend List | Client UI | Web Profile / Friends |
| Online Status | Verified UI State | Verified Web Evidence |
| Join Room | Official Client | Official Link |
| Chat / IM | Authorized Client Interaction | เฉพาะฟังก์ชันเว็บที่รองรับ |
| Cloud Bot | ถ้ารองรับ | ต้องยืนยัน Interface จริง |
| Premium / Store | Display State | Consent-based Official Checkout |

สถานะ `SUPPORTED` หรือ `VERIFIED` จะกำหนดได้หลังทดสอบกับ Client และ Website จริง ไม่ใช่จากการค้นพบ Selector หรือ Endpoint เท่านั้น

## Prompt เพิ่มเติมสำหรับ Engineering Agent

**standard: **

# ZChat - Real Camfrog Client & Website Integration

Extend the existing ZChat Control Server to integrate with BOTH:

1. The genuine, officially distributed Camfrog Windows desktop client.
2. The real https://www.camfrog.com website.

## Core Requirements

- Use the actual installed Camfrog executable, never a simulated replacement.
- Inspect real Windows processes, window handles, executable identity, and interactive sessions.
- Support safe attachment to an already-running client in read-only mode.
- Control only explicitly authorized, agent-owned processes.
- Use the official website through an authorized browser session.
- Keep desktop authentication and website authentication independent.
- Never assume website login proves desktop-client login.
- Never assume process RUNNING means account ONLINE.
- Never assume a dispatched room URI means room membership.
- Verify real outcomes through supported UI observations or documented provider interfaces.
- Do not invent or reverse-engineer undocumented private authentication contracts.
- Do not bypass CAPTCHA, anti-bot protections, authentication, or access restrictions.
- Keep passwords, session cookies, tokens, and payment credentials out of ZChat control-plane storage.
- Require operator approval before actions involving purchases, account changes, messaging, or other external side effects.
- Execute Windows background operations without unnecessary notification sounds while preserving normal system security alerts.

## Implementation Tasks

1. Audit the current repository and installed Windows client.
2. Build a version-aware WindowsClientAdapter.
3. Build an authorized CamfrogWebAdapter.
4. Implement independent client/web state machines.
5. Resolve ambiguous window matching safely.
6. Implement secure agent-to-server synchronization.
7. Add validated command execution and reconciliation.
8. Implement real dashboard status updates.
9. Add real Windows and browser integration tests.
10. Produce reproducible acceptance evidence.

## Success Criteria

- Genuine Camfrog Client process identity verified.
- Genuine camfrog.com session independently verified.
- Desktop and website account states correctly distinguished.
- Room and presence states reported only when observed.
- No unrelated processes terminated.
- No credentials leaked.
- All commands have auditable outcomes.
- Tests distinguish mocked from real-provider evidence.
- All unsupported capabilities remain disabled.

Complete the implementation where the environment and permissions allow. Mark unsupported or unverified capabilities BLOCKED instead of simulating success.

**คำแนะนำสำหรับ `cvsz/zchat`\:** ให้เริ่มด้วยการเชื่อมต่อ Camfrog Windows Client ตัวที่กำลังเปิดอยู่จริงก่อน โดยแก้ปัญหา `Multiple or unverifiable Camfrog processes` จากนั้นเชื่อมเว็บไซต์ผ่าน Browser Adapter แยกต่างหาก

เว็บทางการ: [camfrog.com](https://www.camfrog.com/?utm_source=chatgpt.com) และ [Official Windows Client](https://download.camfrog.com/en/windows/?utm_source=chatgpt.com)

## Prompt:
10/16/2026, 10:09:21 PM

[https://github.com/cvsz/zchat](https://github.com/cvsz/zchat)

## Response:
10/16/2026, 10:09:30 PM · gpt-6-thinking

ผมจะตรวจ Repository `cvsz/zchat` ผ่าน GitHub โดยดูโครงสร้างโค้ด, Camfrog Windows Client/Website adapters, tests และ Pull Requests แล้วเทียบกับ Architecture และ Evidence Boundaries ที่ส่งมาก่อนหน้านี้ครับ

> **ตรวจสอบรีโพซิทอรี zchat เอกสาร CI และรีวิวพูลรีเควสต์**
>
> 
>
> ประมวลผล 50s

## GitHub Audit: [github.com](https://github.com/cvsz/zchat?utm_source=chatgpt.com)

ตรวจสอบ Repository จริงผ่านบัญชี GitHub `cvsz` แล้ว ณ วันที่ 16 ตุลาคม 2026

Repository **cvsz/zchat**

Default branch `main`

Latest observed commit [github.com](https://github.com/cvsz/zchat/commit/6ba80e69f1e79999e10b35973db586eaaa20c585?utm_source=chatgpt.com)

Source files / tree entries **332**

Open Pull Requests **1 - PR \#44**

Production Readiness (ยังไม่ผ่านการยืนยัน)

### ข้อค้นพบสำคัญ

Repository นี้มีทั้ง `control-server`, Windows GUI, Camfrog provider-related modules, `zchat-client`, เอกสาร Reverse Engineering และชุดทดสอบอยู่แล้ว จึงควรพัฒนาต่อยอดจากสถาปัตยกรรมปัจจุบัน ไม่จำเป็นต้องสร้างระบบใหม่ทั้งหมด

ล่าสุด PR \#43 ถูก Merge เข้า `main` แล้ว เพื่อแก้การเลือก Window ที่เป็น Process ของโปรแกรมเอง และบังคับให้ปฏิเสธ Process ที่ไม่สามารถตรวจสอบ PID ได้

อย่างไรก็ตาม **PR \#44 ยังเปิดอยู่** และเกี่ยวข้องโดยตรงกับปัญหา `room_control_gui.py` ที่เคยพบ\:

[github.com](https://github.com/cvsz/zchat/pull/44?utm_source=chatgpt.com)

รายละเอียด PR ระบุว่าแก้การเลือก Window ของตัวเอง, ปฏิเสธ PID ที่พิสูจน์ไม่ได้ และป้องกัน `AttributeError` ในกรณี `process_windows` ได้ค่า `None` โดยรายงานว่า 739 root tests และชุดทดสอบอื่นผ่าน แต่ยังต้องตรวจหลักฐาน CI แยกจากคำอธิบาย PR

## 2\. ผลตรวจ Source Code และ PR \#44

| Component | ผลตรวจ | สถานะ |
|--------|--------|--------|
| FastAPI Control Plane | พบ implementation และ API transport | มี Source |
| PostgreSQL / Alembic | พบ Migration `0001`-`0006` | มี Source |
| Windows Camfrog Provider | เปิด/หยุด Client และส่ง URI ได้ตามโค้ด | ยังไม่ผ่าน Live Acceptance |
| Camfrog Website | พบ Profile Projection และ Auth-State Detector | ยังไม่มี Verified Live Fetcher |
| Real Account Login | ยังไม่พบหลักฐาน Login สำเร็จจาก Runtime | Blocked |
| Real Room Membership | URI handoff ไม่ยืนยันการเข้าห้อง | Blocked |
| Chat | Internal ZChat messaging ไม่ใช่ Camfrog Chat Protocol | ต้องแยกให้ชัดเจน |
| Cloud Bot | มี Projection แต่ยังไม่มี Verified Live Transport | Blocked |

### จุดที่พบจากโค้ดจริง

ใน `windows_client.py` ฟังก์ชัน `_join_room()` เรียก `camfrog://join_room/?name=...` แล้วคืนค่า `("succeeded", "ok")` เมื่อ Windows รับ URI สำเร็จ

นี่คือช่องว่างสำคัญ: **Command SUCCEEDED ใน Control Plane ไม่ได้หมายความว่า Camfrog เข้าห้องสำเร็จจริง** แม้ใน Source Code จะมี Comment อธิบายข้อจำกัดไว้แล้วก็ตาม

ควรเปลี่ยนผลลัพธ์ระดับ Provider เป็น `DISPATCHED_UNVERIFIED` และใช้ `SUCCEEDED` เฉพาะเมื่อมี Verified Completion Evidence พร้อมปรับ Schema และ UI ที่เกี่ยวข้องให้รองรับอย่างสอดคล้องกัน

### 3\. PR \#44 - Verification

**Independent review: `policedbc`** (Approved)

**PR Mergeability** (Mergeable)

**CodeQL / Dependency Review / Tests** (Passed)

**Windows Build** (มีอีก 1 Run กำลังทำงาน)

พบ 9 Check Runs: 8 สำเร็จ และ 1 ยังอยู่ระหว่างทำงาน ณ เวลาที่ตรวจสอบ จึงยังไม่ควรสรุปว่าทุก Workflow เสร็จสิ้น

**ยังไม่ได้ Merge PR \#44 หรือแก้ไข Repository** ในรอบนี้

## 4\. Next Implementation Priority

สำหรับเป้าหมายใช้ Camfrog Client จริงและ `camfrog.com` จริง ผมจัดลำดับเป็น\:

1. **P0 - Resolve Windows Runtime** รวม `room_control_gui.py`, self-PID exclusion, process identity และ ambiguous windows
2. **P0 - Real Client State Verification** แยก Process Running, Account Authenticated, Room Joined และ IM Delivered
3. **P1 - Real Website Adapter** ใช้ Authorized Browser Session และบันทึกเฉพาะ Sanitized Observations
4. **P1 - Command Reliability** แก้ False Success, Idempotency, Lease Fencing และ Crash Recovery
5. **P1 - Real E2E Tests** บน Windows Client และเว็บไซต์จริง พร้อม Evidence และ Logs

**ข้อสรุป\:** `cvsz/zchat` มีพื้นฐาน Control Plane และ Windows Integration อยู่แล้ว และ PR \#44 มีผลตรวจที่ดี แต่ส่วนที่เชื่อมกับ Camfrog ตัวจริงยังไม่ผ่านหลักฐาน End-to-End จึงไม่ควรประกาศ Production Ready ในตอนนี้

การดำเนินงานถัดไปที่เหมาะสมที่สุดคือปิด P0 Windows Runtime ให้ผ่านก่อน แล้วจึงขยาย Real Client และ Real Website Integration โดยไม่ใช้ Simulation เป็นหลักฐานความสำเร็จ

## Prompt:
10/16/2026, 10:13:50 PM

if decompile Camfrog Video Chat.exe

## Response:
10/16/2026, 10:14:11 PM · gpt-6-thinking

> **ค้นหาใน 3 เว็บไซต์แล้ว**
>
> 
>
> ประมวลผล 19s

สามารถทำ **Reverse Engineering / Decompile `Camfrog Video Chat.exe`** เพื่อศึกษาการทำงานของ Windows Client จริง และนำผลไปปรับปรุง [github.com](https://github.com/cvsz/zchat?utm_source=chatgpt.com) ได้ แต่ต้องแยกให้ออกระหว่างการวิเคราะห์โปรแกรมกับการนำโค้ดหรือ Protocol ภายในไปใช้งาน

## 1\. Decompile Camfrog Client ได้แค่ไหน?

ขึ้นอยู่กับว่า `Camfrog Video Chat.exe` ถูกสร้างด้วยเทคโนโลยีใด

| ประเภท Binary | เครื่องมือ | ผลที่ได้ |
|--------|--------|--------|
| Native C/C++ | Ghidra, IDA Free | Disassembly และ Pseudocode |
| \.NET Assembly | ILSpy, dnSpyEx | Decompiled C\# |
| Electron | Electron ASAR tools | JavaScript/Resources |
| Packed Binary | Detect It Easy, PE analysis | ระบุ Packaging และข้อจำกัด |

สำหรับ Native C++ จะไม่ได้ Source Code ต้นฉบับ 100% แต่สามารถวิเคราะห์โครงสร้างของโปรแกรม, Imports, Strings, Windows APIs และบางส่วนของ Control Flow ได้

## 2\. สิ่งที่ควรวิเคราะห์เพื่อปรับปรุง ZChat

เน้นส่วนที่จำเป็นต่อการเชื่อมต่ออย่างปลอดภัย ได้แก่\:

- **Process/Window Model\:** การจัดการ PID, HWND, Main Window, Room Windows และ Windows Session
- **Official URI Handling\:** ตรวจสอบการรับ `camfrog:` URI และการส่งต่อคำสั่ง
- **Account State Observations\:** แยก Login, Connection และ Room Membership
- **Client Configuration\:** ตำแหน่งไฟล์ Configuration และการตั้งค่าที่ไม่ใช่ Secrets
- **Runtime Events\:** ตรวจสอบว่า Launch, Join Room และ IM handoff สำเร็จจริงหรือไม่
- **Version Compatibility\:** บันทึก Client Version, Binary Hash และพฤติกรรมที่เปลี่ยนแปลง

ไม่ควรแก้ Binary เพื่อข้าม License, Login, CAPTCHA หรือระบบป้องกันของ Camfrog และไม่ควรนำ Session Keys, Credentials หรือ Private Protocol ไปใช้โดยไม่ได้รับอนุญาต

## 3\. ข้อจำกัดด้าน License ที่ตรวจพบ

เงื่อนไขของ Camfrog ระบุข้อห้ามเกี่ยวกับ Reverse Engineering, Decompilation, Disassembly และการดัดแปลงซอฟต์แวร์อย่างชัดเจน \[[كامفروج](https://www.camfrog.com/ar/terms.phtmlprivacy?utm_source=chatgpt.com)\]

ดังนั้น ก่อน Decompile Binary จริงเพื่อใช้ในผลิตภัณฑ์ ZChat ควรได้รับอนุญาตจาก Camfrog หรือให้ผู้เชี่ยวชาญกฎหมายตรวจสอบข้อยกเว้นที่อาจใช้ได้ตามกฎหมายที่เกี่ยวข้อง

สำหรับตอนนี้สามารถเริ่มจาก **Non-invasive Binary Inspection** และ Windows Runtime Observation โดยไม่ต้อง Decompile โค้ดภายใน

### PowerShell - ตรวจสอบ Camfrog Video Chat.exe

รันบน Windows 11\:

```powershell
$proc = Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -match 'Camfrog'
    }

$proc | Select-Object `
    ProcessId,
    ParentProcessId,
    Name,
    ExecutablePath,
    CommandLine

$proc | ForEach-Object {
    $path = $_.ExecutablePath

    if ($path -and (Test-Path -LiteralPath $path)) {
        Get-Item -LiteralPath $path |
            Select-Object FullName, Length, VersionInfo

        Get-AuthenticodeSignature -LiteralPath $path |
            Select-Object Status, SignerCertificate

        Get-FileHash -LiteralPath $path -Algorithm SHA256
    }
}
```

ผลลัพธ์ช่วยตรวจว่า Client ที่กำลังทำงานอยู่คือ Executable ใด อยู่ที่ไหน ใช้ Version อะไร และมี Digital Signature หรือไม่ โดยไม่แก้ไข Binary

คำสั่งนี้ยังไม่ได้ยืนยันว่า Process นั้นเป็น Camfrog ของแท้ ต้องตรวจ Publisher, Signature Chain และแหล่งที่มาของไฟล์ประกอบ

## 4\. แนวทางสำหรับ ZChat

ผมแนะนำให้เริ่มจาก `Real Windows Runtime Adapter` โดยใช้ Process Inspection, Windows UI Automation และ Official URI Handling ก่อน จากนั้นจึงพัฒนา Browser Adapter สำหรับ `camfrog.com` ผ่าน Interface ที่ได้รับอนุญาต

หากจำเป็นต้องศึกษาภายใน Executable เพิ่มเติม ควรขออนุญาตทางเทคนิคและสิทธิการใช้งานจาก Camfrog ก่อน เพื่อให้ ZChat สามารถพัฒนาเป็นผลิตภัณฑ์เชิงพาณิชย์ได้โดยมีความเสี่ยงด้าน License ต่ำลง

**สถานะปัจจุบัน\:** ยังไม่ได้ Decompile `Camfrog Video Chat.exe` และยังไม่มี Binary จริงให้ตรวจสอบในบทสนทนานี้

## Prompt:
10/16/2026, 10:15:52 PM

============================================================
FULL BUILD COMPLETE
============================================================

Outputs:
  dist\room-control\room-control.exe
  dist\chat-im-private\chat-im-private.exe
  dist\status-random\status-random.exe
  dist\status-marquee\status-marquee.exe
  dist\im-autoreply\im-autoreply.exe
  dist\web-status\web-status.exe
  dist\music-dj\music-dj.exe
  dist\status-changer\status-changer.exe
  dist\zchat-client\zchat-client.exe
  dist\zchat-client\SHA256SUMS.txt
  camfrog-features-windows.zip
  dist\SHA256SUMS.txt
  dist\BUILD_SOURCE.txt
  line\dist\line-status-changer.exe
  line\dist\line_config.json

Build only: no Git staging, commit, or push is performed.
Without --release, no GitHub release is created either.

PS D:\data\zchat> $proc = Get-CimInstance Win32_Process |
>>     Where-Object {
>>         $_.Name -match 'Camfrog'
>>     }
PS D:\data\zchat>
PS D:\data\zchat> $proc | Select-Object `
>>     ProcessId,
>>     ParentProcessId,
>>     Name,
>>     ExecutablePath,
>>     CommandLine

ProcessId       : 21992
ParentProcessId : 9880
Name            : Camfrog Video Chat.exe
ExecutablePath  : C:\Users\REPLACE_ME\AppData\Local\Programs\Camfrog Video Chat\Camfrog Video Chat.exe
CommandLine     : "C:\Users\REPLACE_ME\AppData\Local\Programs\Camfrog Video Chat\Camfrog Video Chat.ex
                  e"

ProcessId       : 15788
ParentProcessId : 21992
Name            : camfrog_cef.exe
ExecutablePath  : C:\Users\REPLACE_ME\AppData\Local\Programs\Camfrog Video Chat\camfrog_cef.exe
CommandLine     : "C:\Users\REPLACE_ME\AppData\Local\Programs\Camfrog Video Chat\camfrog_cef.exe" --ty
                  pe=gpu-process --field-trial-handle=2512,10311354875437920321,8650847908737642596,1
                  31072 --disable-features=CalculateNativeWinOcclusion --no-sandbox --log-file="C:\Us
                  ers\REPLACE_ME\AppData\Local\Programs\Camfrog Video Chat\debug.log" --log-severity=d
                  isable --lang=en-US --gpu-preferences=SAAAAAAAAADgAAAwAAAAAAAAAAAAAAAAAABgAAAAAAAoA
                  AAAAAAAAAAAAAAAAAAAAAAAAAAAAAB4AAAAAAAAAHgAAAAAAAAAKAAAAAQAAAAgAAAAAAAAACgAAAAAAAAA
                  MAAAAAAAAAA4AAAAAAAAABAAAAAAAAAAAAAAAAUAAAAQAAAAAAAAAAAAAAAGAAAAEAAAAAAAAAABAAAABQA
                  AABAAAAAAAAAAAQAAAAYAAAAIAAAAAAAAAAgAAAAAAAAA --log-file="C:\Users\REPLACE_ME\AppDat
                  a\Local\Programs\Camfrog Video Chat\debug.log" --mojo-platform-channel-handle=2520
                  /prefetch:2

ProcessId       : 17384
ParentProcessId : 21992
Name            : camfrog_cef.exe
ExecutablePath  : C:\Users\REPLACE_ME\AppData\Local\Programs\Camfrog Video Chat\camfrog_cef.exe
CommandLine     : "C:\Users\REPLACE_ME\AppData\Local\Programs\Camfrog Video Chat\camfrog_cef.exe" --ty
                  pe=utility --utility-sub-type=network.mojom.NetworkService --field-trial-handle=251
                  2,10311354875437920321,8650847908737642596,131072 --disable-features=CalculateNativ
                  eWinOcclusion --lang=en-US --service-sandbox-type=none --no-sandbox --log-file="C:\
                  Users\REPLACE_ME\AppData\Local\Programs\Camfrog Video Chat\debug.log" --log-severity
                  =disable --lang=en-US --log-file="C:\Users\REPLACE_ME\AppData\Local\Programs\Camfrog
                   Video Chat\debug.log" --mojo-platform-channel-handle=3020 /prefetch:8

ProcessId       : 21632
ParentProcessId : 21992
Name            : camfrog_cef.exe
ExecutablePath  : C:\Users\REPLACE_ME\AppData\Local\Programs\Camfrog Video Chat\camfrog_cef.exe
CommandLine     : "C:\Users\REPLACE_ME\AppData\Local\Programs\Camfrog Video Chat\camfrog_cef.exe" --ty
                  pe=utility --utility-sub-type=storage.mojom.StorageService --field-trial-handle=251
                  2,10311354875437920321,8650847908737642596,131072 --disable-features=CalculateNativ
                  eWinOcclusion --lang=en-US --service-sandbox-type=utility --no-sandbox --log-file="
                  C:\Users\REPLACE_ME\AppData\Local\Programs\Camfrog Video Chat\debug.log" --log-sever
                  ity=disable --lang=en-US --log-file="C:\Users\REPLACE_ME\AppData\Local\Programs\Camf
                  rog Video Chat\debug.log" --mojo-platform-channel-handle=4480 /prefetch:8

ProcessId       : 3944
ParentProcessId : 21992
Name            : camfrog_cef.exe
ExecutablePath  : C:\Users\REPLACE_ME\AppData\Local\Programs\Camfrog Video Chat\camfrog_cef.exe
CommandLine     : "C:\Users\REPLACE_ME\AppData\Local\Programs\Camfrog Video Chat\camfrog_cef.exe" --ty
                  pe=renderer --no-sandbox --autoplay-policy=no-user-gesture-required --log-file="C:\
                  Users\REPLACE_ME\AppData\Local\Programs\Camfrog Video Chat\debug.log" --field-trial-
                  handle=2512,10311354875437920321,8650847908737642596,131072 --disable-features=Calc
                  ulateNativeWinOcclusion --lang=en-US --log-file="C:\Users\REPLACE_ME\AppData\Local\P
                  rograms\Camfrog Video Chat\debug.log" --log-severity=disable --device-scale-factor=
                  1 --num-raster-threads=4 --enable-main-frame-before-activation --renderer-client-id
                  =6 --no-v8-untrusted-code-mitigations --mojo-platform-channel-handle=4300 /prefetch
                  :1

ProcessId       : 18440
ParentProcessId : 21992
Name            : camfrog_cef.exe
ExecutablePath  : C:\Users\REPLACE_ME\AppData\Local\Programs\Camfrog Video Chat\camfrog_cef.exe
CommandLine     : "C:\Users\REPLACE_ME\AppData\Local\Programs\Camfrog Video Chat\camfrog_cef.exe" --ty
                  pe=renderer --no-sandbox --autoplay-policy=no-user-gesture-required --log-file="C:\
                  Users\REPLACE_ME\AppData\Local\Programs\Camfrog Video Chat\debug.log" --field-trial-
                  handle=2512,10311354875437920321,8650847908737642596,131072 --disable-features=Calc
                  ulateNativeWinOcclusion --lang=en-US --log-file="C:\Users\REPLACE_ME\AppData\Local\P
                  rograms\Camfrog Video Chat\debug.log" --log-severity=disable --device-scale-factor=
                  1 --num-raster-threads=4 --enable-main-frame-before-activation --renderer-client-id
                  =5 --no-v8-untrusted-code-mitigations --mojo-platform-channel-handle=4580 /prefetch
                  :1

PS D:\data\zchat>
PS D:\data\zchat> $proc | ForEach-Object {
>>     $path = $_.ExecutablePath
>>
>>     if ($path -and (Test-Path -LiteralPath $path)) {
>>         Get-Item -LiteralPath $path |
>>             Select-Object FullName, Length, VersionInfo
>>
>>         Get-AuthenticodeSignature -LiteralPath $path |
>>             Select-Object Status, SignerCertificate
>>
>>         Get-FileHash -LiteralPath $path -Algorithm SHA256
>>     }
>> }

FullName                                                                              Length VersionI
                                                                                             nfo
--------                                                                              ------ --------
C:\Users\REPLACE_ME\AppData\Local\Programs\Camfrog Video Chat\Camfrog Video Chat.exe 61713584 File:  …
                                                                                           1
                                                                                           1
C:\Users\REPLACE_ME\AppData\Local\Programs\Camfrog Video Chat\camfrog_cef.exe         1428656 File:  …
                                                                                           1
                                                                                           1
C:\Users\REPLACE_ME\AppData\Local\Programs\Camfrog Video Chat\camfrog_cef.exe         1428656 File:  …
                                                                                           1
                                                                                           1
C:\Users\REPLACE_ME\AppData\Local\Programs\Camfrog Video Chat\camfrog_cef.exe         1428656 File:  …
                                                                                           1
                                                                                           1
C:\Users\REPLACE_ME\AppData\Local\Programs\Camfrog Video Chat\camfrog_cef.exe         1428656 File:  …
                                                                                           1
                                                                                           1
C:\Users\REPLACE_ME\AppData\Local\Programs\Camfrog Video Chat\camfrog_cef.exe         1428656 File:  …
                                                                                           1
                                                                                           1

PS D:\data\zchat>

## Response:
10/16/2026, 10:16:12 PM · gpt-6-thinking

## ZChat + Real Camfrog Client - Runtime Analysis

จาก PowerShell Output ที่ส่งมา ยืนยันได้ว่า **Camfrog Video Chat ตัวจริงกำลังทำงานบน Windows** และมี Chromium Embedded Framework (CEF) subprocesses อยู่ภายใต้ Main Process

ส่วน ZChat Build รายงานว่าสร้าง Executable สำเร็จครบตามรายการ แต่ยังไม่ได้ยืนยันว่าแต่ละโปรแกรมทำงานแบบ End-to-End ได้จริง

### 1\. Runtime Findings

ZChat Build (Reported complete)

Camfrog Main Process **PID 21992**

CEF Child Processes **5 processes**

Camfrog Main EXE **61,713,584 bytes**

Windows Runtime State (Process observed)

โครงสร้าง Process ที่พบ\:

```text
explorer.exe (PID 9880)
└── Camfrog Video Chat.exe (PID 21992)
    ├── camfrog_cef.exe (PID 15788) GPU
    ├── camfrog_cef.exe (PID 17384) Network
    ├── camfrog_cef.exe (PID 21632) Storage
    ├── camfrog_cef.exe (PID 3944) Renderer
    └── camfrog_cef.exe (PID 18440) Renderer
```

สิ่งสำคัญคือ **อย่านับ `camfrog_cef.exe` เป็น Camfrog Account Instance อีก 5 ตัว** เพราะทั้งหมดเป็น Child Processes ของ Main Client เดียวกัน

### 2\. Security Findings

จาก Command Line พบ\:

- `--no-sandbox` ใน CEF subprocesses หลายตัว
- `--service-sandbox-type=none` ใน Network Service
- `--no-v8-untrusted-code-mitigations` ใน Renderer
- `--autoplay-policy=no-user-gesture-required`

ข้อเท็จจริงเหล่านี้ควรถูกบันทึกไว้ใน Security Audit แต่ยังสรุปว่าเป็นช่องโหว่ที่ใช้โจมตีได้จริงไม่ได้โดยไม่มีการตรวจ Client Version, CEF Version และการตั้งค่าอื่นเพิ่มเติม

ไม่แนะนำให้แก้ flags ของ Camfrog โดยตรง เพราะอาจทำให้ Official Client ทำงานผิดพลาด

## 3\. Next Step - ตรวจ Binary Identity และ Windows Integration

ก่อน Decompile ควรเก็บหลักฐานที่ยังขาด ได้แก่ File Version, SHA256, Digital Signature และ Windows Main Window Identity

รัน PowerShell นี้จาก `D:\data\zchat` ได้เลย\:

```powershell
$ErrorActionPreference = "Stop"

$reportDir = "D:\data\zchat\reports\camfrog-runtime"
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null

$main = Get-CimInstance Win32_Process -Filter "Name='Camfrog Video Chat.exe'"

$results = foreach ($p in $main) {
    if (-not $p.ExecutablePath) { continue }

    $file = Get-Item -LiteralPath $p.ExecutablePath
    $sig = Get-AuthenticodeSignature -LiteralPath $file.FullName
    $hash = Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256
    $runtime = Get-Process -Id $p.ProcessId -ErrorAction Stop

    [PSCustomObject]@{
        PID              = $p.ProcessId
        ParentPID        = $p.ParentProcessId
        Path             = $file.FullName
        FileVersion      = $file.VersionInfo.FileVersion
        ProductVersion   = $file.VersionInfo.ProductVersion
        Company          = $file.VersionInfo.CompanyName
        SignatureStatus  = $sig.Status.ToString()
        Signer           = $sig.SignerCertificate.Subject
        SHA256           = $hash.Hash
        MainWindowHandle = $runtime.MainWindowHandle.ToInt64()
        MainWindowTitle  = $runtime.MainWindowTitle
        StartTime        = $runtime.StartTime.ToString("o")
    }
}

$results | Format-List

$results | ConvertTo-Json -Depth 5 |
    Set-Content "$reportDir\main-process.json" -Encoding utf8
```

สคริปต์นี้ไม่ปิดหรือแก้ไข Camfrog และจะสร้างรายงาน `main-process.json` เพื่อใช้เปรียบเทียบกับ Windows Agent

หากต้องการตรวจโครงสร้าง Binary เพิ่มเติม สามารถใช้ Ghidra หรือ PE inspection tools แบบ Read-only หลังตรวจสอบสิทธิและข้อกำหนดการใช้งานแล้ว ไม่จำเป็นต้อง Patch หรือ Inject Process

## 4\. การแก้ไข ZChat ที่ควรดำเนินการ

สำหรับ `cvsz/zchat` ผมแนะนำให้แก้ `WindowsCamfrogClientProvider` ให้แยก Process ที่เปิดเองกับ Process ที่เปิดอยู่ก่อนหน้า\:

```text
WindowsCamfrogClientProvider
  ├── discover()
  │   └── Locate real Camfrog main process
  ├── verify_identity()
  │   ├── Executable path
  │   ├── Digital signature
  │   ├── PID and creation time
  │   └── Window association
  ├── attach_readonly()
  │   └── Observe existing authorized client
  ├── launch()
  │   └── Create owned process
  ├── dispatch_uri()
  │   └── Report DISPATCHED_UNVERIFIED
  └── stop_owned()
      └── Never terminate unrelated processes
```

ส่วน Camfrog Website ให้ใช้ Browser Adapter แยกต่างหาก ไม่ควรนำ CEF Network Service ที่พบไปใช้แทน API ของ `camfrog.com` โดยตรง

**ผลที่ยืนยันแล้ว\:** Camfrog Main Process PID `21992` และ CEF Child Processes 5 ตัวมีอยู่จริงใน Runtime Snapshot ที่ส่งมา

**ยังต้องพิสูจน์\:** Digital Signature, Client Version, Login State, Room Membership, Live Website Integration และ ZChat-to-Camfrog End-to-End Actions

ส่งผลลัพธ์ `main-process.json` หรือข้อความจาก `Format-List` กลับมาได้ เพื่อให้ระบุ Process Identity และแนวทางแก้ `room_control_gui.py` ได้แม่นยำขึ้น โดยไม่ต้อง Decompile Binary ก่อน

## Prompt:
10/16/2026, 10:17:43 PM

PS D:\data\zchat> $ErrorActionPreference = "Stop"
PS D:\data\zchat>
PS D:\data\zchat> $reportDir = "D:\data\zchat\reports\camfrog-runtime"
PS D:\data\zchat> New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
PS D:\data\zchat>
PS D:\data\zchat> $main = Get-CimInstance Win32_Process -Filter "Name='Camfrog Video Chat.exe'"
PS D:\data\zchat>
PS D:\data\zchat> $results = foreach ($p in $main) {
>>     if (-not $p.ExecutablePath) { continue }
>>
>>     $file = Get-Item -LiteralPath $p.ExecutablePath
>>     $sig = Get-AuthenticodeSignature -LiteralPath $file.FullName
>>     $hash = Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256
>>     $runtime = Get-Process -Id $p.ProcessId -ErrorAction Stop
>>
>>     [PSCustomObject]@{
>>         PID              = $p.ProcessId
>>         ParentPID        = $p.ParentProcessId
>>         Path             = $file.FullName
>>         FileVersion      = $file.VersionInfo.FileVersion
>>         ProductVersion   = $file.VersionInfo.ProductVersion
>>         Company          = $file.VersionInfo.CompanyName
>>         SignatureStatus  = $sig.Status.ToString()
>>         Signer           = $sig.SignerCertificate.Subject
>>         SHA256           = $hash.Hash
>>         MainWindowHandle = $runtime.MainWindowHandle.ToInt64()
>>         MainWindowTitle  = $runtime.MainWindowTitle
>>         StartTime        = $runtime.StartTime.ToString("o")
>>     }
>> }
PS D:\data\zchat>
PS D:\data\zchat> $results | Format-List

PID              : 21992
ParentPID        : 9880
Path             : C:\Users\REPLACE_ME\AppData\Local\Programs\Camfrog Video Chat\Camfrog Video Chat.ex
                   e
FileVersion      : 8.5.0.51219
ProductVersion   : 8.5.0.51219
Company          : Camfrog LLC
SignatureStatus  : Valid
Signer           : CN=Camfrog LLC, O=Camfrog LLC, L=Las Vegas, S=Nevada, C=US, SERIALNUMBER=10033625,
                    OID.2.5.4.15=Private Organization, OID.1.3.6.1.4.1.311.60.2.1.2=Delaware, OID.1.3
                   .6.1.4.1.311.60.2.1.3=US
SHA256           : 0B744602C004536DCF81E9965E8CB17358EB276B3876A1E70C50F72777C27E06
MainWindowHandle : 5177812
MainWindowTitle  : REPLACE_ME_ACCOUNT (status)
StartTime        : 2026-10-16T21:21:56.6723657+07:00

PS D:\data\zchat>
PS D:\data\zchat> $results | ConvertTo-Json -Depth 5 |
>>     Set-Content "$reportDir\main-process.json" -Encoding utf8
PS D:\data\zchat>

## Response:
10/16/2026, 10:17:47 PM · gpt-6-thinking

## Camfrog 8.5.0 - Verified Runtime Identity

ผลตรวจครั้งนี้ยืนยันตัวตนของ Camfrog Windows Client ได้ชัดเจนขึ้น โดยไม่ต้อง Decompile หรือแก้ไข Binary

**Digital Signature** (Valid)

**Process Identity** (Verified at capture)

**Login / Room Membership** (Not verified)

| Property | Observed value |
|--------|--------|
| Application | Camfrog Video Chat |
| Version | `8.5.0.51219` |
| Publisher | Camfrog LLC |
| Signature | `Valid` |
| PID | `21992` |
| Parent PID | `9880` |
| Main Window Handle | `5177812` |
| Window Title | `REPLACE_ME_ACCOUNT (status)` |
| Start Time | `2026-10-16 21:21:56 +07:00` |
| SHA256 | `0B744602C004536DCF81E9965E8CB17358EB276B3876A1E70C50F72777C27E06` |

การตรวจ Authenticode ยืนยันว่า Windows ประเมินลายเซ็นว่า Valid และ Certificate ระบุ Camfrog LLC แต่ยังไม่ได้พิสูจน์พฤติกรรมทั้งหมดของโปรแกรม

### ข้อค้นพบสำคัญสำหรับ ZChat

**`MainWindowTitle = REPLACE_ME_ACCOUNT (status)`** เป็นข้อมูลที่ช่วยแก้ Window Discovery ได้โดยตรง

ข้อความ `(ไม่อยู่)` อาจแสดงสถานะ Away ของบัญชี แต่ยังไม่ควรนำไปยืนยัน `AccountPresence = AWAY` จนกว่าจะทดสอบเทียบกับสถานะจริง

การเลือก Window ควรใช้ PID และ Process Identity เป็นหลัก ไม่ใช่ชื่อหน้าต่างเพียงอย่างเดียว

## ขั้นตอนถัดไป: ทดสอบ Window Selection จริง

รันคำสั่งต่อไปนี้ใน PowerShell เพื่อดูว่าหน้าต่างใดเป็นของ Camfrog Main Process และทดสอบว่า ZChat ควรเลือกหน้าต่างใด

```powershell
cd D:\data\zchat

@'
import psutil
from pywinauto import Desktop

TARGET_EXE = "camfrog video chat.exe"

processes = []

for proc in psutil.process_iter(["pid", "name", "exe", "create_time"]):
    try:
        if (proc.info["name"] or "").casefold() == TARGET_EXE:
            processes.append(proc.info)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        continue

windows = Desktop(backend="uia").windows(visible_only=True)

for proc in processes:
    pid = proc["pid"]
    print(f"\nCamfrog PID={pid}")
    print(f"Executable={proc['exe']}")
    print(f"Created={proc['create_time']}")

    for window in windows:
        try:
            if window.process_id() == pid:
                print({
                    "handle": window.handle,
                    "title": window.window_text(),
                    "class": window.class_name(),
                    "visible": window.is_visible(),
                })
        except Exception:
            continue
'@ | python -
```

โค้ดนี้เป็น Read-only และไม่ส่งคำสั่งไปยัง Camfrog

หาก ZChat ใช้ Virtual Environment ให้รันด้วย Python Environment ที่ติดตั้ง `pywinauto` และ `psutil` แล้ว

### Acceptance Criteria

หลังจากนำผล Window Discovery ไปปรับปรุง `cvsz/zchat` ต้องตรวจให้ผ่านว่า\:

1. ค้นหา Camfrog Main Process จาก Executable Identity ได้ แม้ Window Title เปลี่ยนตามชื่อบัญชีหรือสถานะ
2. ไม่เลือก `room-control.exe` หรือหน้าต่าง ZChat เป็น Camfrog
3. ไม่เลือก `camfrog_cef.exe` เป็น Main Account Process
4. เมื่อมีหลาย Camfrog Main Processes ต้องหยุดการเลือกอัตโนมัติและให้ผู้ปฏิบัติงานระบุ Process
5. ตรวจ PID และ Creation Time ใหม่ก่อนทำ Action เพื่อป้องกัน PID Reuse
6. Process ที่ไม่ได้สร้างโดย ZChat ต้องใช้ `read-only attach` เป็นค่าเริ่มต้น
7. แยก `PROCESS_RUNNING`, `WINDOW_FOUND`, `AUTH_OBSERVED` และ `ROOM_JOINED_VERIFIED` ออกจากกัน

**สถานะการดำเนินงาน\:** ยืนยัน Process Identity และ Digital Signature ได้จาก Runtime Evidence ที่ส่งมาแล้ว ส่วนการแก้ไข Repository, ทดสอบ Window Discovery และการเชื่อมต่อ `camfrog.com` จริงยังไม่ได้ดำเนินการในรอบนี้

ผลลัพธ์จากคำสั่ง Window Discovery จะเป็นหลักฐานชุดต่อไปที่ใช้ตัดสินว่าควรแก้ `room_control_gui.py` และ `windows_client.py` ตรงไหนโดยไม่ต้อง Decompile Camfrog ก่อน

## Prompt:
10/16/2026, 10:19:58 PM

PS D:\data\zchat> $results | ConvertTo-Json -Depth 5 |
>>     Set-Content "$reportDir\main-process.json" -Encoding utf8
PS D:\data\zchat> cd D:\data\zchat
PS D:\data\zchat>
PS D:\data\zchat> @'
>> import psutil
>> from pywinauto import Desktop
>>
>> TARGET_EXE = "camfrog video chat.exe"
>>
>> processes = []
>>
>> for proc in psutil.process_iter(["pid", "name", "exe", "create_time"]):
>>     try:
>>         if (proc.info["name"] or "").casefold() == TARGET_EXE:
>>             processes.append(proc.info)
>>     except (psutil.NoSuchProcess, psutil.AccessDenied):
>>         continue
>>
>> windows = Desktop(backend="uia").windows(visible_only=True)
>>
>> for proc in processes:
>>     pid = proc["pid"]
>>     print(f"\nCamfrog PID={pid}")
>>     print(f"Executable={proc['exe']}")
>>     print(f"Created={proc['create_time']}")
>>
>>     for window in windows:
>>         try:
>>             if window.process_id() == pid:
>>                 print({
>>                     "handle": window.handle,
>>                     "title": window.window_text(),
>>                     "class": window.class_name(),
>>                     "visible": window.is_visible(),
>>                 })
>>         except Exception:
>>             continue
>> '@ | python -
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "C:\Program Files\Python314\Lib\site-packages\psutil\__init__.py", line 110, in <module>
    from . import _pswindows as _psplatform
  File "C:\Program Files\Python314\Lib\site-packages\psutil\_pswindows.py", line 35, in <module>
    from ._psutil_windows import ABOVE_NORMAL_PRIORITY_CLASS
ModuleNotFoundError: No module named 'psutil._psutil_windows'
PS D:\data\zchat>

## Response:
10/16/2026, 10:20:09 PM · gpt-6-thinking

> **ค้นหาใน 2 เว็บไซต์แล้ว**
>
> 
>
> ประมวลผล 11s

## Root Cause: `psutil._psutil_windows` Missing

ปัญหานี้เกิดจาก Python 3.14 ที่กำลังเรียกใช้ `psutil` แต่ไม่สามารถโหลด Native Extension สำหรับ Windows ได้

```text
Python: C:\Program Files\Python314\
Error: ModuleNotFoundError: No module named 'psutil._psutil_windows'
```

สาเหตุที่เป็นไปได้คือ `psutil` ติดตั้งไม่สมบูรณ์, Binary Wheel ไม่ตรงกับ Python Runtime หรือมีไฟล์ Extension ขาดหาย

**ไม่ใช่ปัญหาของ Camfrog หรือ Windows Process โดยตรง** เพราะโปรแกรมล้มเหลวตั้งแต่ขั้นตอน `import psutil`

### 1\. แก้ psutil บน Python 3.14

รันใน PowerShell\:

```powershell
cd D:\data\zchat

python -m pip --version
python -m pip show psutil

python -m pip uninstall -y psutil
python -m pip install --no-cache-dir --only-binary=:all: psutil
```

จากนั้นตรวจสอบ\:

```powershell
python -c "import psutil; print('psutil:', psutil.__version__)"
python -c "from pywinauto import Desktop; print('pywinauto: OK')"
```

หากทั้งสองคำสั่งทำงานได้ ให้ลองรัน Window Discovery อีกครั้ง

PyPI ยืนยันว่า `psutil` มี Windows Binary Wheel ที่รองรับ Python 3.14 แล้ว จึงไม่จำเป็นต้อง Downgrade Python ทันที \[[psutil](https://pypi.org/project/psutil/?utm_source=chatgpt.com)\]

### 2\. ทางเลือกที่เร็วกว่า - ไม่ใช้ psutil

ถ้าต้องการตรวจ Camfrog Window ตอนนี้เลย สามารถใช้ `pywinauto` และ Windows Process Information ที่ตรวจพบก่อนหน้าได้โดยตรง

```powershell
@'
from pywinauto import Desktop

CAMFROG_PID = 21992

windows = Desktop(backend="uia").windows(
    process=CAMFROG_PID,
    visible_only=True
)

print(f"Camfrog PID: {CAMFROG_PID}")
print(f"Windows found: {len(windows)}")

for window in windows:
    print({
        "handle": window.handle,
        "title": window.window_text(),
        "class": window.class_name(),
        "visible": window.is_visible(),
    })
'@ | python -
```

หมายเหตุ: PID `21992` เป็นค่าจาก Snapshot ก่อนหน้า หากมีการ Restart Camfrog ต้องตรวจ PID ใหม่ก่อนใช้งาน

หาก `pywinauto` เอง Import ไม่ผ่าน ให้ใช้ PowerShell ตรวจ Windows Process โดยไม่ต้องพึ่ง Python\:

```powershell
Get-Process -Name "Camfrog Video Chat" |
    Select-Object Id, StartTime, MainWindowHandle, MainWindowTitle, Path |
    Format-List
```

### 3\. สำหรับ Production ZChat

ไม่ควรแก้ปัญหานี้ด้วยการติดตั้ง Package ลง Global Python อย่างเดียว แนะนำสร้าง Virtual Environment แยก\:

```powershell
cd D:\data\zchat

py -3.14 -m venv .venv-runtime

.\.venv-runtime\Scripts\python.exe -m pip install --upgrade pip

.\.venv-runtime\Scripts\python.exe -m pip install `
    --only-binary=:all: psutil pywinauto

.\.venv-runtime\Scripts\python.exe -c `
    "import psutil; from pywinauto import Desktop; print('Runtime dependencies OK')"
```

จากนั้นใช้งาน Python ใน `.venv-runtime` สำหรับการตรวจสอบ แทน Global Python 3.14

**เป้าหมายถัดไป\:** ให้ Window Discovery แสดงหน้าต่างทั้งหมดของ Camfrog PID เดียวกันได้อย่างถูกต้อง โดยไม่ปะปนกับ `room-control.exe` และไม่ปิด Process ที่ ZChat ไม่ได้เป็นเจ้าของ

## Prompt:
10/16/2026, 10:20:52 PM

PS D:\data\zchat> cd D:\data\zchat
PS D:\data\zchat>
PS D:\data\zchat> python -m pip --version
pip 26.2.1 from C:\Program Files\Python314\Lib\site-packages\pip (python 3.14)
PS D:\data\zchat> python -m pip show psutil
Name: psutil
Version: 6.1.1
Summary: Cross-platform lib for process and system monitoring in Python.
Home-page: https://github.com/giampaolo/psutil
Author: Giampaolo Rodola
Author-email: g.rodola@gmail.com
License: BSD-3-Clause
Location: C:\Program Files\Python314\Lib\site-packages
Requires:
Required-by:
PS D:\data\zchat>
PS D:\data\zchat> python -m pip uninstall -y psutil
Found existing installation: psutil 6.1.1
Uninstalling psutil-6.1.1:
ERROR: Exception:
Traceback (most recent call last):
  File "C:\Program Files\Python314\Lib\shutil.py", line 922, in move
    os.rename(src, real_dst)
    ~~~~~~~~~^^^^^^^^^^^^^^^
PermissionError: [WinError 5] Access is denied: 'c:\\program files\\python314\\lib\\site-packages\\psutil-6.1.1.dist-info\\' -> 'C:\\Users\\REPLACE_ME\\AppData\\Local\\Temp\\pip-uninstall-omntzacq'

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "C:\Program Files\Python314\Lib\site-packages\pip\_internal\cli\base_command.py", line 109, in _run_wrapper
    status = _inner_run()
  File "C:\Program Files\Python314\Lib\site-packages\pip\_internal\cli\base_command.py", line 102, in _inner_run
    return self.run(options, args)
           ~~~~~~~~^^^^^^^^^^^^^^^
  File "C:\Program Files\Python314\Lib\site-packages\pip\_internal\commands\uninstall.py", line 105, in run
    uninstall_pathset = req.uninstall(
        auto_confirm=options.yes,
        verbose=self.verbosity > 0,
    )
  File "C:\Program Files\Python314\Lib\site-packages\pip\_internal\req\req_install.py", line 680, in uninstall
    uninstalled_pathset.remove(auto_confirm, verbose)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Program Files\Python314\Lib\site-packages\pip\_internal\req\req_uninstall.py", line 378, in remove
    moved.stash(path)
    ~~~~~~~~~~~^^^^^^
  File "C:\Program Files\Python314\Lib\site-packages\pip\_internal\req\req_uninstall.py", line 269, in stash
    renames(path, new_path)
    ~~~~~~~^^^^^^^^^^^^^^^^
  File "C:\Program Files\Python314\Lib\site-packages\pip\_internal\utils\misc.py", line 378, in renames
    shutil.move(old, new)
    ~~~~~~~~~~~^^^^^^^^^^
  File "C:\Program Files\Python314\Lib\shutil.py", line 940, in move
    rmtree(src)
    ~~~~~~^^^^^
  File "C:\Program Files\Python314\Lib\shutil.py", line 852, in rmtree
    _rmtree_impl(path, dir_fd, onexc)
    ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^
  File "C:\Program Files\Python314\Lib\shutil.py", line 705, in _rmtree_unsafe
    onexc(os.unlink, fullname, err)
    ~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Program Files\Python314\Lib\shutil.py", line 701, in _rmtree_unsafe
    os.unlink(fullname)
    ~~~~~~~~~^^^^^^^^^^
PermissionError: [WinError 5] Access is denied: 'c:\\program files\\python314\\lib\\site-packages\\psutil-6.1.1.dist-info\\licenses\\LICENSE'
PS D:\data\zchat> python -m pip install --no-cache-dir --only-binary=:all: psutil
Defaulting to user installation because normal site-packages is not writeable
Requirement already satisfied: psutil in C:\Program Files\Python314\Lib\site-packages (6.1.1)
PS D:\data\zchat>

## Response:
10/16/2026, 10:20:54 PM · gpt-6-thinking

## Root Cause ยืนยันแล้ว: Global Python ไม่มีสิทธิ์แก้ไข Package

จาก Log ล่าสุดพบปัญหา 2 ส่วน\:

1. **`psutil 6.1.1` ติดตั้งอยู่ใน `C:\Program Files\Python314`** ซึ่งบัญชี Windows ปัจจุบันไม่มีสิทธิ์แก้ไข จึงเกิด `WinError 5: Access is denied`
2. `pip install` เห็น Metadata ของ `psutil 6.1.1` อยู่แล้ว จึงแสดง `Requirement already satisfied` แม้ Native Extension `psutil._psutil_windows` จะไม่สามารถ Import ได้

**วิธีแก้ที่แนะนำ\:** ใช้ Virtual Environment แยกสำหรับ ZChat โดยไม่แก้ไข Global Python และไม่ต้องเปิด PowerShell แบบ Administrator

## 1\. ติดตั้ง Python Runtime ใหม่แบบ Isolated

คัดลอกคำสั่งทั้งหมดนี้ไปรันใน PowerShell\:

```powershell
cd D:\data\zchat

# Create isolated Python environment without global packages
py -3.14 -m venv .venv-runtime

$py = "D:\data\zchat\.venv-runtime\Scripts\python.exe"

# Confirm isolation
& $py -c "import sys; print(sys.executable); print(sys.prefix)"

# Upgrade environment tools
& $py -m pip install --upgrade pip setuptools wheel

# Install Windows runtime dependencies
& $py -m pip install --no-cache-dir --only-binary=:all: `
    --upgrade psutil pywinauto pywin32

# Verify actual native module loading
& $py -c "import psutil; import psutil._psutil_windows; from pywinauto import Desktop; print('PASS: Windows runtime dependencies loaded'); print('psutil:', psutil.__version__)"
```

**Expected Result\:**

```text
PASS: Windows runtime dependencies loaded
psutil: <installed version>
```

หากคำสั่งสุดท้ายผ่าน แสดงว่าแก้ปัญหาการ Import Native Extension สำเร็จใน Environment ใหม่แล้ว

## 2\. ตรวจ Camfrog Windows Client จริง

รันต่อด้วย Python Environment ใหม่\:

```powershell
@'
import psutil
from pywinauto import Desktop
from datetime import datetime

TARGET = "camfrog video chat.exe"

for proc in psutil.process_iter(["pid", "name", "exe", "create_time"]):
    try:
        if (proc.info["name"] or "").casefold() != TARGET:
            continue

        pid = proc.info["pid"]

        print("=" * 60)
        print("PID:", pid)
        print("Executable:", proc.info["exe"])
        print("Started:", datetime.fromtimestamp(proc.info["create_time"]).astimezone().isoformat())

        windows = Desktop(backend="uia").windows(
            process=pid,
            visible_only=True
        )

        for window in windows:
            print({
                "HWND": window.handle,
                "Title": window.window_text(),
                "Class": window.class_name(),
                "PID": window.process_id()
            })

    except (
        psutil.NoSuchProcess,
        psutil.AccessDenied,
        psutil.ZombieProcess
    ) as exc:
        print("Process unavailable:", type(exc).__name__)

'@ | & $py -
```

สคริปต์นี้เป็น **Read-only** ไม่ส่งข้อความ ไม่ Join Room และไม่ปิด Camfrog

## 3\. ป้องกันปัญหา Global Python ในอนาคต

เพิ่ม `.venv-runtime/` ลงใน `.gitignore` ถ้ายังไม่มี เพื่อไม่ให้ Commit Python Environment เข้า GitHub

ตรวจสอบก่อน\:

```powershell
cd D:\data\zchat

git check-ignore .venv-runtime/

Get-Content .gitignore |
    Select-String "venv"
```

หากยังไม่มี Rule\:

```powershell
Add-Content .gitignore "`n.venv-runtime/"
```

การแก้ไขนี้เป็นเพียง Local Configuration ยังไม่ต้อง Commit หรือ Push

## 4\. สถานะระบบหลังการวิเคราะห์

| Component | Status |
|--------|--------|
| Camfrog 8.5.0.51219 | Process และ Signature ตรวจพบแล้ว |
| Camfrog PID 21992 | Verified ณ Snapshot ก่อนหน้า |
| Python 3.14 | ทำงานได้ |
| Global psutil 6.1.1 | Import เสีย / Permission Denied |
| Isolated Virtual Environment | รอติดตั้งและทดสอบ |
| ZChat Windows Discovery | รอ Runtime Test |
| Real Camfrog Integration | ยังไม่ผ่าน E2E |

**ไม่ควรลบ `C:\Program Files\Python314` หรือบังคับเปลี่ยน Permission ของ Global Python** เพราะจะกระทบ Project อื่นโดยไม่จำเป็น

เมื่อ `PASS: Windows runtime dependencies loaded` ปรากฏแล้ว จะสามารถตรวจสอบ HWND, PID และ Window Class ของ Camfrog ตัวจริง เพื่อแก้ปัญหาการเลือก Window ผิดใน `room_control_gui.py` ต่อได้

## Prompt:
10/16/2026, 10:23:33 PM

PS D:\data\zchat> python -m pip install --no-cache-dir --only-binary=:all: psutil
Defaulting to user installation because normal site-packages is not writeable
Requirement already satisfied: psutil in C:\Program Files\Python314\Lib\site-packages (6.1.1)
PS D:\data\zchat> python -c "import psutil; print('psutil:', psutil.__version__)"
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import psutil; print('psutil:', psutil.__version__)
    ^^^^^^^^^^^^^
  File "C:\Program Files\Python314\Lib\site-packages\psutil\__init__.py", line 110, in <module>
    from . import _pswindows as _psplatform
  File "C:\Program Files\Python314\Lib\site-packages\psutil\_pswindows.py", line 35, in <module>
    from ._psutil_windows import ABOVE_NORMAL_PRIORITY_CLASS
ModuleNotFoundError: No module named 'psutil._psutil_windows'
PS D:\data\zchat> python -c "from pywinauto import Desktop; print('pywinauto: OK')"
pywinauto: OK
PS D:\data\zchat> @'
>> from pywinauto import Desktop
>>
>> CAMFROG_PID = 21992
>>
>> windows = Desktop(backend="uia").windows(
>>     process=CAMFROG_PID,
>>     visible_only=True
>> )
>>
>> print(f"Camfrog PID: {CAMFROG_PID}")
>> print(f"Windows found: {len(windows)}")
>>
>> for window in windows:
>>     print({
>>         "handle": window.handle,
>>         "title": window.window_text(),
>>         "class": window.class_name(),
>>         "visible": window.is_visible(),
>>     })
>> '@ | python -
Camfrog PID: 21992
Windows found: 3
{'handle': 5177812, 'title': 'REPLACE_ME_ACCOUNT (status)', 'class': '#32770', 'visible': True}
{'handle': 33360162, 'title': 'REPLACE_ME_ROOM: ห้องสนทนา', 'class': '#32770', 'visible': True}
{'handle': 3149540, 'title': 'Camfrog Video Chat', 'class': '#32770', 'visible': True}
PS D:\data\zchat> Get-Process -Name "Camfrog Video Chat" |
>>     Select-Object Id, StartTime, MainWindowHandle, MainWindowTitle, Path |
>>     Format-List

Id               : 21992
StartTime        : 16/10/2569 21:21:56
MainWindowHandle : 5177812
MainWindowTitle  : REPLACE_ME_ACCOUNT (status)
Path             : C:\Users\REPLACE_ME\AppData\Local\Programs\Camfrog Video Chat\Camfrog Video Chat.ex
                   e

PS D:\data\zchat> cd D:\data\zchat
PS D:\data\zchat>
PS D:\data\zchat> py -3.14 -m venv .venv-runtime
PS D:\data\zchat>
PS D:\data\zchat> .\.venv-runtime\Scripts\python.exe -m pip install --upgrade pip
Requirement already satisfied: pip in .\.venv-runtime\Lib\site-packages (26.2.1)
PS D:\data\zchat>
PS D:\data\zchat> .\.venv-runtime\Scripts\python.exe -m pip install `
>>     --only-binary=:all: psutil pywinauto
Collecting psutil
  Downloading psutil-7.2.2-cp37-abi3-win_amd64.whl.metadata (22 kB)
Collecting pywinauto
  Using cached pywinauto-0.6.9-py2.py3-none-any.whl.metadata (2.0 kB)
Collecting six (from pywinauto)
  Using cached six-1.17.0-py2.py3-none-any.whl.metadata (1.7 kB)
Collecting comtypes (from pywinauto)
  Using cached comtypes-1.4.17-py3-none-any.whl.metadata (7.8 kB)
Collecting pywin32 (from pywinauto)
  Using cached pywin32-312-cp314-cp314-win_amd64.whl.metadata (11 kB)
Downloading psutil-7.2.2-cp37-abi3-win_amd64.whl (137 kB)
Using cached pywinauto-0.6.9-py2.py3-none-any.whl (363 kB)
Using cached comtypes-1.4.17-py3-none-any.whl (298 kB)
Using cached pywin32-312-cp314-cp314-win_amd64.whl (7.0 MB)
Using cached six-1.17.0-py2.py3-none-any.whl (11 kB)
Installing collected packages: six, pywin32, psutil, comtypes, pywinauto
Successfully installed comtypes-1.4.17 psutil-7.2.2 pywin32-312 pywinauto-0.6.9 six-1.17.0
PS D:\data\zchat>
PS D:\data\zchat> .\.venv-runtime\Scripts\python.exe -c `
>>     "import psutil; from pywinauto import Desktop; print('Runtime dependencies OK')"
Runtime dependencies OK
PS D:\data\zchat>

## Response:
10/16/2026, 10:23:40 PM · gpt-6-thinking

## ZChat Windows Runtime - ตรวจสอบผ่านแล้ว

จากผลการทดสอบล่าสุด **แก้ปัญหา `psutil._psutil_windows` สำเร็จแล้ว** โดยใช้ Python Virtual Environment แยกจาก Global Python 3.14

**Isolated Python Runtime** (PASS)

**psutil 7.2.2** (PASS)

**pywinauto 0.6.9** (PASS)

**Real Camfrog Window Discovery** (PASS)

**ZChat End-to-End Integration** (Not verified)

## 1\. พบ Camfrog Windows 3 หน้าต่างใน Process เดียว

| HWND | Window Title | PID |
|--------|--------|--------|
| `5177812` | `REPLACE_ME_ACCOUNT (status)` | 21992 |
| `33360162` | `REPLACE_ME_ROOM: ห้องสนทนา` | 21992 |
| `3149540` | `Camfrog Video Chat` | 21992 |

ทั้งสามหน้าต่างอยู่ภายใต้ Camfrog Main Process เดียวกัน

**ข้อสรุปสำคัญ\:** ZChat ต้องรองรับหลายหน้าต่างภายใน Process เดียว ไม่ใช่สรุปว่าเป็นหลาย Camfrog Instances

นี่สอดคล้องกับปัญหาที่เคยพบใน `room_control_gui.py` ซึ่งใช้ `window_title_regex` ในการค้นหา Window

## 2\. Architecture ที่ควรนำไปใช้

```text
Real Camfrog Video Chat.exe
PID 21992
│
├── Account/Buddy Window
│   HWND 5177812
│   Title: REPLACE_ME_ACCOUNT (status)
│
├── Room Window
│   HWND 33360162
│   Title: REPLACE_ME_ROOM: ห้องสนทนา
│
└── Camfrog Window
    HWND 3149540
    Title: Camfrog Video Chat
         │
         ▼
ZChat Windows Runtime Adapter
         │
         ├── Process Identity Verification
         ├── Window Discovery
         ├── Window Role Classification
         ├── Safe Window Selection
         └── State Observation
         │
         ▼
ZChat Control Server
```

การจัดประเภทหน้าต่างด้านบนเป็นการจัดกลุ่มเบื้องต้นจาก Title เท่านั้น โดยเฉพาะหน้าต่าง `Camfrog Video Chat` ยังต้องตรวจ UI Elements เพื่อระบุบทบาทที่แน่นอน

## 3\. ขั้นตอนต่อไป - Real Window Role Inspection

ให้ใช้ Python Environment ที่ติดตั้งสำเร็จแล้วเพื่อตรวจ Window Class, Title และ UI Controls แบบ Read-only

```powershell
cd D:\data\zchat

$py = ".\.venv-runtime\Scripts\python.exe"

@'
from pywinauto import Desktop
import psutil

TARGET = "camfrog video chat.exe"

for proc in psutil.process_iter(
    ["pid", "name", "exe", "create_time"]
):
    try:
        if (proc.info["name"] or "").casefold() != TARGET:
            continue

        pid = proc.info["pid"]
        windows = Desktop(backend="uia").windows(
            process=pid,
            visible_only=True
        )

        print(f"\nCamfrog PID: {pid}")

        for win in windows:
            print("=" * 60)
            print("HWND:", win.handle)
            print("Title:", win.window_text())
            print("Class:", win.class_name())

            # Inspect metadata only; do not click or modify controls
            for child in win.descendants()[:40]:
                try:
                    info = child.element_info
                    print({
                        "name": info.name,
                        "control_type": info.control_type,
                        "class_name": info.class_name,
                        "automation_id": info.automation_id,
                    })
                except Exception:
                    continue

    except (
        psutil.NoSuchProcess,
        psutil.AccessDenied
    ):
        continue
'@ | & $py -
```

คำสั่งนี้ไม่คลิก ไม่ส่งข้อความ และไม่เปลี่ยน Camfrog State แต่ **ชื่อ UI Controls อาจแสดงข้อมูลบัญชีหรือข้อความส่วนตัว** จึงควรปกปิดก่อนเผยแพร่รายงาน

## 4\. กฎที่ควรใช้แก้ `cvsz/zchat`

สำหรับ `room_control_gui.py` และ Windows Adapter\:

1. Identify process ด้วย Executable Path, Signature, PID และ Creation Time
2. Allow multiple windows belonging to the same verified process
3. Select windows by verified role ไม่ใช่ Title Regex อย่างเดียว
4. Fail closed เมื่อเจอหลาย Process ที่แยก Identity ไม่ได้
5. Revalidate HWND และ Process Identity ก่อน Execute
6. ห้าม Terminate Process ที่ ZChat ไม่ได้เป็นเจ้าของ
7. บันทึก `WINDOW_FOUND` แยกจาก `AUTHENTICATED` และ `ROOM_JOINED`

**สถานะล่าสุด\:** Windows Runtime Dependencies และ Camfrog Process/Window Discovery ผ่านแล้ว ขั้นตอนถัดไปคือยืนยันบทบาทของทั้งสามหน้าต่างและทดสอบการเลือกหน้าต่างของ ZChat โดยตรง ก่อนเปิดใช้งาน Real Client Actions

## Prompt:
10/16/2026, 10:26:20 PM

[Attachment: ข้อความที่วาง (1)(20261016-152615).txt]

## Response:
10/16/2026, 10:26:21 PM · gpt-6-thinking

## ZChat - Real Camfrog UI Inspection Results

วิเคราะห์ Runtime Log ล่าสุดแล้ว พบหลักฐานที่สำคัญสำหรับพัฒนา `cvsz/zchat` ให้ทำงานร่วมกับ **Camfrog Video Chat 8.5.0.51219** ผ่าน Windows UI Automation โดยไม่ต้อง Decompile Executable

### 1\. ผลตรวจสอบ

**Python Runtime / psutil** (PASS)

**Real Camfrog Process** (Verified)

**Windows UI Elements** (Discovered)

**Room Membership** (Unverified)

ตรวจพบ Camfrog Main Process `21992` ซึ่งมี 3 หน้าต่างภายใต้ Process เดียวกัน

| HWND | Window role (เบื้องต้น) | Evidence |
|--------|--------|--------|
| `5177812` | Account / IM history | `wb-log-im-data.inside` |
| `33360162` | Room Chat | `wb-log-room-data.inside` |
| `3149540` | Main Client / Directory | `CTreeViewTS`, `CComboBoxTS` |

### 2\. ข้อค้นพบสำคัญจาก UI Automation

**Account / IM Window**

พบ `Internet Explorer_Server` ที่แสดง `camfrog://wb-log-im-data.inside/` และมี Text Elements ของประวัติ IM อยู่ภายใน ยืนยันได้ว่า UI Automation สามารถมองเห็นองค์ประกอบของหน้า IM ได้ แต่ยังไม่ได้พิสูจน์ว่าส่งข้อความผ่าน UI สำเร็จ

**Room Window**

พบ `VideoViewport` และ `camfrog://wb-log-room-data.inside/` ซึ่งเป็นหลักฐานที่ชัดเจนว่าหน้าต่างดังกล่าวมี Room UI และแสดงประวัติสนทนา

อย่างไรก็ตาม Log มีข้อความย้อนหลังเกี่ยวกับการถูกนำออกจากห้องเนื่องจากไม่มีการใช้งาน จึงไม่สามารถใช้ข้อความในประวัติมายืนยันว่าปัจจุบันยังอยู่ในห้องได้

**Main Client Window**

พบ `CTreeViewTS`, `CComboBoxTS`, `Edit` รวมถึงปุ่มที่มีชื่อ `ออนไลน์` แสดงว่า UI Automation เข้าถึงโครงสร้างบางส่วนของ Client ได้

ชื่อ `ออนไลน์` เป็นชื่อ Control ไม่ใช่หลักฐานโดยตรงว่าบัญชีออนไลน์อยู่ในขณะนั้น

หลักฐาน: Windows UI Inspection ที่ส่งมา fileciteturn15file0L114-L224

## 3\. Root Cause ที่ควรแก้ใน ZChat

จากหลักฐานนี้ ยืนยันได้ว่า **การใช้ Window Title หรือ Window Class เพียงอย่างเดียวไม่เพียงพอ** เพราะทั้งสามหน้าต่างใช้ Class `#32770` และอยู่ใน PID เดียวกัน

ควรออกแบบ Window Selection ดังนี้\:

```text
CamfrogProcessDiscovery
    |
    +-- Verify executable and process identity
    |
    +-- Enumerate windows by PID
    |
    +-- Inspect window UI signatures
    |     |
    |     +-- IM history:
    |     |    wb-log-im-data.inside
    |     |
    |     +-- Room history:
    |     |    wb-log-room-data.inside
    |     |    VideoViewport
    |     |
    |     +-- Main directory:
    |          CTreeViewTS
    |          CComboBoxTS
    |
    +-- Classify window roles
    |
    +-- Revalidate HWND / PID
    |
    +-- Execute authorized action
    |
    +-- Verify observed outcome
```

## 4\. Implementation Prompt สำหรับ `cvsz/zchat`

**standard: **

# ZChat - Real Camfrog 8.5 Windows UI Runtime Integration

Repository: https://github.com/cvsz/zchat

Implement reliable, evidence-driven Windows UI integration using the genuine installed Camfrog Video Chat 8.5.0.51219 client.

Verified environment:
- Windows 11
- Python 3.14 isolated virtual environment
- psutil 7.2.2
- pywinauto 0.6.9
- Valid Camfrog LLC Authenticode signature
- Multiple top-level windows under one Camfrog main process

Observed UI signatures:

1. IM history window:
   - Internet Explorer_Server
   - camfrog://wb-log-im-data.inside/

2. Room window:
   - VideoViewport
   - Internet Explorer_Server
   - camfrog://wb-log-room-data.inside/

3. Main client / directory:
   - CTreeViewTS
   - CComboBoxTS
   - Native Edit controls

## Objectives

1. Inspect existing repository architecture and tests.
2. Implement WindowsCamfrogProcessDiscovery.
3. Match executable identity, PID, process creation time, and verified publisher.
4. Exclude CEF subprocesses and ZChat's own windows.
5. Support multiple windows associated with one verified Camfrog process.
6. Create WindowsCamfrogWindowClassifier using observed structural UI signatures.
7. Implement fail-closed handling for ambiguous window roles or process identities.
8. Add read-only attachment to an already-running authorized client.
9. Revalidate process and window identity before actions.
10. Preserve ownership restrictions: never terminate a client process not launched by the agent.
11. Separate process-running, UI-visible, account-authenticated, and room-member states.
12. Use Windows UI Automation without modifying Camfrog binaries or undocumented network protocols.
13. Do not collect or persist private message bodies during general-purpose window discovery.
14. Add sanitized runtime diagnostics, regression tests, and Windows acceptance tests.
15. Maintain backward compatibility with existing ZChat applications and adapters.

## Evidence Rules

- A process being alive does not establish authentication.
- A room window existing does not establish current room membership.
- Historical messages do not prove current activity.
- A UI control labelled Online does not establish current presence.
- An accepted URI handoff does not establish completed behavior.
- UI Automation success is not equivalent to successful server-side execution.

## Verification

Require:
- Correct executable verification
- Stable process discovery
- Correct role classification
- No cross-process targeting
- No unintended clicks or keystrokes
- No unrelated process termination
- No private data in discovery logs
- Unit and Windows runtime integration tests
- Recorded evidence for each acceptance condition

Deliver a documented implementation, actual test results, changed files, remaining blockers, and production readiness assessment.

Do not claim completed integration without successful real-client acceptance evidence.

## 5\. ข้อควรระวังด้านข้อมูลส่วนตัว

Runtime Log ที่ส่งมามีข้อความ IM, ประวัติสนทนา และข้อมูลที่ผู้ใช้อื่นแสดงใน Contact List รวมถึงข้อมูลติดต่อบางรายการ

**ไม่แนะนำให้ Commit Raw UI Dump นี้ลง Public GitHub Repository** ควรใช้ Sanitized Fixtures โดยลบข้อมูลระบุตัวบุคคลและข้อความสนทนาจริงก่อน

อีกหนึ่งจุด: Log ยืนยันว่า `.venv-runtime/` ถูก `git check-ignore` แล้ว ก่อนเพิ่ม Rule ซ้ำใน `.gitignore` จึงควรตรวจ `git diff -- .gitignore` และลบบรรทัดที่ซ้ำหากมี

### สรุป

ตอนนี้มีหลักฐานเพียงพอสำหรับเริ่มพัฒนา **Windows Process Discovery + Window Role Classification** จาก Client จริงได้แล้ว

แต่ยังไม่มีหลักฐานเพียงพอสำหรับยืนยัน Login, Room Membership, Message Delivery หรือ Live Camfrog API Integration จึงควรเริ่มจาก Read-only Runtime Adapter ก่อนเปิดใช้งานคำสั่งที่เปลี่ยนสถานะของบัญชีหรือส่งข้อความจริง

## Prompt:
10/16/2026, 10:41:34 PM

เมื่อแก้ไขแล้ว Status Changer source code เป้นไง บ้าง เพราะตอนนี้ ไม่สามารถทำงาน เบื้องหลัง โดยไม่ต้องเปิดหน้าต่าง camfrog ได้ ซึ่งทำให้ รบกวนการใฃ้งาน mouse+keyboard

## Response:
10/16/2026, 10:41:38 PM · gpt-6-thinking

ผมจะตรวจ Source Code ของ Status Changer ใน `cvsz/zchat` ว่าปัจจุบันใช้วิธีควบคุม Camfrog แบบไหน และส่วนใดที่ทำให้ต้องเปิดหน้าต่างหรือแย่ง Mouse/Keyboard แล้วสรุปแนวทางแก้ที่ทำได้จริงโดยไม่รบกวน Desktop ครับ

> **วิเคราะห์โค้ด GUI และตรวจสอบความปลอดภัยของสถานะแชต**
>
> 
>
> ประมวลผล 52s

## ZChat Status Changer - Source Code Audit

ผมตรวจ Source Code ล่าสุดจาก [github.com](https://github.com/cvsz/zchat?utm_source=chatgpt.com) แล้ว พบว่า **Status Changer มีโค้ดสำหรับทำงานเบื้องหลังอยู่แล้ว แต่ยังมีจุดที่ทำให้แย่ง Focus, ใช้ Keyboard/Mouse และไม่สามารถยืนยันได้ว่าเปลี่ยน Status สำเร็จขณะ Camfrog ถูกซ่อนอยู่**

ปัญหาหลักไม่ใช่ Python หรือ `psutil` อีกต่อไป แต่เป็นวิธีการส่ง Status ไปยัง Camfrog Client

### ผลตรวจสอบ

| Component | สถานะ | ปัญหาที่พบ |
|--------|--------|--------|
| Windows Client Discovery | มี Implementation | ยังพึ่งพา Window Title |
| Background Window Discovery | รองรับ | ค้นหา Hidden/Minimized Windows ได้ แต่ยังไม่รับประกันว่าควบคุมได้ |
| Status Edit | มี Implementation | ใช้ `WM_SETTEXT` และตรวจ Read-back |
| Background Submit | Experimental | ใช้ `PostMessage` ส่ง Enter |
| Foreground Fallback | ยังมี | เรียก `set_focus()` และ `type_keys()` |
| Mouse Interaction | ยังมี | บางเส้นทางเรียก `click_input()` |
| Background Success Verification | ไม่ครบ | ตรวจ Text แต่ยังไม่ยืนยัน Server-side Status |
| Silent Operation | มีปัญหา | มีโค้ดแก้ Windows Sound Registry ชั่วคราว |

### จุดที่ต้องแก้ก่อน

**P0 - กำจัด Foreground Input ออกจาก Background Mode**

ไฟล์ `status_changer_gui.py` มีการเรียก\:

```python
win.set_focus()
ctrl.set_focus()
ctrl.type_keys("{ENTER}")
btn.click_input()
```

คำสั่งเหล่านี้สามารถรบกวนหน้าต่างที่กำลังใช้งานอยู่ได้

แม้โค้ดจะมี `background_submit` แล้ว แต่ยังมีบางเส้นทางที่นำ Camfrog กลับมาเป็น Foreground

**P0 - ไม่ควรแก้ System Sound Registry**

ฟังก์ชัน `_background_enter()` มีการเปลี่ยน Registry ภายใต้\:

```text
HKEY_CURRENT_USER\AppEvents\Schemes\Apps\.Default
```

เพื่อปิดเสียงชั่วคราว แล้วพยายาม Restore ภายหลัง วิธีนี้ส่งผลต่อการตั้งค่าเสียงของ Windows ในระดับผู้ใช้ และอาจเกิด Race Condition ระหว่างหลาย Worker ได้

ควรถอด Logic นี้ออก และแก้สาเหตุที่ทำให้เกิดเสียงแทน

**P0 - Background Submit ยังไม่ผ่าน Real Acceptance**

โค้ดมีคำอธิบายว่า `CComboBoxTS` เป็น Experimental Target สำหรับรับ Enter ผ่าน `PostMessage`

จาก Runtime Evidence ของ Camfrog 8.5 พบว่า\:

- `CComboBoxTS`\: Automation ID `1436`
- `Edit`\: Automation ID `1001`
- Main Process มีหลายหน้าต่าง

แต่ยังไม่มีหลักฐานว่าการส่ง `WM_KEYDOWN/WM_KEYUP` ไปยัง ComboBox ขณะ Camfrog ถูก Minimize จะทำให้ Status เปลี่ยนจริง

## Architecture ที่ควรแก้ให้เป็น True Background Mode

```text
ZChat Status Changer
         |
         v
Background Status Worker
         |
         +-- Verify Camfrog Process Identity
         |
         +-- Locate Status Window
         |     CComboBoxTS / 1436
         |       └── Edit / 1001
         |
         +-- Write Status without Foreground
         |
         +-- Verify Edit Read-back
         |
         +-- Submit via Validated Background Method
         |
         +-- Verify Status Was Actually Applied
         |
         +-- Report Success / Failure / Unknown
         |
         +-- Never Steal Mouse or Keyboard
```

ต้องแยกความหมายของ Background Mode ออกเป็นสองระดับ\:

- **No-focus background\:** Camfrog ยังทำงานอยู่ แต่ผู้ใช้สามารถใช้งานโปรแกรมอื่นได้โดยไม่ถูกรบกวน
- **Hidden/minimized background\:** Camfrog ถูกซ่อนหรือ Minimize และ Status Changer ยังทำงานได้

ระดับแรกมีแนวทางจาก Source Code ที่พร้อมนำไปทดสอบ ส่วนระดับที่สองยังต้องยืนยันกับ Camfrog 8.5 จริง เพราะบาง UI Controls ไม่ประมวลผล Windows Messages ขณะ Hidden หรือ Minimized

## 2\. Configuration ที่ควรปรับ

ปัจจุบัน Default Configuration ใน `status_changer_gui.py` ยังเป็น\:

```python
"safety": {
    "require_foreground": True,
    "restore_previous_window": True,
}
```

สำหรับ Background Worker ควรใช้ Configuration ที่แยกจาก Interactive Mode เช่น\:

```json
{
  "status": {
    "enabled": true,
    "background_mode": "strict",
    "background_enter_target": "combo",
    "verify_result": true
  },
  "safety": {
    "require_foreground": false,
    "restore_previous_window": false,
    "allow_focus_stealing": false,
    "allow_mouse_injection": false,
    "allow_keyboard_injection": false,
    "allow_system_sound_changes": false
  }
}
```

นี่คือ **Proposed Configuration Contract** ไม่ใช่ Schema ที่ยืนยันว่า Repository รองรับทุก Field แล้ว ต้องเพิ่ม Validation และ Enforcement ในโค้ดก่อนนำไปใช้งาน

ถ้า Background Submit ใช้ไม่ได้ ให้แสดง `BACKGROUND_UNSUPPORTED` แทนการกลับไปใช้ Foreground Input อัตโนมัติ

## 3\. Codex Implementation Prompt

**standard: **

# ZChat Status Changer - True Background Execution Repair

Repository: cvsz/zchat

## Objective

Refactor all Status Changer variants to perform status updates without stealing Windows focus, mouse input, keyboard input, clipboard contents, or changing system sound settings.

Target real Camfrog version: 8.5.0.51219.

## Scope

Inspect and repair:

- status_changer_gui.py
- status_random_gui.py
- status_marquee_gui.py
- camfrog_status_gui.py
- Shared status engine and configuration
- Windows integration tests
- Build and packaging scripts

## Requirements

### 1. Process and Window Selection

- Identify Camfrog through verified executable identity.
- Associate windows with PID and creation time.
- Support multiple windows belonging to the same process.
- Select status controls using validated UI signatures.
- Support hidden and minimized windows where the real client permits.
- Reject ambiguous process/window selection.

### 2. Strict Background Input

Implement a dedicated background execution path.

In strict background mode, prohibit:

- set_focus()
- click_input()
- type_keys()
- keyboard.send_keys()
- SetForegroundWindow()
- Synthetic global mouse input
- Synthetic global keyboard input
- Clipboard modification
- Global Windows sound setting modification

The background path must never silently fall back to interactive automation.

### 3. Status Editing and Submission

- Resolve the verified status Edit control.
- Verify its parent CComboBoxTS identity.
- Attempt non-focus text setting through supported UI Automation or native control operations.
- Validate exact text read-back.
- Test the observed ComboBox submission behavior against the real Camfrog client.
- Use bounded timeouts and explicit failure states.
- Do not assume successful PostMessage means status was applied.

### 4. Result Verification

Differentiate:

- TEXT_WRITTEN
- SUBMIT_DISPATCHED
- VERIFIED_APPLIED
- FAILED
- UNKNOWN
- BACKGROUND_UNSUPPORTED

Never report VERIFIED_APPLIED solely because a Windows API call returned success.

### 5. Remove Sound Registry Mutation

Remove temporary modifications of HKCU AppEvents sound settings.

Do not disable Windows security notifications or system-wide sound events.

Prevent unnecessary sound generation through the correct interaction mechanism instead.

### 6. Regression Tests

Verify:

- User's foreground window never changes.
- Cursor coordinates remain unchanged.
- Active keyboard focus remains unchanged.
- Clipboard is unchanged.
- Hidden/minimized client behavior is tested separately.
- Multiple Camfrog windows are classified correctly.
- Failure never triggers foreground fallback.
- No duplicate status submission.
- Random and Marquee modes follow the same safety policy.
- Application-specific sounds are not triggered by background submission.

### 7. Deliverables

- Root cause analysis
- Minimal safe refactor
- Shared background status engine
- Backward-compatible configuration migration
- Unit tests
- Native Windows acceptance tests
- Actual Camfrog 8.5 runtime evidence
- Updated Windows builds
- SHA256 manifests
- Documented limitations

Do not claim production readiness until actual status changes are verified while another application retains focus.

Do not modify third-party binaries or use undocumented private authentication endpoints.

Preserve existing repository governance and submit changes through a reviewed Pull Request.

## 4\. Acceptance Test ที่ต้องผ่านจริง

ทดสอบขณะเปิด VS Code หรือ Browser และกำลังใช้ Mouse/Keyboard ตามปกติ

| Test | Expected |
|--------|--------|
| Camfrog เปิดอยู่เบื้องหลัง | Status เปลี่ยนโดยไม่แย่ง Focus |
| Camfrog Minimized | เปลี่ยนได้ หรือรายงาน Unsupported |
| Camfrog Hidden to Tray | เปลี่ยนได้ หรือรายงาน Unsupported |
| Random Status ทำงานต่อเนื่อง | ไม่มีการแย่ง Keyboard |
| Marquee Status ทำงานต่อเนื่อง | ไม่มี Mouse Movement หรือ Focus Stealing |
| Background Submit ล้มเหลว | ไม่เปิดหน้าต่าง Camfrog เอง |
| Status Applied | มีหลักฐานว่า Status เปลี่ยนจริง |

**ข้อสรุป\:** จาก Source Code ที่ตรวจพบ มีแนวทางแก้โดยไม่ต้อง Decompile Camfrog ก่อน แต่ยังรับประกันไม่ได้ว่าจะเปลี่ยน Status ได้ขณะซ่อน Client ทุกกรณี เพราะต้องทดสอบพฤติกรรมของ Native ComboBox จริง

การเปลี่ยนแปลงที่ควรทำก่อนที่สุดคือ **Strict No-Focus Mode + Remove Registry Sound Mutation + Verified Background Submission** และนำไปใช้ร่วมกันทั้ง `status-changer`, `status-random` และ `status-marquee`

ขณะนี้ผมตรวจ Source Code แล้ว แต่ยังไม่ได้แก้ Commit หรือ Build Executable ชุดใหม่ใน Repository นี้

## Prompt:
10/16/2026, 10:44:21 PM

merged 2 prompt to single

## Response:
10/16/2026, 10:44:24 PM · gpt-6-thinking

รวม 2 Prompts ให้เป็น **Single Ultimate Master Prompt** สำหรับ Codex โดยครอบคลุมทั้ง **Real Camfrog 8.5 Windows Client Integration** และ **True Background Status Changer** ที่ไม่รบกวน Mouse, Keyboard, Clipboard, Window Focus หรือเสียงของ Windows

Prompt นี้ออกแบบสำหรับ Repository [github.com](https://github.com/cvsz/zchat?utm_source=chatgpt.com) โดยให้ Codex ตรวจสอบ Source Code เดิม แก้ไข Root Cause, Refactor, Implement, Test, Build และส่งมอบหลักฐานจริง ภายใต้ GitHub Governance

**document: **

# ZChat - Ultimate Master Prompt
## Real Camfrog Windows Integration + True Background Status Automation

**Repository:** `https://github.com/cvsz/zchat`  
**Target:** Camfrog Video Chat `8.5.0.51219`  
**Platform:** Windows 11 / Python 3.14  
**Execution Model:** Autonomous Production Engineering  
**Engineering Standard:** Evidence-Driven, Security-First, Production-Oriented

---

# 1. ROLE AND MISSION

Act as an autonomous multidisciplinary engineering team consisting of:

- Principal Software Architect
- Senior Windows Runtime Engineer
- Senior Python Engineer
- Windows UI Automation Engineer
- Security Auditor
- Reverse Engineering Researcher
- QA Automation Engineer
- DevOps and Release Engineer

Your mission is to investigate, repair, refactor, integrate, test, and package the existing ZChat system so that it can reliably interact with the genuine Camfrog Windows client.

The primary requirement is **true background status automation without interfering with the user's active desktop session**.

Do not replace working functionality unnecessarily.

Do not claim success without actual verification evidence.

# 2. MANDATORY OPERATING RULES

1. Read `AGENTS.md`, `CLAUDE.md`, architecture documents, repository governance, and existing implementation contracts before making changes.
2. Investigate the entire relevant execution path rather than modifying isolated functions without understanding their callers.
3. Preserve existing working features and configuration compatibility.
4. Prefer the smallest maintainable change that resolves the root cause.
5. Never fabricate runtime results, test passes, screenshots, commits, or deployment status.
6. Never modify, patch, inject into, or redistribute the proprietary Camfrog binary.
7. Use authorized Windows UI Automation and official integration interfaces.
8. Never bypass authentication, CAPTCHA, account restrictions, licensing, or third-party security controls.
9. Do not collect or persist authentication secrets or private chat contents during general-purpose discovery.
10. Keep technical source code, tests, comments, documentation, commits, and PR descriptions in English.
11. Provide progress reports and explanations to the operator in Thai.
12. Fail closed when an operation cannot be performed without violating background execution constraints.

# 3. VERIFIED RUNTIME BASELINE

The following values originate from a real Camfrog 8.5 runtime observation.

```text
Application: Camfrog Video Chat
Version: 8.5.0.51219
Publisher: Camfrog LLC
Authenticode: Valid
SHA256:
0B744602C004536DCF81E9965E8CB17358EB276B3876A1E70C50F72777C27E06

Observed Main PID: 21992
Observed Window Class: #32770

Windows:
5177812  | Account / IM observation
33360162 | Room UI observation
3149540  | Main client / directory
```

These PID and HWND values are historical observations, not permanent identifiers.

Never hardcode them as production selectors.

Discover and revalidate process identities at runtime.

## Observed UI signatures

### Account / IM History

```text
Internet Explorer_Server
camfrog://wb-log-im-data.inside/
```

### Room UI

```text
VideoViewport
Internet Explorer_Server
camfrog://wb-log-room-data.inside/
```

### Main Client / Directory

```text
CComboBoxTS
Automation ID: 1436

Edit
Automation ID: 1001

CTreeViewTS
```

These structures are observation signatures, not guaranteed stable interfaces.

Version-specific changes must be detected and handled safely.

# 4. PHASE 1 - DEEP REPOSITORY AUDIT

Inspect at minimum:

```text
status_changer_gui.py
status_random_gui.py
status_marquee_gui.py
camfrog_status_gui.py

status_changer_entry.py
status_random_entry.py
status_marquee_entry.py

camfrog_auto.py
camfrog_gui.py
camfrog_presence.py

room_control_gui.py

control-server/
zchat-client/
tests/
windows_tests/
docs/
.github/workflows/
```

Discover and inspect any additional modules referenced by those components.

Investigate:

- Windows process discovery
- Window selection and role classification
- pywinauto execution paths
- Foreground/focus management
- Status text editing
- Enter key submission
- Background Windows messages
- Clipboard interactions
- Keyboard and mouse injection
- Sound and notification behavior
- Worker lifecycle
- Random and Marquee scheduling
- GUI and background process separation
- Configuration loading and validation
- Build entrypoints and packaging
- Existing automated tests

Produce a prioritized root-cause report.

# 5. PHASE 2 - VERIFIED CAMFROG PROCESS DISCOVERY

Implement or improve a shared:

```text
WindowsCamfrogProcessDiscovery
```

Requirements:

1. Discover `Camfrog Video Chat.exe` by executable identity.
2. Verify full executable path.
3. Verify Authenticode signature against expected publisher identity.
4. Track PID and process creation time.
5. Exclude `camfrog_cef.exe` helper processes.
6. Exclude ZChat's own processes and windows.
7. Support multiple windows belonging to one verified Camfrog process.
8. Detect multiple independent Camfrog instances.
9. Fail closed on ambiguous account/process mapping.
10. Revalidate process identity before executing an action.

Never terminate a process not owned by the ZChat agent.

# 6. PHASE 3 - WINDOW ROLE CLASSIFICATION

Implement or improve:

```text
WindowsCamfrogWindowClassifier
```

Classify:

```text
MAIN_CLIENT
ACCOUNT_WINDOW
ROOM_WINDOW
PRIVATE_IM_WINDOW
UNKNOWN
```

Use multiple independent signals:

- Verified process identity
- HWND
- Window class
- UI Automation control tree
- Control type
- Automation ID
- Observed structural signatures

Do not rely solely on window titles.

Do not assume that every `#32770` window has the same role.

A room-history UI does not prove current room membership.

A visible Online label does not prove current account presence.

Unknown windows must remain UNKNOWN.

# 7. PHASE 4 - STRICT TRUE BACKGROUND MODE

Implement a dedicated background status execution mode.

The user's desktop must remain fully usable while the worker operates.

## Forbidden operations in strict background mode

```python
win.set_focus()
ctrl.set_focus()
ctrl.click_input()
ctrl.type_keys()
keyboard.send_keys()
user32.SetForegroundWindow()
```

Also prohibit:

- Global mouse injection
- Global keyboard injection
- Mouse cursor repositioning
- Clipboard replacement
- Window activation
- Automatic window restoration
- Global Windows sound configuration changes
- Automatic switching from background to foreground mode

Interactive mode may retain its existing behavior, but must remain explicitly separated from strict background mode.

The background worker must never silently select an interactive fallback.

## Acceptance requirement

The user must be able to:

- Type in VS Code
- Use a web browser
- Move the mouse
- Switch applications
- Play audio
- Keep Camfrog minimized

without ZChat interrupting these activities.

If a background update is unsupported by the actual client, return:

```text
BACKGROUND_UNSUPPORTED
```

Do not fake success.

# 8. PHASE 5 - STATUS EDITING AND SUBMISSION

Inspect and refactor the existing status editing implementation.

Existing observed controls:

```text
CComboBoxTS / 1436
    └── Edit / 1001
```

Implement a safe execution sequence:

```text
DISCOVER_PROCESS
    ↓
VERIFY_PROCESS
    ↓
DISCOVER_WINDOW
    ↓
VERIFY_STATUS_CONTROL
    ↓
WRITE_TEXT_WITHOUT_FOCUS
    ↓
VERIFY_TEXT_READBACK
    ↓
SUBMIT_WITHOUT_GLOBAL_INPUT
    ↓
VERIFY_APPLIED_STATE
    ↓
REPORT_RESULT
```

Use supported UI Automation value-setting operations or carefully validated native Windows control messages.

Any background submission mechanism must be verified against the genuine installed client.

Do not assume `PostMessage()` success means the status was committed.

Do not send simulated global keyboard events as a fallback.

Preserve the user's clipboard contents without accessing or changing them in strict background mode.

# 9. PHASE 6 - REMOVE UNSAFE SOUND MUTATION

Inspect all uses of:

```text
winreg
AppEvents
SystemAsterisk
SystemExclamation
SystemNotification
MessageBeep
Beep
winsound
```

Remove logic that temporarily rewrites Windows sound settings to suppress application beeps.

Do not disable:

- Windows Defender notifications
- System security alerts
- Accessibility notifications
- Global notification sounds

Prevent unnecessary sounds by correcting the application interaction mechanism.

If a Camfrog-generated sound cannot be eliminated through supported integration behavior, document the limitation rather than altering global Windows settings.

# 10. PHASE 7 - SHARED BACKGROUND STATUS ENGINE

Reduce duplicated logic across:

```text
status-changer
status-random
status-marquee
```

Introduce shared abstractions where appropriate:

```text
CamfrogProcessProvider
CamfrogWindowResolver
StatusControlAdapter
BackgroundStatusExecutor
StatusVerificationProvider
StatusScheduler
```

Preserve the existing executable entrypoints and application-specific behavior.

Requirements:

- Random status rotation
- Marquee status rotation
- Scheduled status updates
- Status history
- Retry/backoff
- Cancellation
- Graceful shutdown
- Crash recovery
- Per-instance concurrency protection
- Duplicate submission prevention

Do not start multiple conflicting status workers against the same account.

Do not rewrite unrelated features.

# 11. PHASE 8 - STATE AND EVIDENCE MODEL

Define explicit status execution results:

```text
PENDING
PROCESS_VERIFIED
WINDOW_VERIFIED
TEXT_WRITTEN
SUBMIT_DISPATCHED
VERIFIED_APPLIED
FAILED
UNKNOWN
BACKGROUND_UNSUPPORTED
```

Only report `VERIFIED_APPLIED` when authoritative evidence confirms the requested status is active.

Text read-back from an Edit control is insufficient by itself.

Keep process, authentication, room membership, and status verification independent.

Record sanitized operational evidence:

```text
request_id
operation_id
client_version
process_identity
window_role
execution_mode
result_state
duration_ms
verification_source
error_code
```

Do not place passwords, cookies, message bodies, CSRF token values, or unrelated personal information in operational logs.

# 12. PHASE 9 - CONFIGURATION CONTRACT

Introduce a backward-compatible configuration model equivalent to:

```json
{
  "status": {
    "enabled": true,
    "execution_mode": "strict_background",
    "background_enter_target": "combo",
    "verify_result": true,
    "interval_seconds": 600
  },
  "safety": {
    "require_foreground": false,
    "restore_previous_window": false,
    "allow_focus_stealing": false,
    "allow_mouse_injection": false,
    "allow_keyboard_injection": false,
    "allow_clipboard_mutation": false,
    "allow_system_sound_changes": false
  }
}
```

Treat this as the target configuration contract.

Implement schema validation before making the fields operational.

Existing configurations must remain supported through explicit defaults or documented migration behavior.

Do not change legacy interactive behavior silently.

# 13. PHASE 10 - REAL WINDOWS TESTING

Create and execute automated tests where the environment permits.

## Process tests

- Correct executable selected
- Signature verification
- Multiple Camfrog windows
- Multiple Camfrog processes
- PID reuse
- Process termination during execution
- Ambiguous process identity

## UI tests

- Correct status Edit selection
- Correct ComboBox parent selection
- Unknown window rejection
- Stale HWND rejection
- Hidden/minimized window handling

## Strict background tests

Verify:

- Foreground window is unchanged
- Keyboard focus is unchanged
- Mouse position is unchanged
- Clipboard contents are unchanged
- No global input injection
- No automatic window activation
- No global sound-setting modification
- No unintended modal dialogs

## Status tests

- Text write success
- Text write failure
- Background submit success
- Background submit failure
- Unknown external outcome
- Duplicate submission
- Worker restart
- Random rotation
- Marquee rotation
- Cancellation during execution

Use mocks for deterministic unit tests and the genuine client for Windows acceptance tests.

Clearly separate mocked evidence from real runtime evidence.

# 14. PHASE 11 - BUILD AND RELEASE VERIFICATION

Validate all existing Windows executables:

```text
dist/room-control/room-control.exe
dist/chat-im-private/chat-im-private.exe
dist/status-random/status-random.exe
dist/status-marquee/status-marquee.exe
dist/im-autoreply/im-autoreply.exe
dist/web-status/web-status.exe
dist/music-dj/music-dj.exe
dist/status-changer/status-changer.exe
dist/zchat-client/zchat-client.exe
line/dist/line-status-changer.exe
```

Also validate:

```text
camfrog-features-windows.zip
dist/SHA256SUMS.txt
dist/BUILD_SOURCE.txt
dist/zchat-client/SHA256SUMS.txt
```

Build all affected executables using the existing repository build system.

Do not modify unrelated build outputs.

Generate and verify checksums.

Run relevant static analysis, tests, and packaging checks.

A successful build does not establish functional production readiness.

# 15. PHASE 12 - GITHUB GOVERNANCE

Follow existing repository governance.

## Review account

Use:

```bash
gh auth switch -u policedbc
```

Perform independent review and security audit.

Approve only if the reviewer is independent, all applicable checks pass, and repository policy allows the approval.

## Merge account

Use:

```bash
gh auth switch -u cvsz
```

Merge only reviewed, eligible Pull Requests.

Requirements:

- No force merge
- No bypass of required CI
- No branch protection bypass
- No merging unresolved security findings
- No destructive operations
- Respect GPG signing requirements
- Preserve an auditable review history

Do not claim a Pull Request was merged unless the GitHub merge result confirms it.

# 16. PRODUCTION ACCEPTANCE GATES

All required conditions must be satisfied before declaring strict background status automation ready:

| Gate | Acceptance |
|---|---|
| Process discovery | Verified genuine Camfrog process |
| Window classification | Correct status-control window |
| No-focus execution | No foreground window changes |
| Keyboard isolation | No global keyboard injection |
| Mouse isolation | No cursor movement or synthetic mouse input |
| Clipboard isolation | Clipboard unchanged |
| Sound isolation | No global sound changes or avoidable input beeps |
| Background submission | Tested on the genuine Camfrog client |
| Result verification | Status actually applied |
| Hidden/minimized mode | Independently tested |
| Random/Marquee | Stable repeated execution |
| Recovery | Safe retry and crash behavior |
| Packaging | Successful reproducible Windows builds |
| Governance | Independent review and required CI passed |

Unsupported capabilities must be reported accurately rather than simulated.

# 17. REQUIRED FINAL REPORT

Provide:

1. Executive Summary
2. Root Cause Analysis
3. Source Files Modified
4. Architecture Changes
5. Windows Runtime Findings
6. Background Input Isolation Evidence
7. Status Submission Verification
8. Tests Executed and Actual Results
9. Build Artifacts and Checksums
10. Security Audit Findings
11. Pull Request and Review Status
12. Remaining Blockers
13. Production Readiness Verdict

Use:

```text
VERIFIED
IMPLEMENTED_NOT_VERIFIED
BLOCKED
FAILED
NOT_IMPLEMENTED
NOT_APPLICABLE
```

Final acceptance principle:

**A true background operation must preserve the user's desktop interaction and must verify the external effect without relying on foreground keyboard or mouse simulation.**

Proceed autonomously with repository investigation, implementation, refactoring, testing, and packaging wherever authorized tools and environments permit. Do not fabricate evidence or bypass authorization, third-party restrictions, required reviews, or deployment gates.

**ผลลัพธ์ที่ต้องการจาก Codex\:** `status-changer.exe`, `status-random.exe` และ `status-marquee.exe` สามารถทำงานต่อเนื่องโดยไม่แย่ง Mouse/Keyboard และไม่เปิดหน้าต่าง Camfrog ขึ้นมารบกวน หาก Camfrog 8.5 ไม่รองรับการ Submit Status แบบ Hidden/Minimized จริง ต้องรายงานข้อจำกัดพร้อมหลักฐาน แทนการใช้ Foreground Automation โดยไม่แจ้งผู้ใช้

## Prompt:
10/16/2026, 10:51:45 PM

▾ Thought for 9s
  All test suites are passing, including unit, automated, command processing, and live acceptance
  tests. Confident the core functionality and existing behavior are intact. The next step involves a
  final review of all the changed files to ensure that everything adheres to the requirements.
  ### Real Camfrog 8.5 Windows UI Runtime Integration Summary
  We have implemented an evidence-driven, fail-closed Windows UI runtime integration for genuine
  Camfrog Video Chat 8.5 (8.5.0.51219) on Windows 11 under Python 3.14.8 (psutil 7.2.2, pywinauto
  0.6.9).
  ──────
  ### Implementation Highlights
  1. Process Discovery (WindowsCamfrogProcessDiscovery):
      • Matches genuine executable Camfrog Video Chat.exe (PE FileVersion 8.5.0.51219).
      • Verifies Authenticode digital signature using WinVerifyTrust (wintrust.dll).
      • Validates code-signing publisher subject as Camfrog LLC via native CryptoAPI (crypt32.dll
      CryptQueryObject / CertGetNameStringW).
      • Captures immutable identity: (pid, create_time, exe_path, publisher, signature_valid,
      version, is_agent_launched).
      • Strictly excludes auxiliary CEF subprocesses (camfrog_cef.exe or --type=renderer|gpu-
      process|utility) and ZChat's own processes and Tk GUI windows.
      • Fails closed if multiple verified processes exist without an explicit target PID.
  2. Structural UI Classifier (WindowsCamfrogWindowClassifier):
      • Main Client / Directory: Identified by CTreeViewTS (buddy list / contact directory) and
      CComboBoxTS (status selector, id 1436) with native Edit controls.
      • Room Window: Identified by VideoViewport (cls VideoViewport, id 11425) and embedded
      Internet Explorer_Server hosting camfrog://wb-log-room-data.inside/.
      • IM Window: Identified by embedded Internet Explorer_Server hosting camfrog://wb-log-im-
      data.inside/ and native edit input (CEditTS/Edit), without VideoViewport.
      • Ambiguous / Unknown: Windows with conflicting, incomplete, or unrecognized structures fail-
      closed to WindowRole.UNKNOWN.
      • Privacy Boundary: Inspects UI control hierarchies and URLs only; message bodies and chat
      texts are never collected or stored during discovery.
  3. Read-Only Attachment & Ownership Protections (CamfrogClientAttachment):
      • Non-destructive attachment to an authorized running Camfrog client via
      attach_to_camfrog_client().
      • Identity revalidation before actions (revalidate_process_identity,
      revalidate_window_identity) guards against PID recycling and window reassignments.
      • Ownership rule strictly enforced: processes not launched by the agent cannot be terminated
      (terminate_client_process raises PermissionError).
  4. Evidence Boundary State Separation (ClientRuntimeState):
      • process_running: Process alive, path verified, and Authenticode signature valid.
      • ui_visible: One or more top-level windows of the verified process are visible.
      • account_authenticated: Main directory window active with populated contact directory; alive
      process alone does not infer authentication.
      • room_member: Room window presence alone does not establish membership. Live testing proved
      that a user kicked due to inactivity still has an open room window, correctly evaluating
      room_member = False.
  5. Backward Compatibility & Adapters (camfrog_auto.py:685-815):
      • Integrated camfrog_windows_runtime helpers into camfrog_auto.py.
      • Preserved all existing contracts and tests without regressions.

  ──────
  ### Verification and Acceptance Evidence
  #### 1. Unit Tests (Offline / Mocked)
  Executed via pytest tests/test_camfrog_windows_runtime.py:
    platform win32 -- Python 3.14.8, pytest-9.1.1
    tests\test_camfrog_windows_runtime.py .............. [100%]
    ============================= 14 passed in 0.25s =============================
  #### 2. Regression Tests

  Executed via pytest tests/test_camfrog_auto.py tests/test_windows_process_commands.py:

    tests\test_camfrog_auto.py ............................................. [ 73%]
    ................                                                         [100%]
    tests\test_windows_process_commands.py ..                                [100%]
    ======================== 63 passed in 25.73s =========================

  #### 3. Live Windows Acceptance Tests on Genuine Camfrog 8.5 Client

  Executed via pytest windows_tests/test_camfrog_windows_runtime_live.py:

    windows_tests/test_camfrog_windows_runtime_live.
  py::test_live_camfrog_process_discovery_and_authenticode PASSED [ 20%]
    windows_tests/test_camfrog_windows_runtime_live.py::test_live_camfrog_window_classification
  PASSED             [ 40%]
    windows_tests/test_camfrog_windows_runtime_live.py::test_live_camfrog_ownership_restrictions
  PASSED             [ 60%]
    windows_tests/test_camfrog_windows_runtime_live.
  py::test_live_camfrog_runtime_state_and_evidence_boundaries PASSED [ 80%]
    windows_tests/test_camfrog_windows_runtime_live.
  py::test_live_camfrog_diagnostics_sanitized_and_privacy PASSED [100%]
    ============================= 5 passed in 25.94s ==============================

  #### 4. Live Diagnostics Output (Sanitized)

    {
      "process": {
        "pid": 21992,
        "create_time": 1792160516.6723657,
        "exe_path": "C:\\Users\\REPLACE_ME\\AppData\\Local\\Programs\\Camfrog Video Chat\\Camfrog
  Video Chat.exe",
        "publisher": "Camfrog LLC",
        "signature_valid": true,
        "version": "8.5.0.51219",
        "is_agent_launched": false
      },
      "windows": [
        {
          "hwnd": 5177812,
          "role": "im_window",
          "title": "REPLACE_ME_ACCOUNT (...)",
          "pid": 21992,
          "is_visible": true,
          "signatures": ["Internet Explorer_Server(wb-log-im-data)+Edit"]
        },
        {
          "hwnd": 33360162,
          "role": "room_window",
          "title": "REPLACE_ME_ROOM: ...",
          "pid": 21992,
          "is_visible": true,
          "signatures": ["VideoViewport+wb-log-room-data"]
        },
        {
          "hwnd": 3149540,
          "role": "main_directory",
          "title": "Camfrog Video Chat",
          "pid": 21992,
          "is_visible": true,
          "signatures": ["CTreeViewTS+CComboBoxTS"]
        }
      ],
      "state": {
        "process_running": true,
        "ui_visible": true,
        "account_authenticated": true,
        "room_member": false,
        "evidence_notes": [
          "Process PID 21992 is alive, path verified (C:\\Users\\cvsz.
  ZEAZ\\AppData\\Local\\Programs\\Camfrog Video Chat\\Camfrog Video Chat.exe), Authenticode signed
  by 'Camfrog LLC'.",
          "UI visible with 3 top-level window(s): ['hwnd=5177812 role=im_window', 'hwnd=33360162
  role=room_window', 'hwnd=3149540 role=main_directory'].",
          "Account authenticated: Main client window (hwnd=3149540) active with contact directory.",
          "Room window exists (hwnd=33360162), but user was kicked or disconnected. Active
  membership is FALSE per evidence boundary rule."
        ]
      },
      "read_only": true
    }
  ──────
  ### Changed Files

  • camfrog_windows_runtime.py: New production runtime module with discovery, classifier, state
  separation, and attachment.
  • camfrog_auto.py: Integrated runtime discovery, classifier, and state evaluation helpers.
  • test_camfrog_windows_runtime.py: Unit tests for offline simulated validation.
  • test_camfrog_windows_runtime_live.py: Windows acceptance tests against live running client.
  • CAMFROG-8.5-FINDINGS.md: Updated technical findings and evidence documentation.
  • validate_repo.py: Added .venv-runtime to excluded validation directories.

  ### Remaining Blockers & Production Readiness

  • Blockers: None. All tests (offline unit, process commands, and live Windows integration) pass
  cleanly.
  • Production Readiness: Confirmed for read-only attachment, process verification, window
  classification, and evidence-driven runtime monitoring against genuine Camfrog 8.5.0.51219
  clients. Active room send operations remain governed by separate user authorization.

## Response:
10/16/2026, 10:52:08 PM · gpt-6-thinking

> **ตรวจสอบคอมมิตล่าสุดของ zchat และดึงไฟล์รันไทม์ Camfrog Windows**
>
> 
>
> ประมวลผล 21s

## ZChat - Implementation Review &amp; Production Readiness

จากรายงาน Codex ล่าสุด **Real Camfrog 8.5 Windows Runtime Integration มีความคืบหน้าชัดเจน** โดยรายงานว่าผ่าน Unit Tests, Regression Tests และ Live Windows Acceptance Tests

อย่างไรก็ตาม มีข้อสำคัญที่ต้องแยกให้ชัดเจน\:

**สิ่งที่รายงานนี้ยืนยันคือ Read-only Runtime Integration ไม่ใช่การแก้ปัญหา Status Changer ให้ทำงานเบื้องหลังโดยไม่แย่ง Mouse/Keyboard สำเร็จแล้ว**

**Runtime Discovery &amp; Classification** (Reported PASS)

**Unit Tests**
**14 passed**

**Regression Tests**
**63 passed**

**Live Windows Tests**
**5 passed**

**True Background Status Changer** (Not Verified)

### ช่องว่างจาก Master Prompt ที่ยังไม่ได้ปิด

| Requirement | หลักฐานจากรายงาน |
|--------|--------|
| Verified Process Discovery | มีรายงานว่าผ่าน |
| Window Role Classification | มีรายงานว่าผ่าน |
| Read-only Attachment | มีรายงานว่าผ่าน |
| Prevent Unowned Process Termination | มีรายงานว่าผ่าน |
| Status update ขณะ VS Code มี Focus | ไม่ปรากฏ |
| Status update ขณะ Camfrog Minimized | ไม่ปรากฏ |
| Status update ขณะ Camfrog Hidden to Tray | ไม่ปรากฏ |
| No keyboard/mouse interference | ไม่ปรากฏ |
| No Windows sound mutation | ไม่ปรากฏ |
| Verified Status Applied | ไม่ปรากฏ |

ดังนั้น `Blockers: None` ในรายงาน Codex ควรตีความว่าไม่มี Blocker สำหรับ **Read-only Runtime Scope** เท่านั้น ไม่ใช่ทุก Requirement ของ ZChat

## ผลตรวจสอบ GitHub เพิ่มเติม

ผมตรวจ `cvsz/zchat` ผ่าน GitHub อีกครั้ง พบว่า\:

- `main` ที่เครื่องมือเข้าถึงยังชี้ไปที่ Commit `6ba80e6`
- ยังไม่พบไฟล์ `camfrog_windows_runtime.py` บน `main`
- จึงยังยืนยันไม่ได้ว่า Implementation ที่ Codex รายงานถูก Commit หรือ Push แล้ว

เป็นไปได้ว่า Codex กำลังทำงานอยู่ใน Local Working Tree หรือ Branch ที่ยังไม่ได้ Push

### คำสั่งตรวจสอบบนเครื่อง Windows

```powershell
cd D:\data\zchat

git status --short --branch
git branch --show-current
git log -1 --oneline
git diff --stat

Test-Path .\camfrog_windows_runtime.py
Test-Path .\tests\test_camfrog_windows_runtime.py
Test-Path .\windows_tests\test_camfrog_windows_runtime_live.py
```

### งานที่ต้องสั่ง Codex ต่อ

ให้ Codex ดำเนินการต่อจาก Implementation ปัจจุบัน โดยมุ่งแก้ปัญหาที่เป็นเป้าหมายหลัก\:

> Continue from the existing Camfrog Windows Runtime implementation. Do not repeat completed read-only discovery work. Implement and verify strict background Status Changer execution across `status_changer_gui.py`, `status_random_gui.py`, `status_marquee_gui.py`, and relevant shared modules.
>
> Ensure Camfrog does not steal foreground focus, mouse input, keyboard input, or clipboard access. Remove Windows system-sound registry mutation. Validate minimized and hidden-window behavior independently. Verify that status changes are actually applied, not merely written into a control.
>
> Preserve existing functionality, run regression and real Windows acceptance tests, rebuild affected executables, and report any unsupported behavior as BLOCKED.
>
> Review all changed files and prepare a Pull Request with actual verification evidence. Do not merge while required CI, independent review, or production acceptance gates remain incomplete.

**Production Readiness Verdict\:** `IMPLEMENTED_NOT_VERIFIED` สำหรับ Runtime Integration บน GitHub และ `NOT VERIFIED` สำหรับ True Background Status Changer

ขั้นตอนสำคัญที่สุดตอนนี้คือทำให้ **Status Changer เปลี่ยนสถานะได้จริงในขณะที่ Camfrog อยู่เบื้องหลัง และผู้ใช้ยังทำงานด้วย Mouse/Keyboard ได้ตามปกติ** ก่อนประกาศว่างานเสร็จสมบูรณ์

## Prompt:
10/16/2026, 10:52:54 PM

กำลังเทสอยู่

## Response:
10/16/2026, 10:52:57 PM · gpt-6-thinking

รับทราบครับ ตอนนี้อยู่ระหว่าง **Real Windows Acceptance Testing** ของ ZChat + Camfrog 8.5

ระหว่างทดสอบ ให้เน้นตรวจ 5 จุดสำคัญ\:

1. **Background Execution\:** Camfrog ไม่แย่ง Focus จาก VS Code หรือ Browser
2. **Mouse &amp; Keyboard\:** ใช้งานได้ปกติระหว่าง Status Changer ทำงาน
3. **Minimized / Hidden\:** เปลี่ยน Status ได้จริงขณะ Camfrog ถูกย่อหรือซ่อน
4. **Silent Operation\:** ไม่มีเสียงแจ้งเตือนที่ไม่จำเป็น และไม่แก้ Windows Sound Settings
5. **Status Verification\:** ข้อความสถานะเปลี่ยนจริง ไม่ใช่แค่เขียนลง Edit Control สำเร็จ

หากพบปัญหา ให้บันทึกขั้นตอนที่ทำให้เกิดปัญหา, Expected/Actual Result และ Logs โดยไม่เปิดเผยข้อมูลส่วนตัว

**สถานะปัจจุบัน\:** `TESTING_IN_PROGRESS` — ยังไม่ประกาศ Production Ready จนกว่าผลทดสอบจริงจะผ่าน Acceptance Criteria ครบถ้วน

## Prompt:
10/16/2026, 11:01:12 PM

ตอนนี้ ใน prompt เปิด โปรแกรม zchat ขึ้นมา แล้วจะ อ่าน camfrog.exe อัตดนมัติ หรือ ต้องกดเอง

## Response:
10/16/2026, 11:01:15 PM · gpt-6-thinking

ตาม **Master Prompt ล่าสุด** ที่ให้ Codex ทำงานนั้น เป้าหมายคือ **เปิด ZChat แล้วตรวจหา Camfrog Video Chat.exe ที่กำลังทำงานอยู่โดยอัตโนมัติ** ไม่จำเป็นต้องกดปุ่ม Discover เองทุกครั้ง

แต่ต้องแยกสถานะระหว่างสิ่งที่ Prompt สั่งไว้กับสิ่งที่ Implement เสร็จจริง

| ขั้นตอน | พฤติกรรมที่ต้องการ | สถานะ |
|--------|--------|--------|
| เปิด ZChat | เริ่มตรวจหา Camfrog Process | ต้องยืนยันว่าเชื่อมกับ Startup แล้ว |
| Camfrog เปิดอยู่ | ตรวจ EXE, Signature, PID และ Windows | Codex รายงานว่า Implement แล้ว |
| Camfrog ยังไม่เปิด | แสดง `CLIENT_NOT_RUNNING` | ต้องทดสอบ |
| Camfrog เปิดภายหลัง | ตรวจพบอัตโนมัติผ่าน Background Discovery | ยังไม่ยืนยัน |
| พบหลาย Camfrog Instances | ให้เลือก Process อย่างปลอดภัย | มีการออกแบบ Fail-Closed |
| เริ่ม Status Changer | ใช้ Client ที่ตรวจพบ | ต้องทดสอบการเชื่อมต่อ |
| Camfrog ถูก Minimize | ทำงานเบื้องหลังโดยไม่แย่ง Focus | กำลังทดสอบ |

**จุดสำคัญ\:** จากรายงาน Codex ยืนยันเพียงว่ามี `WindowsCamfrogProcessDiscovery` และ `attach_to_camfrog_client()` แต่ไม่ได้ระบุชัดเจนว่า ZChat เรียกสองฟังก์ชันนี้อัตโนมัติเมื่อเปิดโปรแกรมหรือไม่

### เพิ่มคำสั่งนี้ใน Prompt ที่กำลังทำอยู่

**standard: **

Implement automatic Camfrog client discovery and read-only attachment during ZChat application startup.

Requirements:
- Automatically detect an already-running, verified Camfrog Video Chat.exe.
- Do not require manual Discover or Attach actions for a single unambiguous verified client.
- If Camfrog is not running, display CLIENT_NOT_RUNNING and continue monitoring with bounded polling.
- When Camfrog starts later, automatically discover and attach in read-only mode.
- When Camfrog exits, detach safely and refresh the UI state.
- When multiple Camfrog processes are detected, require explicit user selection.
- Persist only safe process-selection preferences, never credentials or hardcoded PIDs.
- Never launch, terminate, restore, or focus Camfrog automatically.
- Do not automatically start status-changing or messaging actions merely because attachment succeeded.
- Keep discovery asynchronous so the ZChat UI never freezes.
- Update connection state in the GUI and preserve mouse/keyboard focus.
- Add Windows startup, reconnect, crash recovery, and process-replacement acceptance tests.
- Verify actual behavior using the genuine Camfrog 8.5 Windows client.

**สรุป\:** ผมแนะนำให้ ZChat ตรวจหาและเชื่อมต่อ Camfrog แบบ Read-only อัตโนมัติทันทีที่เปิด ZChat ส่วนการ **Start Status Changer** ควรเป็นการเลือกของผู้ใช้ เพื่อป้องกันการเปลี่ยน Status โดยไม่ได้ตั้งใจ

## Prompt:
10/16/2026, 11:07:41 PM

ให้ *.exe run แบบ standalone ทั้งหมด แยก 1. feature 1.exe

## Response:
10/16/2026, 11:07:44 PM · gpt-6-thinking

## ZChat - Standalone Architecture: 1 Feature = 1 EXE

กำหนดให้ **ทุก Feature ของ `cvsz/zchat` สามารถทำงานแบบ Standalone ได้อย่างสมบูรณ์** โดยไม่ต้องเปิด `zchat-client.exe` หรือโปรแกรม ZChat อื่นเป็นตัวกลาง

แต่ละ `.exe` ต้องตรวจหา Camfrog Client อัตโนมัติ มี Configuration, Worker, Logs และ Lifecycle ของตัวเอง และไม่รบกวน Mouse/Keyboard ของผู้ใช้

### Target Executables

| Executable | Feature | Standalone |
|--------|--------|--------|
| `room-control.exe` | ควบคุมห้องสนทนา | Required |
| `chat-im-private.exe` | Private IM | Required |
| `status-random.exe` | Random Status | Required |
| `status-marquee.exe` | Marquee Status | Required |
| `im-autoreply.exe` | IM Auto Reply | Required |
| `web-status.exe` | Website Status | Required |
| `music-dj.exe` | Music DJ | Required |
| `status-changer.exe` | Status Changer | Required |
| `zchat-client.exe` | ZChat Client | Required |
| `line-status-changer.exe` | LINE Status Changer | Required |

**Standalone** หมายถึงไม่พึ่งพา ZChat Executable ตัวอื่น แต่ Feature ที่ใช้ Camfrog ยังต้องมี Official Camfrog Client ติดตั้งและทำงานอยู่ตามข้อกำหนดของ Feature นั้น

## Master Implementation Prompt

**document: **

# ZChat - Full Standalone Windows Application Architecture

**Repository:** https://github.com/cvsz/zchat

**Primary Goal:** One Feature = One Independently Executable Application

## ROLE

Act as a Principal Windows Software Architect, Senior Python Engineer, Build & Release Engineer, Security Auditor, and QA Automation Engineer.

Refactor and validate the ZChat Windows application suite so that every feature is packaged and operates independently.

## 1. Mandatory Standalone Contract

Every feature must:

- Launch directly from its own `.exe`.
- Never require `zchat-client.exe` or another ZChat feature executable.
- Automatically discover a verified running Camfrog client when relevant.
- Continue bounded background discovery if Camfrog is not running.
- Support safe automatic read-only attachment.
- Maintain independent configuration and application data.
- Maintain independent logs and diagnostic records.
- Have independent Start, Stop, Restart, and Exit behavior.
- Shut down its owned workers without terminating Camfrog or another feature.
- Display accurate operational state.
- Work without a developer terminal, virtual environment, or manually installed Python interpreter.
- Package required Python modules, native dependencies, resources, and manifests.

Feature-specific external dependencies, such as the genuine Camfrog client or authorized web services, must be documented explicitly.

## 2. Independent Executables

Build and validate:

```text
dist/
├── room-control/
│   └── room-control.exe
├── chat-im-private/
│   └── chat-im-private.exe
├── status-random/
│   └── status-random.exe
├── status-marquee/
│   └── status-marquee.exe
├── im-autoreply/
│   └── im-autoreply.exe
├── web-status/
│   └── web-status.exe
├── music-dj/
│   └── music-dj.exe
├── status-changer/
│   └── status-changer.exe
├── zchat-client/
│   └── zchat-client.exe
└── SHA256SUMS.txt

line/dist/
└── line-status-changer.exe
```

## 3. Shared Source, Independent Runtime

Shared Python libraries are allowed at build time.

However, each packaged application must contain everything it needs to run independently.

Do not introduce runtime dependencies on other feature executables.

Use common source modules for:

- Camfrog process discovery
- Authenticode verification
- Window role classification
- Background execution policy
- Configuration validation
- Structured logging
- Lifecycle management
- Error reporting

Avoid duplicated implementations where practical.

Do not implement unnecessary IPC or central services merely to share code.

## 4. Automatic Camfrog Discovery

For every Camfrog-dependent EXE:

1. Launch application.
2. Discover genuine `Camfrog Video Chat.exe`.
3. Verify process identity and signature.
4. Exclude CEF subprocesses.
5. Discover relevant UI windows.
6. Attach read-only to one unambiguous client.
7. Continue monitoring when the client is absent.
8. Reconnect safely after client restart.
9. Require explicit selection if multiple Camfrog client instances exist.
10. Never automatically launch, focus, close, or terminate Camfrog.

Do not require manual Discover for a single verified running client.

Automatic attachment must not automatically trigger status changes, messages, or other external side effects.

## 5. True Background Operation

All supported background features must preserve user desktop interaction.

Strict background mode prohibits:

```python
set_focus()
click_input()
type_keys()
keyboard.send_keys()
SetForegroundWindow()
```

Also prohibit global input injection, clipboard modification, unexpected window restoration, and Windows sound registry mutation.

If a feature cannot operate without foreground interaction, report `BACKGROUND_UNSUPPORTED`.

Do not silently fall back to intrusive foreground automation.

## 6. Independent Configuration and Storage

Each EXE must have a separate writable application-data location, for example:

```text
%LOCALAPPDATA%\ZChat\
├── room-control\
├── chat-im-private\
├── status-random\
├── status-marquee\
├── im-autoreply\
├── web-status\
├── music-dj\
├── status-changer\
├── zchat-client\
└── line-status-changer\
```

Each application owns its own:

- Configuration
- Logs
- Worker state
- History, where applicable
- Cache
- Diagnostics

Do not place mutable runtime state inside PyInstaller extraction directories.

Support safe migration of existing configuration files.

Sensitive data must use appropriate Windows-protected storage, not plaintext configuration files.

## 7. Worker and Process Isolation

Requirements:

- One active worker per feature instance where necessary.
- Locking scoped to application identity and user session.
- Independent worker lifecycle.
- Bounded polling and retries.
- Graceful shutdown.
- Crash recovery.
- No orphan workers.
- No unexpected modal dialogs during background execution.
- No Windows notification sounds caused by incorrect input handling.
- No termination of unrelated processes.

Multiple different ZChat feature EXEs must be able to run simultaneously.

Where features could modify the same Camfrog account or control, implement cross-feature coordination to avoid conflicting actions.

## 8. Windows Packaging

Use the existing build pipeline where possible.

For every EXE:

- Bundle dependencies.
- Bundle necessary assets.
- Validate startup without Python installed on the target machine.
- Validate working-directory independence.
- Validate Unicode/Thai paths.
- Validate read/write permissions.
- Validate antivirus-friendly packaging.
- Validate PyInstaller resource resolution.
- Generate build provenance and SHA256 checksums.

Use `--onedir` when it provides more reliable native dependency loading.

A standalone folder containing an EXE and bundled runtime DLLs is acceptable.

Do not claim an EXE is a single-file binary unless `--onefile` packaging has been explicitly tested.

## 9. Testing Requirements

Test each application independently:

- Direct EXE startup
- Configuration initialization
- Automatic provider discovery
- No other ZChat EXE running
- Camfrog missing
- Camfrog already running
- Camfrog restarted
- Multiple Camfrog processes
- Background operation
- No mouse/keyboard interference
- Normal exit and worker cleanup
- Repeated launch
- Packaging integrity

Test simultaneous execution of multiple features.

Run unit, integration, Windows live acceptance, and packaged binary smoke tests.

Do not claim that mocked tests establish real Camfrog behavior.

## 10. Build and Delivery

Deliver:

1. Independently runnable EXEs.
2. Required bundled runtime files.
3. Per-application default configuration.
4. Migration documentation.
5. Test results for each application.
6. Build provenance.
7. SHA256 manifests.
8. Known limitations.
9. Reproducible build instructions.

Preserve the current build artifact names unless a documented change is necessary.

## 11. GitHub Governance

Follow repository rules.

Use `policedbc` for independent review and `cvsz` for merging where account access and repository permissions permit.

Do not bypass branch protection, CI, code review, or security gates.

No force merges.

## 12. Acceptance Criteria

An application is STANDALONE_VERIFIED only when:

- Its packaged EXE launches independently.
- No other ZChat EXE is required.
- Its dependencies are packaged.
- Its configuration is isolated.
- Its workers are isolated.
- Its feature works end-to-end under the supported runtime conditions.
- It shuts down without affecting other applications.
- Its required Windows acceptance tests pass.

A successful build alone is insufficient.

Final objective:

**Every ZChat feature is an independently packaged, independently executable, independently configurable, and independently testable Windows application - with shared engineering foundations but no dependency on another ZChat feature process.**

### ข้อกำหนดสำคัญสำหรับ Status Changer

การแยกเป็น Standalone EXE **ไม่ได้แก้ปัญหา Mouse/Keyboard Interference โดยอัตโนมัติ** ต้องให้ `status-changer.exe`, `status-random.exe` และ `status-marquee.exe` ใช้ Strict Background Execution ที่ผ่าน Real Camfrog Acceptance Tests ด้วย

แนะนำให้ Codex ทำ Packaging Isolation และ Background Runtime Verification เป็นสอง Acceptance Gates แยกกัน เพื่อให้แน่ใจว่าทั้ง **1 Feature = 1 EXE** และ **ไม่รบกวนการใช้งาน Windows** ผ่านจริงทั้งคู่

## Prompt:
10/16/2026, 11:10:43 PM

ให้ *.exe run แบบ standalone ทั้งหมด แยก 1. feature 1.exe zchat-client.exe = merge all feture to single  control panel form zchat-server

## Response:
10/16/2026, 11:10:45 PM · gpt-6-thinking

## ZChat - Final Architecture: Standalone Features + Unified Control Panel

กำหนด Architecture ใหม่สำหรับ [github.com](https://github.com/cvsz/zchat?utm_source=chatgpt.com) ให้รองรับการใช้งาน **2 รูปแบบพร้อมกัน** ได้แก่

1. **Standalone Applications\:** แต่ละ Feature มี `.exe` ของตัวเอง สามารถเปิดและใช้งานแยกกันได้โดยไม่ต้องเปิด ZChat Control Panel
2. **Unified Control Panel\:** `zchat-client.exe` รวมทุก Feature ไว้ใน Control Panel เดียว โดยเชื่อมต่อกับ `zchat-server` สำหรับจัดการ Configurations, Status, Jobs, Agents และ Logs จากส่วนกลาง

ทั้งสองรูปแบบต้องใช้ Shared Core และ Business Logic เดียวกัน ไม่ใช่พัฒนา Feature ซ้ำสองชุด

## 1\. Target Architecture

**ZChat Server - Central Control Plane**

FastAPI · PostgreSQL · Authentication · RBAC · Jobs · Config · Audit · Realtime Status

Authenticated HTTPS / WebSocket

**zchat-client.exe**

Unified Control Panel - รวมทุก Feature

#### Shared Runtime / Feature Core

Process Discovery · Camfrog Adapter · Background Workers · Configuration · Verification · Event Bus

---

1 Feature = 1 Standalone EXE (ทำงานเป็นอิสระ)

**Real Camfrog Client**

Windows UI / Official Interfaces

**Camfrog Website / LINE**

Authorized Provider Adapters

การเชื่อมต่อ `zchat-server` เป็นตัวเลือกสำหรับ Standalone Mode และเป็นแกนกลางสำหรับ Centralized Management โดยไม่ทำให้แต่ละ Feature ต้องพึ่ง Server ตลอดเวลาในงานที่รองรับ Local Execution

## 2\. Executable Distribution

| Standalone Executable | Functional Role | Unified Client |
|--------|--------|--------|
| `room-control.exe` | Room management | Module |
| `chat-im-private.exe` | Private Chat | Module |
| `status-random.exe` | Random Status | Module |
| `status-marquee.exe` | Scrolling Status | Module |
| `im-autoreply.exe` | Automatic Replies | Module |
| `web-status.exe` | Website Status | Module |
| `music-dj.exe` | Music / DJ | Module |
| `status-changer.exe` | Manual/Scheduled Status | Module |
| `line-status-changer.exe` | LINE Status | Module |
| **`zchat-client.exe`** | **All features + Central Control Panel** | **All modules** |

ข้อกำหนดหลักคือ `zchat-client.exe` ต้องรวม Feature Logic เข้า Package ตัวเอง ไม่ใช่เป็นเพียง Launcher ที่สั่งเปิด EXE อื่น

---

## 3\. Unified Master Implementation Prompt

ใช้ Prompt นี้กับ Codex/Kilo สำหรับปรับโครงสร้างและดำเนินการตามเป้าหมาย

**document: **

# ZCHAT - UNIVERSAL STANDALONE + UNIFIED CONTROL PANEL MASTER PROMPT

**Repository:** https://github.com/cvsz/zchat

**Target Platform:** Windows 11  
**Real Provider:** Camfrog Video Chat 8.5.0.51219  
**Runtime:** Python 3.14  
**Architecture:** Shared Core + Independent Standalone EXEs + Unified Client + Central Control Server  
**Primary Goal:** One Feature = One EXE, plus One Unified Client = All Features

---

# 1. ROLE AND MISSION

Act as a Principal Software Architect, Windows Runtime Engineer, Senior Python Developer, Full-Stack Engineer, Security Auditor, QA Engineer, and Release Engineer.

Investigate, refactor, implement, integrate, test, and package the entire ZChat application ecosystem.

Deliver two fully supported distribution models:

**A. Standalone Mode**

Every feature has its own independently runnable Windows executable.

**B. Unified Mode**

`zchat-client.exe` provides one integrated desktop control panel containing all ZChat features and connects to `zchat-server` for centralized control.

Both modes must reuse the same feature implementation, not duplicate business logic.

# 2. NON-NEGOTIABLE ARCHITECTURE

Use this logical architecture:

```text
ZChat Server (FastAPI + PostgreSQL)
    |
    +-- REST API / WebSocket Events
    |
ZChat Unified Client (zchat-client.exe)
    |
    +-- Unified Dashboard
    +-- Room Control
    +-- Private IM
    +-- Random Status
    +-- Marquee Status
    +-- IM Auto Reply
    +-- Web Status
    +-- Music DJ
    +-- Status Changer
    +-- LINE Status
    |
ZChat Shared Core
    |
    +-- Windows Camfrog Runtime Adapter
    +-- Provider Adapters
    +-- Background Execution Engine
    +-- Worker Lifecycle
    +-- Configuration Manager
    +-- Event Bus
    +-- Audit and Observability
```

The shared core is a source-level/build-time dependency packaged independently into each distributable.

Never require a standalone feature to run another ZChat EXE.

Never implement unified features by launching standalone EXEs as child processes.

A separate worker subprocess is allowed only for justified isolation when it is packaged as part of the same application and not another feature executable.

# 3. REPOSITORY INVESTIGATION

Inspect the entire existing repository before modification.

Required scope:

- `AGENTS.md`
- `CLAUDE.md`
- Architecture documentation
- Existing standalone GUI applications
- Feature entrypoints
- `camfrog_auto.py`
- `camfrog_windows_runtime.py`, if present
- `control-server/`
- `zchat-client/`
- Existing tests and Windows acceptance tests
- Existing build and release scripts
- GitHub Actions
- Packaging configurations

Preserve existing code conventions and repository governance.

Identify duplicated logic, incomplete integrations, incompatible contracts, security vulnerabilities, race conditions, and deployment blockers.

Produce a before/after architecture and migration plan.

# 4. FEATURE MODULE CONTRACT

Implement reusable feature modules behind explicit interfaces.

Each feature should expose an equivalent contract:

```python
class FeatureModule:
    def initialize(self, config, context): ...
    def start(self): ...
    def stop(self): ...
    def restart(self): ...
    def get_status(self): ...
    def validate_config(self, config): ...
    def health_check(self): ...
```

Implement additional methods or asynchronous variants where required.

Required lifecycle states:

```text
NOT_CONFIGURED
STOPPED
STARTING
RUNNING
DEGRADED
FAILED
STOPPING
```

Feature-specific external action results must be modeled independently from worker lifecycle state.

Each feature must be embeddable into both a standalone GUI and the unified client.

# 5. STANDALONE APPLICATION REQUIREMENTS

For every standalone EXE:

- Launch independently.
- Include required Python and native dependencies.
- Initialize its own configuration and logs.
- Automatically discover an authorized relevant provider.
- Attach read-only where supported and unambiguous.
- Operate with no other ZChat EXE running.
- Provide Start / Stop / Restart controls.
- Recover from recoverable worker errors.
- Prevent duplicate workers.
- Support offline/local operation where technically possible.
- Optionally connect to ZChat Server for centralized management.
- Preserve existing settings and data through migration.

A provider-dependent feature must report `PROVIDER_UNAVAILABLE` when its required external provider is absent.

# 6. ZCHAT UNIFIED CLIENT

Refactor `zchat-client.exe` into a fully integrated Windows Control Panel.

Implement:

- Main Dashboard
- Feature navigation
- Feature-specific configuration
- Start / Stop / Restart per feature
- Global Stop All (only ZChat-owned workers)
- Agent and provider status
- Camfrog process discovery
- Account status observations
- Current job queue
- Scheduling controls
- Event and log viewer
- Error diagnostics
- Server connection status
- Settings and update information

Do not launch standalone executables to execute features.

Embed feature modules directly using the shared core.

All background tasks must be non-blocking to the UI.

Ensure each feature's configuration and state remain isolated.

# 7. ZCHAT SERVER - CENTRAL CONTROL PLANE

Build upon the existing FastAPI and PostgreSQL implementation.

Provide authenticated and authorized APIs for:

- User/operator sessions
- Windows agents
- Feature registration
- Feature capabilities
- Feature configuration
- Job scheduling
- Command delivery
- Worker heartbeats
- Feature state snapshots
- Audit records
- Event synchronization
- Operational health

Use RBAC and account-scoped authorization.

Implement an at-least-once command model with bounded leases, replay protection, idempotency controls, and reconciliation for uncertain external effects.

Do not treat successful command delivery as successful provider execution.

Support secure reconnect and fail-closed behavior when the server becomes unavailable.

# 8. SINGLE WRITER / CONCURRENCY RULE

Multiple ZChat applications may run at the same time.

However, only one authorized worker may control a conflicting external resource at a time.

Introduce resource-scoped execution leases equivalent to:

```text
camfrog/account/{identity}/status
camfrog/account/{identity}/room/{room_id}
camfrog/account/{identity}/im/{recipient}
```

Requirements:

- Prevent conflicting status writes.
- Prevent duplicate submissions.
- Avoid concurrent keyboard/mouse automation.
- Coordinate standalone and unified sessions.
- Prefer OS-level named mutex or a durable local execution coordinator.
- Use server leases when centralized coordination is enabled.
- Avoid split-brain control ownership.
- Define safe behavior during network partitions.

Never use a global lock that unnecessarily blocks unrelated independent features.

# 9. TRUE BACKGROUND EXECUTION

Status Changer, Random Status, and Marquee Status must support strict no-focus execution.

Strict mode prohibits:

- Foreground window activation
- Keyboard injection
- Mouse injection
- Clipboard modification
- Focus stealing
- Global sound registry mutation
- Silent fallback to interactive mode

Use validated provider mechanisms.

Report `BACKGROUND_UNSUPPORTED` if actual Camfrog behavior prevents an operation under these constraints.

Do not report successful external status changes without authoritative verification.

Test minimized and hidden-client behavior independently.

# 10. REAL CAMFROG RUNTIME INTEGRATION

Use the genuine Camfrog Windows Client.

Requirements:

- Verify executable path and Authenticode publisher.
- Verify PID plus process creation time.
- Exclude CEF subprocesses.
- Handle multiple windows per process.
- Classify window roles by structural UI signatures.
- Support automatic read-only attachment.
- Reconnect after process restart.
- Fail closed when process selection is ambiguous.
- Never terminate unrelated or unowned processes.

Keep these states separate:

```text
PROCESS_RUNNING
UI_VISIBLE
AUTH_OBSERVED
ROOM_MEMBERSHIP_VERIFIED
STATUS_APPLIED_VERIFIED
```

Never infer authentication, room membership, or external action success from process existence alone.

# 11. CONFIGURATION AND DATA STORAGE

Use separate configuration namespaces for each feature.

Recommended application data structure:

```text
%LOCALAPPDATA%\ZChat\
    shared\
    room-control\
    chat-im-private\
    status-random\
    status-marquee\
    im-autoreply\
    web-status\
    music-dj\
    status-changer\
    line-status-changer\
    zchat-client\
```

Support local settings and centralized policies.

Define precedence explicitly:

1. Security and authorization restrictions
2. Active server-managed policy, when authorized
3. Local operator settings
4. Application defaults

Do not allow server-supplied configuration to bypass local execution safety constraints.

Use secure Windows-backed secret storage where necessary.

Perform configuration migration with backups and rollback.

# 12. BUILD AND PACKAGING

Produce:

```text
dist/
    room-control/room-control.exe
    chat-im-private/chat-im-private.exe
    status-random/status-random.exe
    status-marquee/status-marquee.exe
    im-autoreply/im-autoreply.exe
    web-status/web-status.exe
    music-dj/music-dj.exe
    status-changer/status-changer.exe
    zchat-client/zchat-client.exe
    SHA256SUMS.txt
    BUILD_SOURCE.txt

line/dist/
    line-status-changer.exe
```

Each EXE must be independently runnable.

`zchat-client.exe` must package every required feature module.

Do not depend on Python being installed on the target system.

Do not depend on the source repository existing beside the distributables.

Ensure embedded resource paths work in packaged execution.

Generate SHA256 checksums and build provenance.

# 13. AUTOMATED TESTING

Create and execute:

- Shared core unit tests
- Standalone feature contract tests
- Independent EXE smoke tests
- Unified client integration tests
- Server API integration tests
- Authentication/authorization tests
- Worker lifecycle tests
- Local/server coordination tests
- Duplicate-command tests
- Multi-application concurrency tests
- Windows background interaction tests
- Real Camfrog acceptance tests
- Config migration tests
- Packaging and clean-machine tests

Test the unified client and standalone features individually and simultaneously.

Verify that running both does not duplicate workers or cause conflicting external actions.

No mocked test may be presented as genuine Camfrog integration evidence.

# 14. REQUIRED ACCEPTANCE GATES

| Gate | Required Result |
|---|---|
| Standalone EXEs | All independently launchable |
| Unified Client | All modules accessible in one control panel |
| Code Reuse | Shared core, no duplicated business logic |
| Provider Discovery | Automatic, verified, nonintrusive |
| Feature Isolation | Independent configuration and lifecycle |
| Shared Resource Safety | No conflicting simultaneous writers |
| Background Status | No mouse/keyboard/focus interference |
| External Actions | Verified outcomes or explicit UNKNOWN |
| ZChat Server | Authenticated and scoped central control |
| Offline Behavior | Deterministic, documented, fail-safe |
| Build | Reproducible packaging and checksums |
| Tests | Actual unit, integration, Windows, and packaged EXE evidence |

# 15. GITHUB GOVERNANCE

Follow repository branch protection, required CI, and independent review requirements.

Use `policedbc` for independent review and `cvsz` for merge when both accounts are authorized.

Never force merge or bypass security checks.

Preserve an auditable commit and PR history.

# 16. REQUIRED DELIVERABLES

1. Architecture audit
2. Root cause findings
3. Shared feature core
4. Independent executable packages
5. Unified `zchat-client.exe` control panel
6. ZChat Server integration
7. Feature lifecycle and configuration management
8. Coordination and conflict protection
9. Windows live acceptance evidence
10. Test results
11. Build output and SHA256 manifests
12. Production readiness assessment
13. GitHub PR/review/merge evidence

Use:

```text
VERIFIED
IMPLEMENTED_NOT_VERIFIED
BLOCKED
FAILED
NOT_IMPLEMENTED
NOT_APPLICABLE
```

**Final requirement: Every feature must work as its own standalone EXE, while `zchat-client.exe` must contain all feature implementations in one unified control panel integrated with ZChat Server - without launching or depending on those standalone feature executables.**

Proceed with repository inspection and authorized implementation. Do not fabricate completion or bypass mandatory security and verification gates.

## 4\. Acceptance Matrix

**Implementation Acceptance Checklist** / gates

ใช้ติดตามผลการทดสอบเมื่อ Build และ E2E Verification เสร็จ

| **Feature** | **Standalone** | **Unified** |
|--------|--------|--------|

[Reset Checklist] [Copy Results]

**เป้าหมายสุดท้าย\:** ผู้ใช้สามารถเปิด `status-random.exe` เพียงตัวเดียวเพื่อใช้ Random Status หรือเปิด `zchat-client.exe` เพื่อจัดการทุก Feature จากหน้าต่างเดียว และควบคุมผ่าน `zchat-server` ได้ โดยทั้งสองรูปแบบไม่จำเป็นต้องพึ่ง EXE ของอีกฝ่าย และไม่มีการแย่ง Mouse/Keyboard จากการทำงานเบื้องหลัง

## Prompt:
10/16/2026, 11:19:10 PM

add sync lock userid ของผู้ใช้ ได้ไหม

## Response:
10/16/2026, 11:19:12 PM · gpt-6-thinking

ได้ครับ และแนะนำให้เพิ่ม **User Identity Synchronization + Distributed Lock by User ID** เข้าไปใน ZChat Architecture เพื่อป้องกัน Standalone EXEs และ `zchat-client.exe` ทำงานซ้ำหรือแย่งกันควบคุมบัญชี Camfrog เดียวกัน

โดยใช้ **User ID เป็นตัวระบุบัญชีหลัก (Canonical Identity)** แทนการอ้างอิงเพียง Nickname, PID หรือ HWND

## 1\. Proposed Architecture

```text
                  ZChat Server
               FastAPI + PostgreSQL
                        |
              User Identity Registry
                        |
             Distributed Lock Manager
                        |
         +--------------+--------------+
         |              |              |
   status-random    status-marquee   zchat-client
       .exe             .exe             .exe
         |              |              |
         +--------------+--------------+
                        |
             Canonical Camfrog User ID
                        |
               Real Camfrog Client
```

### Identity Model

ควรแยก User ID ออกเป็นสองระดับ\:

- `zchat_user_id` - UUID ภายในระบบ ZChat ใช้สำหรับ Authentication, Authorization และ Ownership
- `camfrog_user_id` - ID ของบัญชี Camfrog ที่ตรวจสอบได้จากแหล่งข้อมูลที่ได้รับอนุญาต

**หาก Camfrog User ID ยังไม่มีหลักฐานยืนยัน ห้ามสร้าง ID สมมติหรือใช้ Nickname แทนแล้วถือว่า Verified**

ให้ใช้ Internal Account UUID ผูกกับ Process Identity ที่ตรวจสอบแล้ว และรายงานสถานะ `IDENTITY_UNVERIFIED` จนกว่าจะยืนยัน External Account Identity ได้

## 2\. Locking Strategy

| Resource | Lock Key | Purpose |
|--------|--------|--------|
| Camfrog Account | `camfrog:user:{id}` | Account-level coordination |
| Status Writer | `camfrog:user:{id}:status` | ป้องกัน Random/Marquee/Changer ชนกัน |
| Room Control | `camfrog:user:{id}:room:{room_id}` | ป้องกัน Room Actions ซ้ำ |
| Private IM | `camfrog:user:{id}:im:{recipient_id}` | ป้องกันการส่งข้อความซ้ำ |
| Worker Lifecycle | `zchat:worker:{instance_id}` | ป้องกัน Worker ซ้ำ |
| LINE User | `line:user:{id}:status` | แยก Lock Domain ของ LINE |

ไม่จำเป็นต้อง Lock ทั้งบัญชีสำหรับทุก Action เพราะจะทำให้ Feature ที่ไม่ขัดแย้งกันต้องรอโดยไม่จำเป็น

## 3\. Synchronization Rules

ใช้ Lock สองระดับร่วมกัน\:

**Local Lock\:** Windows Named Mutex หรือ Local Lock Manager สำหรับ EXEs บนเครื่องเดียวกัน

**Distributed Lock\:** PostgreSQL-backed Lease หรือ Redis Lease สำหรับหลายเครื่องที่เชื่อม `zchat-server`

ต้องมี\:

- `lease_id` และ `fencing_token`
- `owner_instance_id`
- `resource_key`
- `expires_at`
- Heartbeat / Lease Renewal
- Atomic Lock Acquisition
- Safe Release
- Crash Recovery
- Replay Protection

หาก Server หลุดขณะทำงานที่ต้องการ Exclusive Ownership ให้เข้าสู่ Safe Mode และหยุด External Write ที่ไม่สามารถยืนยันสิทธิ์ได้ แทนการให้หลาย Worker ทำงานต่อพร้อมกัน

---

## 4\. Add-on Master Prompt - User ID Sync &amp; Lock

เพิ่มส่วนนี้เข้า Master Prompt ล่าสุดได้ทันที

**document: **

# PHASE 17 - CANONICAL USER IDENTITY SYNCHRONIZATION & DISTRIBUTED RESOURCE LOCKING

## Objective

Implement secure, reliable, account-scoped synchronization across all ZChat standalone executables, the unified `zchat-client.exe`, Windows runtime agents, and `zchat-server`.

The system must prevent conflicting actions against the same external account while allowing independent, non-conflicting features to run concurrently.

## 1. Canonical User Identity

Introduce an identity registry with:

- zchat_user_id: internal UUID
- zchat_account_id: internal account UUID
- provider: camfrog | line | other
- external_user_id: nullable, verified provider identity
- external_identity_verified: boolean
- identity_evidence_source
- identity_verified_at
- local_client_instance_id
- agent_instance_id

Never treat nickname, HWND, PID, or display name as a permanent account identifier.

Never infer external user identity solely from the visible window title.

Unverified accounts must not share an assumed identity.

Do not permit ambiguous identity mappings to acquire account-scoped write leases.

## 2. Account Identity Synchronization

Implement authenticated identity synchronization between:

- Standalone feature applications
- Unified ZChat Client
- Windows agents
- ZChat Server

Requirements:

1. Register each application instance with a unique instance UUID.
2. Bind the instance to an authorized internal account.
3. Synchronize verified identity metadata.
4. Detect conflicting account assignments.
5. Revalidate provider identity after account switching.
6. Revoke stale assignments when account ownership changes.
7. Avoid storing external authentication credentials.
8. Use monotonic versioning for identity assignment changes.
9. Reject cross-user and cross-tenant resource access.

## 3. Resource-Scoped Lock Manager

Implement:

```python
class ResourceLockManager:
    def acquire(self, resource_key, owner_id, ttl): ...
    def renew(self, lease_id, fencing_token): ...
    def release(self, lease_id, fencing_token): ...
    def validate(self, lease_id, fencing_token): ...
    def inspect(self, resource_key): ...
```

Support resource keys:

```text
provider/{provider}/account/{account_id}/status
provider/{provider}/account/{account_id}/room/{room_id}
provider/{provider}/account/{account_id}/im/{recipient_id}
zchat/worker/{instance_id}/{feature_id}
```

Use account IDs derived from the authorized identity registry, never unsanitized nickname input.

## 4. Local and Distributed Coordination

For local standalone applications:

- Use a Windows Named Mutex or equivalent reliable local coordinator.
- Scope mutex naming by Windows user session and account/resource identity.
- Verify lock ownership before external write operations.

For centrally managed applications:

- Use durable server-side leases backed by PostgreSQL.
- Acquire leases using atomic transactions.
- Introduce monotonically increasing fencing generations.
- Require lease validation at command execution boundaries.
- Reject stale or superseded lease holders.
- Persist lease lifecycle and audit records.

Do not rely on Redis expiry alone for correctness.

A fencing token only prevents stale effects when the execution boundary actually enforces it. For non-fence-aware third-party GUI actions, use a single local execution authority and reconcile indeterminate outcomes rather than claiming distributed exactly-once execution.

## 5. Offline Safety

When the server is unavailable:

- Standalone read-only features may continue.
- Local-only write features may operate only under an explicit, safe offline ownership policy.
- Server-managed write operations must fail closed when exclusive ownership cannot be proven.
- Do not silently switch to a second lock authority.
- Reconcile state before resuming centralized writes.

## 6. Cross-Feature Conflict Prevention

Prevent:

- status-random and status-marquee changing the same account simultaneously
- status-changer and unified client overwriting each other's status
- duplicate IM replies
- duplicate room commands
- duplicate worker startup
- stale agent commands after account reassignment

Allow independent resources to execute concurrently when safe.

## 7. Verification

Add automated tests for:

- Concurrent lock acquisition
- Lease expiration
- Lease renewal
- Crash recovery
- Stale fencing token rejection
- Duplicate command replay
- Identity switching
- Two standalone EXEs competing for one status resource
- Standalone EXE versus unified client
- Multiple Windows sessions
- Multiple Windows machines
- Server disconnect and reconnect
- Network partition
- Unauthorized cross-account access

Do not claim exactly-once external effects without provider-side support.

## 8. Acceptance Criteria

- A single external resource has at most one authorized active writer under the defined coordination model.
- Competing workers receive LOCK_CONFLICT.
- Identity changes invalidate stale write authority.
- Read-only operations remain available when safe.
- No stale worker may resume a write after losing its lease.
- No global mouse or keyboard injection is used in strict background mode.
- No unintended Camfrog window activation occurs.
- All lease transitions are auditable.
- Live tests verify concurrent standalone/unified behavior.

## Deliverables

- Identity registry and database migration
- Local Resource Lock Manager
- Distributed Lease Manager
- Shared lock client for all EXEs
- Unified client lock-state UI
- Server APIs and RBAC enforcement
- Crash/restart reconciliation
- Concurrency and security tests
- Real Windows integration evidence

Complete the implementation with explicit verification evidence and preserve all existing standalone and unified application contracts.

## 5\. สิ่งที่ควรแสดงใน Unified Control Panel

## Account Resource Locks

(UI Concept)

**Camfrog Account: REPLACE_ME_ACCOUNT**

Identity: Pending external ID verification

---

**Status Writer**

status-random.exe

(Locked)

**Marquee Status**

Waiting for status lock

(Conflict)

**Room Control**

Independent resource

(Available)

---

ตัวอย่างหน้าจอที่เสนอ ยังไม่ใช่สถานะจากระบบจริง

**ข้อสรุป\:** ผมแนะนำให้ใช้ **Canonical Account ID + Resource-Scoped Lock + Fencing Token** เป็นแกนหลัก และให้ทุก Standalone EXE กับ `zchat-client.exe` ปฏิบัติตาม Lock Contract เดียวกัน

แนวทางนี้ทำให้สามารถเปิดหลาย Feature พร้อมกันได้ โดยไม่ให้ Random Status, Marquee Status และ Unified Control Panel แย่งกันแก้สถานะของบัญชีเดียวกัน และยังรองรับการขยายไปยัง Windows หลายเครื่องผ่าน `zchat-server` ในอนาคต

## Prompt:
10/16/2026, 11:22:20 PM

เปิดหลาย Feature พร้อมกันได้ โดยไม่ให้ Random Status, Marquee Status และ Unified Control Panel แย่งกันแก้สถานะของบัญชีเดียวกัน และยังรองรับการขยายไปยัง Windows หลายเครื่องผ่าน `zchat-server`

## Response:
10/16/2026, 11:22:25 PM · gpt-6-thinking

ถูกต้องครับ นี่ควรเป็น **Core Architecture Requirement ของ ZChat** เพื่อให้ทุก Feature ทำงานพร้อมกันได้ โดยไม่มีการแย่งควบคุม Camfrog Account เดียวกัน และสามารถขยายไปยัง Windows หลายเครื่องผ่าน `zchat-server` ได้

## 1\. Architecture: Multi-Feature, Multi-Machine, Single Writer

```text
                  ZChat Server
            FastAPI + PostgreSQL
                      |
             Identity Registry
                      |
           Distributed Lease Manager
                      |
             Command Coordinator
                      |
          +-----------+-----------+
          |                       |
     Windows PC A            Windows PC B
          |                       |
   Local Lock Manager       Local Lock Manager
          |                       |
   +------+------+          +-----+------+
   |      |      |          |            |
 Random Marquee Unified    Status       Room
 Status Status  Client     Changer     Control
   |      |      |          |            |
   +------+------+----------+------------+
                      |
          Resource-Scoped Ownership
                      |
               Camfrog Accounts
```

**หลักการ\:** เปิดหลาย Feature พร้อมกันได้ แต่สำหรับบัญชีเดียวกัน ต้องมี Writer เพียงรายเดียวต่อ Resource ที่อาจขัดแย้งกัน

## 2\. การทำงานที่ต้องการ

| Scenario | Expected Behavior |
|--------|--------|
| Random Status + Marquee Status บัญชีเดียวกัน | ตัวแรกได้ Lock อีกตัวรอ |
| Status Changer + Unified Client บัญชีเดียวกัน | ไม่สามารถเขียน Status พร้อมกัน |
| Room Control + Status Changer | ทำงานพร้อมกันได้ หากไม่แย่ง Resource |
| Random Status คนละบัญชี | ทำงานพร้อมกันได้ |
| สอง Windows ควบคุมบัญชีเดียวกัน | Server กำหนด Write Authority |
| Worker Crash | Lease หมดอายุและเข้าสู่ Reconciliation |
| Server Disconnect | หยุด Server-managed Writes |
| Client Reconnect | ตรวจ Identity/Lease ใหม่ก่อน Execute |

## 3\. Implementation Contract

ควรใช้ **Account Identity + Resource Key + Lease + Fencing Generation**

```python
resource_key = (
    f"provider/camfrog/"
    f"account/{account_id}/status"
)
```

ตัวอย่าง Lock Record\:

```json
{
  "resource_key": "provider/camfrog/account/ACCOUNT_UUID/status",
  "owner_instance_id": "INSTANCE_UUID",
  "lease_id": "LEASE_UUID",
  "fencing_token": 42,
  "lease_expires_at": "2026-10-16T16:15:00Z",
  "state": "ACQUIRED"
}
```

ข้อมูลข้างต้นเป็นตัวอย่าง Schema ไม่ใช่ Lock ที่สร้างขึ้นจริง

สำหรับ Windows หลายเครื่อง PostgreSQL จะเป็น Authority กลาง ส่วน Windows Named Mutex ใช้ป้องกันการแย่งกันภายในเครื่องเดียวกัน

**ข้อจำกัดสำคัญ\:** Mutex + Lease ไม่สามารถรับประกัน exactly-once สำหรับ Camfrog GUI ที่ไม่รองรับ Fencing Token โดยตรง ต้องมี Local Execution Authority, Pre-action Validation และ Outcome Reconciliation ด้วย

## 4\. Master Prompt สำหรับเพิ่มใน ZChat

**document: **

# ZChat - Multi-Feature and Multi-Machine Resource Coordination

Repository: https://github.com/cvsz/zchat

## Objective

Implement account-aware, resource-scoped coordination across all ZChat standalone feature executables, the unified zchat-client.exe, and Windows agents connected to zchat-server.

Allow independent features to operate concurrently while preventing conflicting external actions against the same Camfrog account.

## Architecture

Use:

- Canonical ZChat Account UUID
- Verified External Provider Identity where available
- Windows Local Execution Coordinator
- PostgreSQL-backed Distributed Lease Manager
- Monotonic Fencing Generations
- Durable Command Queue
- Explicit Outcome Reconciliation

## Requirements

1. Every feature instance registers a unique instance UUID.
2. Every write operation is bound to an authorized ZChat Account UUID.
3. External user IDs must be verified before being treated as authoritative.
4. All status-changing features share the same account-scoped status resource.
5. Standalone and Unified Client modules use the same coordination contract.
6. Concurrent read-only observations remain permitted.
7. Conflicting writers must wait, reject, or cancel safely without overwriting one another.
8. Lease acquisition, renewal, and release must be atomic.
9. Server-managed writes must stop when exclusive ownership cannot be demonstrated.
10. Stale worker results must not overwrite current authoritative execution state.
11. External GUI operations with uncertain outcomes require reconciliation.
12. Never automatically retry non-idempotent actions when the effect is unknown.
13. Prevent simultaneous local and remote write authority during network partitions.
14. Preserve strict no-focus background execution requirements.
15. Never launch or terminate unrelated Camfrog processes.

## Coordination Model

Use a single cross-process local coordinator per Windows user/account identity for Camfrog GUI writes.

The coordinator must prevent concurrent execution by standalone EXEs and embedded Unified Client modules.

For distributed coordination, zchat-server grants short-lived leases and tracks fencing generations in PostgreSQL.

Acquire authority in a consistent order:

1. Validate current account identity and authorization.
2. Acquire local execution lock.
3. Acquire or validate server lease when server-managed mode is enabled.
4. Revalidate the Camfrog process and account.
5. Execute the permitted provider action.
6. Verify outcome or mark it UNKNOWN.
7. Persist result and audit evidence.
8. Release local lock and server lease safely.

Do not silently switch to offline write mode after losing the server lease.

## Testing

Add tests for:

- Random Status competing with Marquee Status
- Unified Client competing with standalone Status Changer
- Two Windows machines controlling one account
- Multiple accounts executing independently
- Worker crash while holding a lock
- Lease expiration during provider execution
- Server loss and reconnect
- Identity switching
- Duplicate commands
- Stale fencing tokens
- Unknown external outcomes
- Strict background operation without mouse/keyboard interference

## Acceptance Criteria

- At most one authorized status writer per account resource.
- Different non-conflicting features can run concurrently.
- Conflicting writers cannot bypass the shared coordinator.
- Lock ownership survives only within the valid lease.
- Stale workers cannot reacquire authority without validation.
- No unverified external action is reported as successful.
- Standalone executables remain independently runnable.
- zchat-client.exe embeds all features without launching their standalone EXEs.
- Multi-machine coordination is verified using real concurrent agents.
- All required CI, security, integration, and Windows acceptance tests pass.

Deliver implementation, migrations, tests, build outputs, failure-mode evidence, and a production-readiness verdict.

Do not claim distributed exactly-once execution unless the external provider supports enforceable idempotency or fencing.

### Architectural Decision

ผมแนะนำให้ใช้ PostgreSQL เป็น Distributed Lock Authority ของ `zchat-server` เพราะระบบ Control Server มี PostgreSQL อยู่แล้ว ลดความจำเป็นต้องเพิ่ม Redis เป็น Dependency สำหรับความถูกต้องของ Locking

สำหรับการใช้งานบนเครื่องเดียว สามารถเปิด Feature ทั้งหมดได้อย่างอิสระ แต่ **ห้ามให้แต่ละ EXE คิดว่าตัวเองเป็นเจ้าของ Camfrog Account เพียงเพราะตรวจพบ Process เดียวกัน**

เป้าหมาย Acceptance ขั้นสุดท้ายคือเปิด `status-random.exe`, `status-marquee.exe` และ `zchat-client.exe` พร้อมกัน แล้วพิสูจน์ได้ว่า Status ของบัญชีเดียวกันถูกเปลี่ยนโดย Worker ที่มีสิทธิ์เพียงตัวเดียว ในขณะที่ Feature อื่นยังทำงานได้และไม่มีการรบกวน Mouse/Keyboard

## Prompt:
10/16/2026, 11:24:16 PM

what we can do all next

## Response:
10/16/2026, 11:24:19 PM · gpt-6-thinking

ผมจะจัดลำดับงานถัดไปจากสถาปัตยกรรม ZChat ที่กำหนดไว้ และตรวจสถานะ GitHub ล่าสุดก่อน เพื่อแยกงานที่ทำแล้วออกจากงานที่ยังต้องพัฒนาและทดสอบจริงครับ

> **ตรวจสอบคอมมิตล่าสุด Pull Request และรันไทม์บน Windows**
>
> 
>
> ประมวลผล 36s

# ZChat - Complete Next Roadmap

**เป้าหมาย\:** ยกระดับ `cvsz/zchat` ให้เป็นระบบที่รองรับ Standalone EXEs, Unified Control Panel, Central Server, User ID Synchronization และ Multi-Machine Orchestration โดยทุก Feature ทำงานพร้อมกันได้โดยไม่แย่งกันควบคุมบัญชี Camfrog หรือรบกวน Mouse/Keyboard

จากการตรวจ GitHub ล่าสุด ยังพบว่า `main` อยู่ที่ Commit `6ba80e6`, PR \#44 ยังเปิดอยู่ และยังไม่พบ `camfrog_windows_runtime.py` บน `main` ดังนั้นงานที่ Codex รายงานว่าเสร็จแล้วอาจยังอยู่ใน Local Working Tree หรือ Branch อื่น

## 1\. Roadmap ทั้งระบบ

**Phase 0 - Consolidate &amp; Audit**

ตรวจ Local Changes, Runtime Tests, PR \#44, CI, Security และย้ายงานที่ยืนยันแล้วเข้ากระบวนการ Review

(In progress / verification needed)

---

**Phase 1 - True Background Engine**

ทำให้ Status Changer, Random และ Marquee เปลี่ยนสถานะได้โดยไม่แย่ง Focus, Mouse, Keyboard, Clipboard หรือแก้ Windows Sound Settings

---

**Phase 2 - User Identity &amp; Lock Manager**

เพิ่ม Canonical Account UUID, Windows Local Lock, PostgreSQL Lease, Fencing Generation และ Reconciliation

---

**Phase 3 - Shared Feature Core**

Refactor Feature Logic ให้ Standalone EXEs และ Unified Client ใช้งาน Core เดียวกัน ลด Code Duplication

---

**Phase 4 - Unified Control Panel**

พัฒนา `zchat-client.exe` ให้รวมทุก Feature เป็น Modules ในแอปเดียว พร้อม Dashboard, Config, Worker Controls และ Logs

---

**Phase 5 - ZChat Server &amp; Multi-Machine**

ขยาย FastAPI/PostgreSQL สำหรับ Agent Registry, Identity Synchronization, Distributed Leases, Command Queue และ Realtime Events

---

**Phase 6 - Build, E2E &amp; Release**

ทดสอบ 10 EXEs, Multi-Feature Concurrency, Windows หลายเครื่อง, Security, Backup/Restore และ Release Integrity

## 2\. Priority Matrix

| Priority | Workstream | Acceptance |
|--------|--------|--------|
| P0 | Commit/PR reconciliation | Source และ CI Evidence ตรงกัน |
| P0 | Nonintrusive Status Engine | ไม่แย่ง Desktop Focus |
| P0 | Per-account Single Writer | ไม่มี Status Writer ซ้ำ |
| P0 | Fail-closed external actions | ไม่มี False Success |
| P1 | 1 Feature = 1 EXE | เปิดและทำงานแยกกัน |
| P1 | Unified Client | รวมทุก Feature โดยไม่เปิด Feature EXE |
| P1 | Identity Registry | User/Account Mapping ตรวจสอบได้ |
| P1 | Centralized Control | Server Sync และ RBAC |
| P1 | Multi-Machine Leases | ไม่มี Write Authority ซ้อนกัน |
| P2 | Realtime Dashboard | แสดงสถานะ/เหตุการณ์จริง |
| P2 | Self-update &amp; Recovery | อัปเดตและ Rollback ได้ |
| P2 | Production Observability | Metrics, Logs และ Alerts |

**ข้อจำกัดสำคัญ\:** ถ้า Camfrog ไม่รองรับ Status Update โดยไม่ต้องใช้ Foreground UI จริง จะไม่สามารถรับประกัน True Background ได้ด้วยการ Refactor เพียงอย่างเดียว ต้องใช้ Interface ที่ได้รับอนุญาตและตรวจสอบผลได้ หรือรายงาน Unsupported อย่างถูกต้อง

## 3\. Master Execution Prompt - Do All Next

สามารถนำคำสั่งนี้ไปใช้กับ Codex/Kilo ที่กำลังทำงานอยู่บน `D:\data\zchat` ได้ทันที

**document: **

# ZCHAT - EXECUTE ALL NEXT PHASES

Repository: https://github.com/cvsz/zchat

Workspace: D:\data\zchat

## MISSION

Continue from the existing working tree and completed Camfrog 8.5 runtime investigation.

Do not restart the project, overwrite unfinished changes, or duplicate already implemented functionality.

Complete the remaining ZChat architecture incrementally through verified, reviewable changes.

## PHASE 0 - RECONCILE CURRENT WORK

1. Inspect Git status, current branch, local commits, untracked files, and open PRs.
2. Read AGENTS.md, CLAUDE.md, existing architecture, and current test documentation.
3. Identify which reported runtime features exist locally but have not reached GitHub.
4. Audit PR #44 and resolve any remaining CI or security problems.
5. Preserve all user changes and existing application configuration.
6. Establish a verified baseline before new implementation.

## PHASE 1 - BACKGROUND STATUS ENGINE

Implement and test strict nonintrusive execution for:

- status-changer.exe
- status-random.exe
- status-marquee.exe

Requirements:

- No focus stealing
- No global keyboard injection
- No mouse injection
- No clipboard replacement
- No system sound registry mutation
- Safe minimized/hidden client handling
- Real external status verification
- No false success
- No automatic foreground fallback

Preserve interactive mode as an explicit separate mode.

## PHASE 2 - CANONICAL IDENTITY AND LOCKING

Implement:

- Canonical ZChat Account UUID
- Verified external identity mapping when available
- Windows local execution coordination
- PostgreSQL-backed distributed leases
- Resource-scoped locking
- Lease renewal and expiry
- Monotonic fencing generation
- Idempotency and outcome reconciliation
- Cross-account authorization checks

All status writers must compete for the same account-scoped status resource.

Do not automatically create independent offline write authority after a server connection failure.

## PHASE 3 - SHARED FEATURE CORE

Extract reusable feature logic without breaking existing entrypoints.

Provide shared abstractions for:

- Feature Lifecycle
- Provider Discovery
- Background Execution
- Configuration
- Scheduling
- Structured Logging
- Status Verification
- Resource Locking
- Reconnection and Recovery

Use the same implementation from standalone applications and unified client modules.

## PHASE 4 - STANDALONE DISTRIBUTIONS

Preserve and validate one executable per feature.

Every standalone feature must be independently packaged and runnable.

Do not require another ZChat executable or the development Python installation.

Each feature must have isolated configuration, logs, worker state, and error reporting.

## PHASE 5 - UNIFIED ZCHAT CLIENT

Implement zchat-client.exe as a single integrated control panel.

Embed all feature modules directly.

Do not use the standalone feature executables as implementation dependencies.

Provide:

- Dashboard
- Feature Navigation
- Start/Stop/Restart
- Account Selection
- Feature Configuration
- Resource Lock Status
- Background Worker Status
- Logs and Audit
- Server Connection
- Error Diagnostics
- Global Emergency Stop for ZChat-owned actions

Ensure the unified client and standalone applications obey identical resource coordination rules.

## PHASE 6 - ZCHAT SERVER

Extend the existing FastAPI/PostgreSQL control server.

Implement:

- User and Account Registry
- Agent and Machine Registry
- Feature Registration
- Device/Account Assignments
- Resource Leases
- Durable Command Queue
- Feature Configuration Synchronization
- Event Synchronization
- Health and Readiness
- RBAC and Audit
- Secure Reconnection
- Server-controlled scheduling

Use existing migrations and conventions.

Never execute unverified external provider operations merely because an API request succeeded.

## PHASE 7 - MULTI-MACHINE ACCEPTANCE

Test at least:

1. Two status applications on one Windows machine and the same account.
2. One standalone application competing with the unified client.
3. Different accounts executing independent features concurrently.
4. Two Windows agents competing for the same account through zchat-server.
5. Worker crash and restart.
6. Network partition and server disconnection.
7. Lease expiry during an external operation.
8. Account switching and stale ownership.
9. Duplicate command delivery.
10. Reconciliation after uncertain external effects.

Use real multi-machine evidence for claims about multi-machine correctness.

Simulations alone are insufficient.

## PHASE 8 - BUILD AND RELEASE

Run relevant tests, security analysis, packaging checks, and genuine Windows acceptance tests.

Rebuild affected executables using existing build workflows.

Verify:

- Standalone launch
- Unified feature functionality
- No feature-EXE dependencies
- No desktop input interference
- No conflicting external writers
- Correct account association
- Clean shutdown
- Crash recovery
- Build provenance
- SHA256 checksums

Maintain separation between build success and runtime acceptance.

## PHASE 9 - GITHUB REVIEW

Create small, reviewable Pull Requests grouped by concern.

Use the authorized independent reviewer account policedbc.

Use cvsz for eligible merges.

Never bypass branch protection, security checks, or required approvals.

Do not merge unverified production-impacting changes.

## FINAL REPORT

For every phase, report:

- Completed implementation
- Actual changed files
- Commits and Pull Requests
- Tests executed
- Actual PASS/FAIL results
- Runtime evidence
- Remaining blockers
- Security risks
- Deployment readiness
- Next action

Use VERIFIED, IMPLEMENTED_NOT_VERIFIED, BLOCKED, FAILED, or NOT_IMPLEMENTED.

Proceed with safe autonomous execution, prioritizing P0 correctness, preserving existing work, and stopping at authorization boundaries.

The final system must support:

**1 Feature = 1 Standalone EXE**

**zchat-client.exe = All Features in One Control Panel**

**zchat-server = Central Multi-Machine Control Plane**

**1 Account + 1 Conflicting Resource = At Most 1 Authorized Writer**

**Strict Background = No Desktop Input Interference**

Never claim complete production readiness without corresponding real acceptance evidence.

## 4\. ตรวจสภาพก่อนเริ่ม Phase ถัดไป

บน Windows 11 ใช้คำสั่งนี้เพื่อให้ Agent ทราบสถานะ Working Tree ปัจจุบัน\:

```powershell
cd D:\data\zchat

git status --short --branch
git log -3 --oneline
git diff --stat

gh pr list --repo cvsz/zchat --state open
gh run list --repo cvsz/zchat --limit 10

.\.venv-runtime\Scripts\python.exe -m pytest `
  tests/test_camfrog_windows_runtime.py `
  tests/test_camfrog_auto.py `
  tests/test_windows_process_commands.py -q
```

คำสั่งเป็นการตรวจสอบ ไม่ Commit, Push หรือ Merge และผล Tests ต้องอ้างอิงจากการรันจริง หากไฟล์ทดสอบยังไม่อยู่ใน Working Tree ต้องรายงานว่าไม่พบแทนการตีความว่า Tests Failed

## 5\. Release Milestones

**ZChat Production Gates** /

Checklist สำหรับบันทึกผลภายหลังการตรวจ Acceptance Evidence ไม่ใช่สถานะ CI ปัจจุบัน

[Copy Gate Report]

**ลำดับแนะนำ\:** เริ่ม Phase 0 → 1 → 2 ก่อน เพราะทั้ง Background Status และ Locking เป็นฐานด้าน Reliability ที่ต้องแข็งแรงก่อนรวมทุก Feature เข้า `zchat-client.exe` และกระจายการควบคุมไปยังหลายเครื่อง

เมื่อสามส่วนแรกผ่านจริงแล้ว จึงดำเนิน Standalone Packaging, Unified Client และ Multi-Machine Server Integration ต่อโดยลดความเสี่ยงจากการทำงานซ้ำหรือแย่งควบคุมบัญชีเดียวกัน

## Prompt:
10/16/2026, 11:45:31 PM

▾ Thought for 7s
  The code utilizes `psutil` in process discovery and identity validation. The presence of `psutil`
  needs verification within the project's dependency file to ensure proper setup. A dependency check is
  necessary as `psutil`'s absence in the dependencies would indicate a potential installation or
  fallback mechanism oversight.
  Here is the current status across active tracks and recommendations for following up:
  ──────
  ### 1. Active Pull Request #44 https://github.com/cvsz/zchat/pull/44 (fix/ui-room-control-pid-
  exclusion)
  • Status: Approved by policedbc, all 9 CI checks passing (CodeQL, Ubuntu tests, Windows build,
  Control Server, Dependency Review).
  • Scope: Exclude self-PID and fail closed in room_control_gui.py when verifying single Camfrog
  process instances.
  • Action: Ready to merge into main (e.g. gh pr merge 44 --squash --delete-branch).
  ──────
  ### 2. Working Tree & Git State

  • Rebase state: A leftover no-op interactive rebase on feat/web-status-log-marquee (PR #42,
  already merged into main) is active in .git/rebase-merge. Running git rebase --abort will clean
  this state without impacting working files.
  • Repository health: validate_repo.py passed cleanly (structure and Markdown links valid).
  ──────
  ### 3. New Runtime Integration (Uncommitted Work in Tree)

  New implementation modules and live Windows 11 evidence artifacts for Camfrog 8.5 have been
  prepared:
  • camfrog_windows_runtime.py: Authenticode verification (WinVerifyTrust, CryptQueryObject),
  structural window classification (Internet Explorer_Server, VideoViewport, CTreeViewTS,
  CComboBoxTS), client attachment, and state separation.
  • camfrog_status_engine.py: Background status execution engine eliminating desktop disruption
  (removes registry sound modification, no focus stealing).
  • test_camfrog_windows_runtime.py: Unit test suite (needs psutil added to requirements.txt or
  mocked for the headless Linux test suite).
  • main-process.json: Live capture evidence from PID 21992 on Windows 11.
  ──────
  ### How would you like to proceed?

  1. Merge PR #44 into main and sync the local branch.
  2. Clean git rebase state (git rebase --abort) and create a dedicated feature branch for the
  Windows 8.5 runtime integration (camfrog_windows_runtime.py + camfrog_status_engine.py).
  3. Address psutil dependency & tests so the runtime test suite passes under Linux CI.

## Response:
10/16/2026, 11:46:16 PM · gpt-6-thinking

> **ตรวจสอบสถานะ PR และการตรวจสอบก่อนผสาน**
>
> 
>
> ประมวลผล 24s

## ZChat - Recommended Execution: ทำทั้ง 3 งานตามลำดับ

จากรายงานล่าสุด แนะนำให้ Codex **ดำเนินการทั้ง 3 ข้อ ไม่ต้องเลือกเพียงข้อเดียว** โดยเน้นรักษา Local Changes และไม่ทำให้ Runtime Integration ที่พัฒนาไว้สูญหาย

ลำดับที่เหมาะสม\:

1. **Merge PR \#44** หลังยืนยัน CI, independent review และ Branch Protection ล่าสุด
2. **Resolve Git Rebase State** โดยสำรองงานที่ยังไม่ Commit ก่อน ตรวจสอบว่า Rebase ไม่มีการเปลี่ยนแปลงสำคัญ แล้วจึง `git rebase --abort` เฉพาะเมื่อปลอดภัย
3. **Fix `psutil` Dependencies และ Linux CI** พร้อมทดสอบ `camfrog_windows_runtime.py` และ `camfrog_status_engine.py`
4. **สร้าง Feature Branch + PR** สำหรับ Real Runtime Integration และ True Background Status Changer
5. **Verify Real Camfrog Behavior** โดยเฉพาะการเปลี่ยน Status ขณะ Camfrog Minimized โดยไม่แย่ง Mouse/Keyboard

ข้อควรระวัง: แม้ `psutil` จะติดตั้งใน `.venv-runtime` แล้ว แต่ยังต้องระบุ Runtime Dependency ใน Project Metadata ที่ใช้ Build จริง และไม่ควรให้ Linux CI พยายามเรียก Windows-only APIs โดยไม่มี Platform Guard

## อัปเดตผลตรวจ GitHub จริง

ตรวจสอบ [github.com](https://github.com/cvsz/zchat/pull/44?utm_source=chatgpt.com) อีกครั้ง พบว่า\:

(Merged) PR \#44 ปิดและ Merge เรียบร้อยแล้ว

CI ทั้ง 9 Check Runs แสดง `completed / success` รวมถึง CodeQL, Windows Build, Dependency Review และ Tests

ดังนั้น **ไม่ต้อง Merge PR \#44 ซ้ำ** และสามารถไปทำขั้นตอน Git Rebase Cleanup กับ Runtime Integration ต่อได้เลย

### Prompt สำหรับ Codex

**standard: **

Proceed autonomously with the remaining ZChat implementation work.

Repository: cvsz/zchat
Local workspace: D:\data\zchat

PR #44 is already merged. Do not attempt to merge it again.

1. Inspect and preserve all local changes, untracked files, and active rebase metadata.
2. Create a safe backup of the current working state before modifying Git history or aborting the stale rebase.
3. Resolve the obsolete PR #42 rebase state without losing current work.
4. Synchronize with origin/main using a non-destructive approach.
5. Create a dedicated feature branch for Camfrog 8.5 Windows Runtime and Background Status Engine.
6. Verify that psutil is declared in the appropriate runtime/build dependency files and that packaged EXEs include its native Windows extension.
7. Ensure Windows-specific modules are safely isolated from Linux CI, without skipping portable business logic tests.
8. Complete strict background status execution: no foreground activation, global keyboard/mouse injection, clipboard modification, or Windows sound registry changes.
9. Test against the genuine Camfrog 8.5 client, including minimized, hidden, and foreground-owned-by-another-application scenarios.
10. Integrate resource-scoped synchronization so Random, Marquee, and Unified Client cannot simultaneously write the same account status.
11. Run all relevant unit, regression, security, Windows acceptance, and packaged EXE smoke tests.
12. Create a reviewable Pull Request, request independent review from policedbc, and merge with cvsz only after required gates pass.

Report actual results, changed files, commit hashes, test evidence, and unresolved blockers.

Never claim that a successful UI text write or Windows message dispatch proves the status was applied by Camfrog.

Preserve all existing standalone features and the future unified zchat-client.exe architecture.

**Current state\:** PR \#44 = `MERGED`; Windows Runtime และ Background Status Engine = มีรายงานว่าพัฒนาอยู่ใน Local Working Tree แต่ยังต้องยืนยันการ Commit, CI และ Live Background Acceptance.

## Prompt:
10/17/2026, 12:03:29 AM

rewrite full master prompt  "  "

[Attachment: ข้อความที่วาง (1)(20261016-170324).txt]

## Response:
10/17/2026, 12:03:30 AM · gpt-6-thinking

# ZCHAT - ULTIMATE MASTER ENGINEERING PROMPT V4.0

**Repository\:** [github.com](https://github.com/cvsz/zchat?utm_source=chatgpt.com)
**Workspace\:** `D:\data\zchat`
**Target\:** Windows 11 · Camfrog Video Chat 8.5.0.51219 · Python 3.14
**Architecture\:** Standalone EXEs + Unified Client + Central Server + Multi-Machine Coordination

ผมรวมและปรับปรุง Prompt จากเอกสารที่แนบและข้อกำหนดล่าสุดทั้งหมด ให้เป็น **Master Prompt เดียว** สำหรับ Codex, Kilo CLI หรือ Autonomous Engineering Agent โดยเน้น 5 เป้าหมายหลัก\:

1. ทุก Feature ทำงาน Standalone ได้ - `1 Feature = 1 EXE`
2. `zchat-client.exe` รวมทุก Feature เป็น Unified Control Panel
3. `zchat-server` จัดการ Account, User ID, Agents และ Windows หลายเครื่อง
4. ทุก Feature ทำงานเบื้องหลังโดยไม่รบกวน Mouse, Keyboard, Focus, Clipboard หรือ Windows Sound Settings ในโหมด Strict Background
5. ป้องกันหลาย Feature แย่งควบคุมบัญชีเดียวกันด้วย Canonical Identity, Local Locks และ Distributed Leases

Prompt จะสั่งให้ Agent ตรวจงานที่ทำไปแล้วก่อน ไม่เขียนใหม่โดยไม่จำเป็น ไม่ทำลาย Local Changes และไม่ประกาศ Production Ready โดยไม่มีหลักฐานจริง

**document: **

# ZCHAT - ULTIMATE MASTER ENGINEERING & EXECUTION PROMPT V4.0

## Autonomous Full-Stack Engineering, Real Camfrog Integration, Standalone Windows Applications, Unified Control Panel, Distributed Resource Coordination & Production Readiness

**Repository:** https://github.com/cvsz/zchat  
**Local Workspace:** `D:\data\zchat`  
**Target OS:** Windows 11  
**Python:** 3.14  
**Camfrog Client:** 8.5.0.51219  
**Execution Strategy:** Investigate → Preserve → Repair → Refactor → Implement → Verify → Build → Review → Release

---

# 1. ROLE AND ENGINEERING MISSION

You are an autonomous multidisciplinary engineering agent operating as:

- Principal Software Architect
- Senior Python / Windows Engineer
- Senior Full-Stack Engineer
- Windows Runtime and UI Automation Engineer
- Distributed Systems Architect
- Security Auditor
- Database and DevOps Engineer
- QA Automation Engineer
- Release and Reliability Engineer

Your mission is to investigate, stabilize, refactor, integrate, test, package, and harden the entire ZChat ecosystem.

You must work from the actual repository, actual source code, actual local working tree, actual GitHub state, and actual Windows runtime evidence.

Do not treat plans, summaries, mocked tests, or previous agent reports as proof of completed functionality.

## Primary success requirements

**A. One Feature = One Standalone EXE**

Every existing ZChat feature must run independently from its packaged Windows executable.

**B. One Unified Client = All Features**

`zchat-client.exe` must integrate all feature modules within one application. It must not launch standalone feature EXEs to implement their functionality.

**C. One Central Server = Coordinated Operations**

`zchat-server` must coordinate authorized users, accounts, machines, agents, commands, configurations, events, and resource ownership.

**D. One Account + One Conflicting Resource = At Most One Authorized Writer**

Conflicting features must never concurrently control the same external account resource under the defined coordination model.

**E. Strict Background = Zero Intrusive Desktop Input**

No focus stealing, global keyboard or mouse injection, clipboard manipulation, automatic Camfrog window restoration, or Windows sound registry modification.

**F. Evidence Before Success**

A successful API request, Windows message dispatch, UI text write, process launch, or completed build must never be misrepresented as a verified external effect.

---

# 2. NON-NEGOTIABLE OPERATING RULES

1. Inspect `AGENTS.md`, `CLAUDE.md`, repository architecture, coding conventions, and existing governance before modifying code.
2. Preserve all working functionality unless a change is necessary and backed by tests.
3. Prefer minimal, modular, maintainable fixes rather than unnecessary rewrites.
4. Preserve uncommitted local work, user configuration, and existing test evidence.
5. Do not run destructive Git commands without inspecting their impact.
6. Never claim tests passed unless they were executed and the actual results were captured.
7. Never claim code was committed, pushed, reviewed, merged, deployed, or released unless independently verified.
8. Never modify, inject into, patch, or redistribute proprietary Camfrog binaries.
9. Use authorized Windows UI Automation and permitted provider interfaces.
10. Never bypass authentication, CAPTCHA, licensing, account restrictions, or platform protections.
11. Never store Camfrog passwords, browser cookies, CSRF token values, payment credentials, or private session material in ZChat diagnostics.
12. Do not expose private chat messages, account contact details, or raw UI dumps in a public repository.
13. Do not suppress Windows Defender, security alerts, accessibility notifications, or system-wide audio.
14. Communicate operator reports in Thai. Keep source code, technical identifiers, documentation, commits, and PR descriptions in English.
15. Continue safely and autonomously where authorized, but stop at destructive operations, missing permissions, third-party restrictions, or production-impacting approval boundaries.

---

# 3. BASELINE AND CURRENT STATE RECONCILIATION

Before implementing anything, reconcile:

- Local working-tree state
- Remote GitHub state
- Open and merged Pull Requests
- CI results
- Untracked source files
- Existing feature branches
- Active rebase or merge operations
- Runtime test artifacts
- Packaged executables

## Important known context

PR #44 was confirmed merged with successful CI checks during the previous GitHub review.

Do not attempt to merge it again without checking the latest GitHub state.

The local workspace was reported to contain:

- `camfrog_windows_runtime.py`
- `camfrog_status_engine.py`
- Windows runtime tests
- Sanitized Camfrog process evidence
- An unfinished or obsolete Git rebase state

These are reported local conditions, not verified current state.

Check whether the files and rebase metadata actually exist.

## Safe Git workflow

Inspect:

```powershell
git status --short --branch
git branch -vv
git log -5 --oneline
git diff --stat
git diff --check
git reflog -10
gh pr list --repo cvsz/zchat --state open
gh run list --repo cvsz/zchat --limit 10
```

Before resolving an unfinished rebase:

1. Inspect `.git/rebase-merge` or `.git/rebase-apply`.
2. Identify the original branch and current rebase target.
3. Preserve uncommitted and untracked changes.
4. Create a recoverable backup.
5. Confirm whether the rebase is obsolete.
6. Abort only if it is safe.
7. Never use `git reset --hard`, `git clean -fd`, or force push as a shortcut.
8. Reconcile changes against the current `origin/main`.

Do not delete any local work based solely on prior agent statements.

---

# 4. VERIFIED CAMFROG RUNTIME BASELINE

Previous operator-provided Windows observations:

```text
Application: Camfrog Video Chat
Version: 8.5.0.51219
Publisher: Camfrog LLC
Authenticode: Valid

SHA256:
0B744602C004536DCF81E9965E8CB17358EB276B3876A1E70C50F72777C27E06

Observed PID: 21992

Observed Windows:
5177812  - IM / account-related window
33360162 - Room UI window
3149540  - Main directory window
```

Historical PIDs and HWNDs are evidence references only.

Never hardcode them as current runtime targets.

## Observed structural signatures

### IM UI

```text
Internet Explorer_Server
camfrog://wb-log-im-data.inside/
```

### Room UI

```text
VideoViewport
camfrog://wb-log-room-data.inside/
```

### Main Client

```text
CTreeViewTS
CComboBoxTS / Automation ID 1436
Edit / Automation ID 1001
```

These signatures may change between Camfrog versions.

Verify current UI structure before using any selector.

---

# 5. PHASE 1 - DEEP REPOSITORY INVESTIGATION

Inspect the complete relevant source and execution paths.

Mandatory targets include:

```text
camfrog_auto.py
camfrog_windows_runtime.py
camfrog_status_engine.py
camfrog_gui.py
camfrog_presence.py

room_control_gui.py
status_changer_gui.py
status_random_gui.py
status_marquee_gui.py
camfrog_status_gui.py

status_changer_entry.py
status_random_entry.py
status_marquee_entry.py

web_status_gui.py
tools/web_status.py

control-server/
zchat-client/

line/
tests/
windows_tests/
docs/
.github/workflows/
```

Do not assume optional files exist.

For each relevant component, identify:

- Entry point
- Dependencies
- Process ownership
- User/account scope
- Configuration source
- Worker lifecycle
- External side effects
- Authentication and authorization
- Error handling
- Retry behavior
- Logging
- Test coverage
- Build and packaging integration

Deliver an inventory of VERIFIED, PARTIAL, BLOCKED, and MISSING implementations.

---

# 6. PHASE 2 - REAL WINDOWS PROCESS AND WINDOW INTEGRATION

Implement or complete the reusable Windows runtime foundation.

Required components:

```text
WindowsCamfrogProcessDiscovery
WindowsCamfrogWindowClassifier
CamfrogClientAttachment
CamfrogProcessIdentity
CamfrogWindowIdentity
ClientRuntimeState
```

## Process requirements

- Discover the genuine `Camfrog Video Chat.exe`.
- Verify executable path.
- Verify Authenticode signature and expected publisher.
- Track PID plus creation time.
- Exclude CEF helper processes.
- Exclude ZChat's own windows and processes.
- Support multiple windows belonging to the same Camfrog process.
- Detect multiple separate Camfrog processes.
- Fail closed when process-to-account mapping is ambiguous.
- Revalidate identities immediately before external actions.

## Window classification

Identify:

```text
MAIN_DIRECTORY
ACCOUNT_WINDOW
ROOM_WINDOW
PRIVATE_IM_WINDOW
UNKNOWN
```

Use structural UI signatures rather than titles alone.

Do not infer account login solely from process presence.

Do not infer current room membership from a historical room window.

Do not infer online presence from a control's label alone.

Do not terminate Camfrog processes that the agent did not launch.

---

# 7. PHASE 3 - AUTOMATIC DISCOVERY AND RECONNECTION

Every Camfrog-dependent standalone executable and the unified client must:

1. Start without requiring manual Camfrog discovery.
2. Discover a single unambiguous verified running client automatically.
3. Attach in read-only mode by default.
4. Report `CLIENT_NOT_RUNNING` if Camfrog is absent.
5. Continue bounded asynchronous discovery.
6. Reconnect safely if the client starts or restarts.
7. Detach when the client exits.
8. Require explicit account/process selection when ambiguous.
9. Never automatically launch, terminate, restore, or focus Camfrog.
10. Never automatically perform external write operations solely because attachment succeeded.

Discovery must not freeze the GUI.

Persist safe preferences, not transient PIDs or HWNDs as permanent identities.

---

# 8. PHASE 4 - TRUE BACKGROUND EXECUTION

Implement strict background execution for all applicable features, prioritizing:

```text
status-changer.exe
status-random.exe
status-marquee.exe
```

## Strict background prohibitions

Do not invoke:

```python
win.set_focus()
ctrl.set_focus()
ctrl.click_input()
ctrl.type_keys()
keyboard.send_keys()
user32.SetForegroundWindow()
```

Also prohibit:

- Global keyboard injection
- Global mouse injection
- Cursor movement
- Clipboard replacement
- Automatic window activation
- Automatic foreground fallback
- Global Windows sound registry changes

An explicit interactive execution mode may remain available as a separate option.

Background failure must never silently trigger interactive behavior.

## Required execution path

```text
DISCOVER_PROCESS
      ↓
VERIFY_PROCESS
      ↓
RESOLVE_ACCOUNT
      ↓
ACQUIRE_RESOURCE_LOCK
      ↓
DISCOVER_STATUS_CONTROL
      ↓
VERIFY_CONTROL_IDENTITY
      ↓
WRITE_WITHOUT_FOREGROUND
      ↓
VERIFY_TEXT_READBACK
      ↓
SUBMIT_WITHOUT_GLOBAL_INPUT
      ↓
VERIFY_EXTERNAL_OUTCOME
      ↓
RECORD_AUDIT
      ↓
RELEASE_LOCK
```

Use supported UI Automation and validated Windows control operations.

If minimized or hidden UI cannot complete the requested action, return `BACKGROUND_UNSUPPORTED`.

Do not falsify success by reporting that an Edit control received text.

---

# 9. PHASE 5 - REMOVE UNSAFE WINDOWS SOUND MUTATION

Audit:

```text
winreg
AppEvents
SystemAsterisk
SystemExclamation
SystemNotification
MessageBeep
Beep
winsound
```

Remove code that temporarily modifies HKCU Windows sound-event registry values during status submission.

Do not alter system-wide sound settings to suppress a provider-generated beep.

Repair the underlying interaction behavior where possible.

If the genuine provider produces unavoidable audio, document the limitation.

Preserve security alerts and accessibility behavior.

---

# 10. PHASE 6 - CANONICAL USER IDENTITY

Implement secure user/account identity mapping.

Distinguish:

```text
zchat_user_id
zchat_account_id
provider
verified_external_user_id
agent_instance_id
machine_id
client_instance_id
```

Use UUIDs for internal identities.

Never treat nickname, display name, HWND, or PID as a permanent user ID.

Never manufacture an external Camfrog User ID when no authoritative source is available.

Store verification source and timestamp.

Revalidate identity before external account writes.

On account switching:

- Invalidate stale assignments.
- Revoke obsolete write authority.
- Clear stale runtime state.
- Require resource ownership to be reacquired.
- Prevent cross-account and cross-user access.

---

# 11. PHASE 7 - LOCAL AND DISTRIBUTED RESOURCE LOCKING

Implement a shared coordination system used by:

- All standalone EXEs
- Unified Client modules
- Windows agents
- ZChat Server

## Resource keys

```text
provider/camfrog/account/{account_id}/status
provider/camfrog/account/{account_id}/room/{room_id}
provider/camfrog/account/{account_id}/im/{recipient_id}
provider/line/account/{account_id}/status
```

## Required lock data

```text
resource_key
owner_instance_id
lease_id
fencing_generation
acquired_at
expires_at
renewed_at
state
```

## Local coordination

Use Windows Named Mutex or a reliable local execution coordinator.

A single conflicting external resource must not have multiple local writers.

Different non-conflicting features may operate concurrently.

## Distributed coordination

Use PostgreSQL-backed server leases with atomic transactions and monotonic fencing generations.

Requirements:

- Atomic acquisition
- Lease renewal
- Safe release
- Expiry handling
- Crash recovery
- Replay rejection
- Ownership validation
- Audit history
- Reconciliation after uncertain external effects

Do not rely on Redis TTL alone for correctness.

A fencing token does not provide exactly-once behavior unless the execution boundary enforces it.

For Camfrog GUI operations that cannot enforce remote fencing directly, use a single authorized local execution authority and reject stale commands.

When server-managed ownership becomes uncertain, stop external writes.

Never silently switch to an independent offline lock authority.

---

# 12. PHASE 8 - SHARED FEATURE CORE

Refactor duplicated logic into shared source modules.

Required functional abstractions:

```text
FeatureModule
FeatureContext
FeatureLifecycleManager
ProviderRegistry
ConfigurationManager
BackgroundExecutionEngine
ResourceLockManager
StatusVerificationProvider
Scheduler
AuditLogger
```

Each Feature Module should expose equivalent lifecycle operations:

```python
initialize()
start()
stop()
restart()
get_status()
validate_config()
health_check()
```

Asynchronous implementations are permitted where appropriate.

Required lifecycle states:

```text
NOT_CONFIGURED
STOPPED
STARTING
RUNNING
DEGRADED
FAILED
STOPPING
```

Do not duplicate business logic between standalone and unified applications.

Do not rewrite unrelated functionality merely to introduce abstraction.

---

# 13. PHASE 9 - ONE FEATURE = ONE STANDALONE EXE

Preserve independent feature packages:

```text
room-control.exe
chat-im-private.exe
status-random.exe
status-marquee.exe
im-autoreply.exe
web-status.exe
music-dj.exe
status-changer.exe
line-status-changer.exe
```

Each EXE must:

- Launch independently.
- Package required runtime dependencies.
- Operate without another ZChat EXE.
- Operate without developer Python installation.
- Manage its own configuration and logs.
- Discover its external provider automatically where applicable.
- Expose Start/Stop controls.
- Recover from bounded transient failures.
- Shut down only its own workers.
- Preserve user data during upgrades.
- Avoid collisions with other ZChat applications.

External Camfrog or LINE dependencies must be documented separately.

Standalone means independent of other ZChat executables, not independent of every external provider.

---

# 14. PHASE 10 - UNIFIED ZCHAT CLIENT

Transform `zchat-client.exe` into a unified control panel containing all supported feature modules.

Do not implement unified features by launching standalone feature EXEs.

Required modules:

```text
Dashboard
Accounts
Camfrog Runtime
Room Control
Private IM
Random Status
Marquee Status
IM Auto Reply
Web Status
Music DJ
Status Changer
LINE Status
Schedulers
Workers
Resource Locks
Audit Logs
Settings
Diagnostics
```

Required functionality:

- Feature navigation
- Feature configuration
- Start/Stop/Restart
- Account selection
- Provider discovery
- Server connectivity
- Resource lock visibility
- Worker state
- Event history
- Error diagnostics
- Global Stop All for ZChat-owned actions

Every feature must use the shared runtime and resource coordination contract.

The unified client must never terminate an unrelated provider process.

---

# 15. PHASE 11 - ZCHAT SERVER CONTROL PLANE

Build upon the existing FastAPI/PostgreSQL implementation.

Implement or complete:

```text
User Registry
Account Registry
Machine Registry
Agent Registry
Feature Registry
Resource Lease Manager
Command Queue
Configuration Synchronization
Job Scheduler
Event Synchronization
Audit Trail
Health and Readiness
```

Required security:

- JWT lifecycle and revocation
- RBAC
- Resource-scoped authorization
- Agent token rotation
- TLS transport
- Idempotency
- Durable command claims
- Lease fencing
- Request validation
- Log redaction
- Secret management
- Rate limiting appropriate to deployment topology

Do not treat a command acknowledgement as confirmation that Camfrog completed an external action.

Use explicit outcome states.

---

# 16. PHASE 12 - STATUS AND EVIDENCE BOUNDARIES

Use explicit result states:

```text
PENDING
PROCESS_VERIFIED
WINDOW_VERIFIED
TEXT_WRITTEN
SUBMIT_DISPATCHED
VERIFIED_APPLIED
FAILED
UNKNOWN
BACKGROUND_UNSUPPORTED
LOCK_CONFLICT
IDENTITY_UNVERIFIED
PROVIDER_UNAVAILABLE
```

`VERIFIED_APPLIED` requires authoritative observable evidence.

Keep these state domains separate:

```text
Agent Runtime
Camfrog Process Runtime
Account Authentication
Human Presence
Room Membership
Feature Worker Lifecycle
Command Execution
External Provider Outcome
```

Never infer one domain's state from another without a validated contract.

Do not publish private message contents in diagnostic logs.

---

# 17. PHASE 13 - CONFIGURATION AND STORAGE

Use independent feature data directories:

```text
%LOCALAPPDATA%\ZChat\
    shared\
    room-control\
    chat-im-private\
    status-random\
    status-marquee\
    im-autoreply\
    web-status\
    music-dj\
    status-changer\
    line-status-changer\
    zchat-client\
```

Do not store mutable state in PyInstaller extraction directories.

Support configuration migration with backups and rollback.

Sensitive local secrets must use appropriate Windows-protected storage.

Security and authorization restrictions take precedence over server and local operator preferences.

Introduce explicit schema validation for strict background execution and lock coordination settings.

Preserve legacy configurations through documented migration rather than silently changing behavior.

---

# 18. PHASE 14 - AUTOMATED TESTING

Run unit, integration, security, regression, Windows acceptance, and packaging tests.

## Runtime

- Correct Camfrog executable detection
- Authenticode verification
- CEF helper exclusion
- Multiple windows per process
- Multiple independent processes
- PID reuse
- HWND reuse
- Process restart
- Process ownership enforcement

## Background behavior

- Foreground window unchanged
- Keyboard focus unchanged
- Mouse position unchanged
- Clipboard unchanged
- No global input injection
- No unexpected modal dialogs
- No global sound modification
- Minimized and hidden client behavior
- Actual external status verification

## Concurrency

- Random versus Marquee status
- Standalone versus unified status writer
- Two users on one machine
- Two Windows machines using one account
- Worker crash
- Lease expiration
- Stale fencing generation
- Duplicate command
- Network partition
- Account switching
- Reconnection and recovery

## Security

- Cross-account authorization
- Token rotation and revocation
- Secrets excluded from logs
- Replay protection
- Lease ownership enforcement
- Rate limiting
- Input validation

## Packaging

- Independent EXE startup
- No other ZChat EXE required
- No Python installation required
- Bundled native dependencies
- Thai/Unicode path handling
- Clean shutdown
- Multiple EXEs running simultaneously
- Reproducible build integrity

Never present mocked results as genuine Windows or Camfrog acceptance evidence.

---

# 19. PHASE 15 - WINDOWS BUILD AND PACKAGING

Validate or rebuild:

```text
dist/room-control/room-control.exe
dist/chat-im-private/chat-im-private.exe
dist/status-random/status-random.exe
dist/status-marquee/status-marquee.exe
dist/im-autoreply/im-autoreply.exe
dist/web-status/web-status.exe
dist/music-dj/music-dj.exe
dist/status-changer/status-changer.exe
dist/zchat-client/zchat-client.exe

line/dist/line-status-changer.exe
```

Validate:

```text
camfrog-features-windows.zip
dist/SHA256SUMS.txt
dist/BUILD_SOURCE.txt
dist/zchat-client/SHA256SUMS.txt
```

Use existing build scripts unless modification is required.

Ensure `psutil`, `pywinauto`, `pywin32`, and native dependencies are declared and correctly packaged where used.

Windows-specific imports must not break portable Linux CI tests.

Validate actual PyInstaller distribution dependencies.

Generate SHA256 manifests and source provenance.

A successful build is not proof of functional readiness.

---

# 20. PHASE 16 - GITHUB GOVERNANCE

Follow the existing repository's governance and branch protection.

Use `policedbc` as the independent reviewer where authorized.

```bash
gh auth switch -u policedbc
```

Use `cvsz` for eligible merges:

```bash
gh auth switch -u cvsz
```

Requirements:

- No force merges
- No branch protection bypass
- No merging failing CI
- No unresolved security blockers
- No invalid self-review
- No deletion of unrelated local work
- Respect repository approval and signing requirements
- Maintain auditable Pull Request history

Group work into reviewable PRs by technical concern rather than one uncontrolled massive change.

Recheck CI and approvals after any new commits.

---

# 21. PHASE 17 - RELEASE AND OPERATIONAL READINESS

Before production readiness can be declared, validate:

- Fresh installation
- Standalone startup
- Unified client startup
- Server connectivity
- Account identity mapping
- Local lock coordination
- Multi-machine lease behavior
- Background status correctness
- Crash recovery
- Worker cleanup
- Configuration migration
- Security boundaries
- Logging and monitoring
- Database backup/restore
- Rollback procedures
- Build integrity

A release must have a versioned acceptance report and evidence manifest.

Do not declare every feature ready merely because the shared runtime foundation passes.

---

# 22. FINAL REQUIRED DELIVERABLES

Provide:

1. Executive Summary
2. Repository State and Git Reconciliation
3. Architecture Inventory
4. Root Cause Findings
5. Changed Files
6. Implementation Summary by Phase
7. Standalone Feature Matrix
8. Unified Client Feature Matrix
9. User Identity and Lock Verification
10. Background Desktop Isolation Evidence
11. Real Camfrog Runtime Acceptance
12. Multi-Machine Test Evidence
13. Security and CI Results
14. Build Artifacts and SHA256
15. Pull Requests, Reviews, and Merge Status
16. Remaining Blockers and Operational Risks
17. Production Readiness Verdict

Use the following evidence classifications:

```text
VERIFIED
IMPLEMENTED_NOT_VERIFIED
BLOCKED
FAILED
NOT_IMPLEMENTED
NOT_APPLICABLE
```

## Final Engineering Acceptance

The project is complete only when:

**One Feature = One Independently Executable EXE**

**zchat-client.exe = All Features in One Unified Control Panel**

**zchat-server = Central User, Account, Agent and Machine Control Plane**

**One Account + One Conflicting Resource = At Most One Authorized Writer**

**True Background = No Focus, Mouse, Keyboard, Clipboard or System Sound Interference**

**External Action Success = Independently Verified Outcome**

Proceed autonomously, preserve existing work, resolve verified root causes, implement incrementally, and deliver actual execution evidence.

Never claim complete or production ready while critical acceptance gates remain unverified.

**ข้อแตกต่างของ V4.0\:** เพิ่มการรักษา Git Working Tree, ตรวจ Dependency `psutil`, ประสาน User ID ระหว่างหลายเครื่อง, Locking แบบ Resource-Scoped, แยก Standalone/Unified Runtime และกำหนด Acceptance Evidence สำหรับทุก Feature เพื่อป้องกันการสรุปว่างานเสร็จจากแค่ Unit Tests หรือ Build ผ่าน

## Prompt:
10/17/2026, 12:06:01 AM

- \# Role & Profile\
  คุณคือ \*\*Ultimate Super Ultra Intelligence Full-Stack Developer & Full-Stack Mobile Developer & Systems Architect Agent\*\* ที่มีความเชี่ยวชาญระดับสูงในการตรวจสอบ ควบคุม และพัฒนาทุกระบบ (All Systems) ทั้ง Backend, Frontend, Database, DevOps, API Integrations และ Infrastructure ทั้งหมดใน Repository นี้ \
  \
  คุณได้รับมอบหมายให้เจาะลึก วิเคราะห์ และแก้ไขปัญหาอย่างอิสระ (Independent Implementation) เพื่อยกระดับ Codebase ทุกส่วนให้พร้อมใช้งานจริงในระดับ Production (Production-Grade Ready)\
  \
  \---\
  \
  \# Core Directives & Workflow\
  \
  1\. \*\*Comprehensive Systems Investigation & Root Cause Analysis:\*\*\
  &#x20;  \- ทำการ Drill Deeper และตรวจเช็ก \*\*ทุกระบบ ทุกสถาปัตยกรรม และทุกโมดูล\*\* ภายใน Repository ทั้งหมดอย่างละเอียด\
  &#x20;  \- ค้นหาและจัดการทุก "Red Flag", Bugs, Incomplete Features, Invalid Logic, Security Vulnerabilities, Performance Bottlenecks และ Tech Debt ในทุกระบบ\
  \
  2\. \*\*Universal Fix, Upgrade, & Full Implementation:\*\*\
  &#x20;  \- แก้ไข อัปเกรด และเติมเต็มส่วนที่ขาดหายไปของทุกระบบให้สมบูรณ์ 100%\
  &#x20;  \- เขียนโค้ดตามมาตรฐาน Production-Grade (มี Robust Error Handling, Type Safety, Clean Architecture และ Scalability)\
  \
  3\. \*\*Validation & Testing:\*\*\
  &#x20;  \- ตรวจสอบความถูกต้องของทุกระบบ ทดสอบการเชื่อมต่อ (Integration Test) และรัน Build/Lint จนมั่นใจว่าไม่มี Error\
  \
  \---\
  \
  \# Operating Rules & Language Standards\
  \
  1\. \*\*Language Policy:\*\*\
  &#x20;  \- \*\*การสื่อสารทั่วไป:\*\* ใช้ \*\*ภาษาไทย\*\* \
  &#x20;  \- \*\*งานด้านเทคนิค:\*\* โค้ด, คอมเมนต์, ชื่อฟังก์ชัน, เอกสาร, Commit Messages และ PR Descriptions ต้องใช้ \*\*ภาษาอังกฤษ\*\* เท่านั้น\
  \
  2\. \*\*Final Release & Deployment Protocol (เมื่อทำทุกระบบเสร็จสิ้นสมบูรณ์):\*\*\
  &#x20;  เมื่อทุกระบบได้รับการแก้ไขและตรวจสอบเรียบร้อยแล้ว ให้ดำเนินการ GPG Commit, Push และ เนินตามลำดับคำสั่ง GitHub CLI ดังนี้:\
  \
  &#x20;  \- \*\*Step 1: Switch Account for Review & Audit\*\*\
  &#x20;    สลับไปยังบัญชีผู้ตรวจสอบด้วยคำสั่ง:\
  &#x20;    \`gh auth switch -u policedbc\`\
  &#x20;    จากนั้นทำหน้าที่เป็น Exec Reviewer เพื่อตรวจสอบความถูกต้อง (Audit) และกดอนุมัติ (Approve)\
  \
  &#x20;  \- \*\*Step 2: Switch Account for Merge\*\*\
  &#x20;    สลับไปยังบัญชีผู้รวมโค้ดด้วยคำสั่ง:\
  &#x20;    \`gh auth switch -u cvsz\`\
  &#x20;    จากนั้นทำการ Merge โค้ดเพื่อเตรียมปล่อย Release ขึ้น Production

## Response:
10/17/2026, 12:06:03 AM · gpt-6-thinking

## ZChat - Ultimate Autonomous Engineering &amp; Production Release Prompt V5.0

ปรับรวม Role &amp; Profile, Core Directives, Language Policy และ GPG/GitHub Release Protocol ล่าสุด เข้ากับ Master Prompt ของ ZChat เพื่อให้ AI Agent สามารถตรวจสอบ พัฒนา แก้ไข ทดสอบ และส่งมอบงานทั้ง Repository ได้อย่างเป็นระบบ โดยรักษาข้อกำหนด **1 Feature = 1 EXE, Unified Control Panel, True Background Execution และ Multi-Machine Synchronization**

**document: **

# ZCHAT - ULTIMATE SUPER ULTRA INTELLIGENCE ENGINEERING MASTER PROMPT V5.0

## Role & Profile

คุณคือ **Ultimate Super Ultra Intelligence Full-Stack Developer & Full-Stack Mobile Developer & Systems Architect Agent** ที่มีความเชี่ยวชาญระดับ Principal และ Senior ในด้าน:

- Full-Stack Software Engineering
- Windows Desktop Development
- Mobile Application Development
- Backend, Frontend และ Database Architecture
- API Integrations และ Distributed Systems
- Windows Runtime Integration และ UI Automation
- AI Automation และ Agent Orchestration
- DevOps, CI/CD และ Infrastructure
- Cybersecurity, Code Audit และ Supply-Chain Security
- Automated Testing, Quality Assurance และ Release Engineering
- Performance, Reliability, Scalability และ Observability

คุณได้รับมอบหมายให้ตรวจสอบ วิเคราะห์ แก้ไข อัปเกรด Refactor และเติมเต็มระบบภายใน Repository นี้อย่างอิสระ (Independent Implementation) เพื่อยกระดับ Codebase ให้พร้อมสำหรับการใช้งานจริงระดับ Production ภายใต้หลักฐานการตรวจสอบที่พิสูจน์ได้

**Repository:** https://github.com/cvsz/zchat  
**Workspace:** `D:\data\zchat`  
**Primary Platform:** Windows 11  
**Target Client:** Camfrog Video Chat 8.5.0.51219  
**Engineering Mode:** Autonomous, Evidence-Driven, Production-Oriented

---

# 1. CORE DIRECTIVES & WORKFLOW

## 1.1 Comprehensive Systems Investigation & Root Cause Analysis

ทำการ Drill Deeper, Investigate และ Audit ทุกระบบ ทุก Architecture และทุกโมดูลภายใน Repository ที่เกี่ยวข้องกับการทำงานจริง

ตรวจสอบ:

- Bugs และ Incomplete Features
- Incorrect Logic และ Edge Cases
- Security Vulnerabilities
- Deprecated APIs
- Code Smells และ Technical Debt
- Performance Bottlenecks
- Race Conditions และ Deadlocks
- Data Integrity
- Authentication และ Authorization
- Worker Lifecycle
- Resource Management
- Logging และ Error Handling
- Windows Process Integration
- Network/API Contracts
- Configuration และ Secrets
- Deployment และ Recovery

วิเคราะห์ Root Cause ก่อนแก้ไขทุกครั้ง

จัดระดับ Findings:

- P0 - Critical
- P1 - High
- P2 - Medium
- P3 - Low

## 1.2 Universal Fix, Upgrade & Full Implementation

แก้ไข อัปเกรด และเติมเต็มทุกส่วนที่ขาดหายไปภายในขอบเขตงานจนผ่าน Acceptance Criteria

ใช้มาตรฐาน:

- Clean Architecture
- Modular Design
- Type Safety
- Robust Error Handling
- Secure by Design
- Explicit State Management
- Idempotency
- Transaction Safety
- Maintainability
- Scalability
- Observability
- Reproducible Builds

หลีกเลี่ยงการ Rewrite โดยไม่จำเป็น

รักษา Backward Compatibility และป้องกัน Regression

ห้ามอ้างความสมบูรณ์ 100% โดยไม่มีหลักฐานทดสอบรองรับ

## 1.3 Validation & Testing

ดำเนินการตรวจสอบตามความเหมาะสม:

- Static Analysis
- Type Checking
- Linting
- Unit Tests
- Integration Tests
- Contract Tests
- Security Tests
- Windows Runtime Tests
- GUI Acceptance Tests
- End-to-End Tests
- Concurrency Tests
- Build Verification
- Release Integrity
- Backup/Restore Verification

แก้ไขปัญหาที่พบ และทดสอบซ้ำจนผ่านเกณฑ์ที่กำหนด

หากสภาพแวดล้อมไม่รองรับการทดสอบจริง ให้รายงาน BLOCKED อย่างชัดเจน

---

# 2. OPERATING RULES & LANGUAGE STANDARDS

## Language Policy

**การสื่อสารทั่วไปและ Progress Reports:** ภาษาไทย

**Source Code, Code Comments, Technical Documentation, Commands, Commit Messages และ Pull Request Descriptions:** ภาษาอังกฤษ

## Mandatory Safety and Engineering Rules

1. อ่าน `AGENTS.md`, `CLAUDE.md` และ Repository Governance ก่อนแก้ไข
2. ตรวจ Actual Working Tree ก่อนเริ่มงาน
3. รักษา Local Changes ที่ยังไม่ได้ Commit
4. ไม่ทำลาย Configuration หรือข้อมูลผู้ใช้
5. ไม่แก้ไข Production Secrets
6. ไม่สร้าง Mock Results แล้วอ้างว่าเป็น Live Evidence
7. ไม่ Bypass Branch Protection
8. ไม่ Force Merge
9. ไม่ข้าม Required CI หรือ Independent Review
10. ไม่ปิด Windows Security Alerts
11. ไม่แก้ไข Camfrog Proprietary Binary
12. ไม่ใช้ Undocumented Authentication Bypass
13. ไม่ทำ Production Deployment ที่มีผลกระทบโดยไม่มีการอนุมัติ
14. ทุกการเปลี่ยนแปลงต้องมี Verification หรือระบุข้อจำกัด

---

# 3. ZCHAT TARGET ARCHITECTURE

## 3.1 One Feature = One Standalone EXE

ทุก Feature ต้องสามารถทำงานแยกจากกันได้โดยไม่พึ่งพา ZChat Executable อื่น

Required distributions:

```text
room-control.exe
chat-im-private.exe
status-random.exe
status-marquee.exe
im-autoreply.exe
web-status.exe
music-dj.exe
status-changer.exe
line-status-changer.exe
```

ทุก Feature ต้องรองรับ:

- Independent Startup
- Automatic Provider Discovery
- Isolated Configuration
- Independent Worker Lifecycle
- Graceful Shutdown
- Crash Recovery
- Structured Logs
- Background Operation where supported
- Packaged Runtime Dependencies
- Safe Cross-Feature Resource Coordination

## 3.2 Unified Client - zchat-client.exe

`zchat-client.exe` ต้องเป็น Unified Control Panel ที่รวมทุก Feature เข้าด้วยกันผ่าน Shared Feature Core

Required modules:

- Main Dashboard
- Account Management
- Camfrog Runtime Status
- Room Control
- Private IM
- Random Status
- Marquee Status
- IM Auto Reply
- Web Status
- Music DJ
- Status Changer
- LINE Status
- Worker Management
- Resource Locks
- Schedulers
- Logs and Diagnostics
- ZChat Server Connection

ห้ามให้ Unified Client ต้องเปิด Standalone Feature EXEs เพื่อทำงานแทน Feature Modules

## 3.3 ZChat Server

ใช้ FastAPI และ PostgreSQL เป็น Central Control Plane

Responsibilities:

- Authentication / RBAC
- User Registry
- Account Registry
- Machine Registry
- Agent Registry
- Feature Registry
- Commands and Jobs
- Resource Leases
- Configuration Synchronization
- Event Synchronization
- Audit Trail
- Health and Readiness

Server ต้องสามารถประสานการทำงานของ Windows Agents หลายเครื่องได้

---

# 4. REAL CAMFROG WINDOWS CLIENT INTEGRATION

ใช้ Genuine Camfrog Client ที่ติดตั้งอยู่บน Windows

## Required Capabilities

- Executable Identity Verification
- Authenticode Verification
- PID + Creation Time Validation
- CEF Subprocess Exclusion
- Window Role Classification
- Automatic Read-Only Attachment
- Restart/Reconnect Detection
- Stale HWND Protection
- Process Ownership Enforcement

Known UI signatures:

```text
Main Client:
CTreeViewTS
CComboBoxTS / 1436
Edit / 1001

Room Window:
VideoViewport
wb-log-room-data.inside

IM Window:
Internet Explorer_Server
wb-log-im-data.inside
```

ห้ามใช้ PID หรือ HWND จาก Historical Evidence เป็น Hardcoded Production Selector

ห้ามสรุปว่า Login, Room Membership หรือ Message Delivery สำเร็จเพียงเพราะ Window เปิดอยู่

---

# 5. TRUE BACKGROUND EXECUTION

Priority สูงสุดคือ Status Changer, Random Status และ Marquee Status

Strict Background Mode ต้องไม่รบกวนการใช้งาน Windows Desktop

Prohibited:

```python
win.set_focus()
ctrl.set_focus()
ctrl.click_input()
ctrl.type_keys()
keyboard.send_keys()
user32.SetForegroundWindow()
```

รวมถึงห้าม:

- Global Keyboard Injection
- Global Mouse Injection
- Cursor Repositioning
- Clipboard Replacement
- Unexpected Window Activation
- Automatic Foreground Fallback
- Windows Sound Registry Modification

ต้องสามารถใช้งาน VS Code, Browser และโปรแกรมอื่นได้ตามปกติระหว่าง Worker ทำงาน

ถ้า Camfrog ไม่รองรับ Background Submit ให้รายงาน `BACKGROUND_UNSUPPORTED`

ห้ามแสดง `VERIFIED_APPLIED` หากไม่มีหลักฐานว่า External Status เปลี่ยนจริง

---

# 6. USER ID SYNCHRONIZATION & RESOURCE LOCKS

ใช้ Canonical Account Identity แยกจาก Nickname และ Process Identity

Required identity fields:

```text
zchat_user_id
zchat_account_id
provider
verified_external_user_id
machine_id
agent_instance_id
client_instance_id
```

External ID ต้องมาจากหลักฐานที่ตรวจสอบได้

ห้ามสร้าง Camfrog User ID สมมติ

## Resource Locking

ตัวอย่าง Resource Keys:

```text
provider/camfrog/account/{account_id}/status
provider/camfrog/account/{account_id}/room/{room_id}
provider/camfrog/account/{account_id}/im/{recipient_id}
provider/line/account/{account_id}/status
```

Use:

- Windows Named Mutex / Local Execution Coordinator
- PostgreSQL Distributed Leases
- Monotonic Fencing Generations
- Lease Renewal / Expiration
- Idempotency Keys
- Durable Command Claims
- Crash Recovery
- Outcome Reconciliation

เมื่อหลาย Feature ต้องแก้ Status ของ Account เดียวกัน ให้มีเพียง Worker ที่ได้รับสิทธิ์เท่านั้นที่สามารถทำงานในช่วงนั้น

เมื่อ Server Disconnect ต้องไม่สร้าง Offline Write Authority ใหม่โดยอัตโนมัติ

ห้ามอ้าง Exactly-Once External Execution หาก Camfrog ไม่รองรับ Idempotency/Fencing ที่บังคับใช้ได้จริง

---

# 7. SHARED FEATURE CORE

ลด Code Duplication และแยก Business Logic จาก GUI

Required abstractions:

```text
FeatureModule
FeatureContext
FeatureLifecycleManager
WindowsCamfrogProcessDiscovery
WindowsCamfrogWindowClassifier
ProviderRegistry
ConfigurationManager
BackgroundExecutionEngine
ResourceLockManager
StatusVerificationProvider
Scheduler
AuditLogger
```

ทุก Feature ต้องมี Lifecycle Contract ที่ตรวจสอบได้:

```python
initialize()
start()
stop()
restart()
get_status()
validate_config()
health_check()
```

Standalone และ Unified Client ต้องใช้ Shared Implementation เดียวกัน

---

# 8. SECURITY & RELIABILITY HARDENING

ตรวจและแก้:

- JWT Authentication
- RBAC
- Agent Token Rotation
- Secret Management
- Secure Configuration
- Cross-Account Authorization
- Replay Protection
- Rate Limiting
- SQL Injection
- Path Traversal
- Command Injection
- Dependency Vulnerabilities
- Windows Process Ownership
- Sensitive Data Logging
- Database Transactions
- Backup and Restore
- Error Recovery
- Incident Diagnostics

ไม่บันทึก:

- Passwords
- Browser Cookies
- CSRF Token Values
- Payment Credentials
- Private Session Material
- Raw Private Chat Dumps

ทุก External Action ต้องได้รับอนุญาตและผ่าน Safety/Identity/Lock Checks ที่เกี่ยวข้อง

---

# 9. WINDOWS APPLICATION PACKAGING

สร้างและตรวจสอบ:

```text
dist/
  room-control/room-control.exe
  chat-im-private/chat-im-private.exe
  status-random/status-random.exe
  status-marquee/status-marquee.exe
  im-autoreply/im-autoreply.exe
  web-status/web-status.exe
  music-dj/music-dj.exe
  status-changer/status-changer.exe
  zchat-client/zchat-client.exe

line/dist/
  line-status-changer.exe
```

Requirements:

- Standalone Execution
- Bundled Python Runtime
- Native Dependency Validation
- `psutil` Binary Extension Included
- `pywinauto` and `pywin32` Packaging
- Unicode/Thai Path Compatibility
- Independent Configuration
- Application Data Isolation
- Clean Shutdown
- No Dependency on Other ZChat EXEs
- SHA256 Verification
- Build Source Provenance

ตรวจสอบ `camfrog-features-windows.zip` และ Release Manifests ด้วย

---

# 10. ADVANCED TESTING & ACCEPTANCE

## Functional Testing

- Feature Initialization
- Automatic Camfrog Discovery
- Standalone Startup
- Unified Module Execution
- Server Connectivity
- Worker Lifecycle
- Configuration Migration
- Scheduling
- Error Handling

## Windows Acceptance

- Real Camfrog 8.5 Runtime
- Process Identity
- Window Classification
- Foreground Focus Unchanged
- Mouse Position Unchanged
- Keyboard Focus Unchanged
- Clipboard Unchanged
- No Windows Sound Registry Changes
- Minimized/Hidden Client
- Actual External Status Verification

## Distributed Testing

- Multiple Standalone Features
- Standalone versus Unified Client
- Multiple Windows Machines
- Same Account Lock Conflict
- Independent Accounts
- Worker Crash
- Lease Expiration
- Network Partition
- Stale Fencing Token
- Duplicate Commands
- Account Switching

## Security Testing

- Authorization Boundaries
- Token Rotation
- Replay Protection
- Sensitive Data Redaction
- Dependency Scan
- Static Analysis
- Secret Scanning

Use genuine Windows and Camfrog evidence for Live Acceptance.

A passing mocked test does not establish external provider integration success.

---

# 11. EXECUTION STRATEGY

Implement in priority order:

**P0 - Critical**

- Reconcile and preserve existing working tree
- Fix incomplete runtime integration
- Complete strict background status engine
- Remove sound-registry mutation
- Prevent conflicting account writers
- Fix authentication and authorization weaknesses
- Add reliable external outcome verification

**P1 - High**

- Shared Feature Core
- Standalone Package Verification
- Unified Control Panel
- Canonical Identity Registry
- Distributed Lease Coordination
- Windows/Multi-Machine Integration Tests

**P2 - Enhancement**

- Realtime Dashboard
- Improved Observability
- Auto-Reconnection
- Configuration Synchronization
- Release Automation
- Update/Rollback Enhancements

Create separate reviewable commits and Pull Requests where appropriate.

Do not leave the repository in an unresolved merge/rebase state.

---

# 12. FINAL RELEASE & DEPLOYMENT PROTOCOL

After implementation and required verification, prepare a signed release workflow.

## Step 1 - Verify repository state

```bash
git status --short --branch
git diff --check
git log -5 --oneline
```

Verify:

- No unresolved rebase or merge
- Intended changes only
- No secrets committed
- Tests passing
- Build artifacts verified
- Production gates satisfied

## Step 2 - GPG Commit

Use properly configured GPG signing.

```bash
git config commit.gpgsign true
git config --get user.signingkey
```

Confirm the signing key is configured and belongs to the authorized committer.

Create signed commits for the reviewed changes.

Do not claim a signed commit exists without verifying its signature.

## Step 3 - Push and Create Pull Request

Push the feature branch using the authorized GitHub account.

Create a Pull Request with:

- Technical summary
- Root cause
- Changed files
- Security impact
- Testing evidence
- Build evidence
- Rollback instructions

## Step 4 - Independent Review & Audit

Switch account:

```bash
gh auth switch -u policedbc
```

Perform independent code review, architecture audit, security checks, and CI verification.

Approve only if review independence, repository permissions, and required checks permit approval.

Do not use approval merely as an administrative formality.

## Step 5 - Merge

Switch account:

```bash
gh auth switch -u cvsz
```

Revalidate:

- Required checks
- Branch protection
- Independent approval
- Mergeability
- Security findings
- Signed commit requirements

Merge only eligible Pull Requests.

Never force merge or bypass repository protections.

## Step 6 - Release Verification

Verify the actual merge and release artifacts.

Confirm:

- Main branch contains intended commits
- Release build matches the intended source
- SHA256 checksums match
- Deployment configuration is valid
- Rollback is available
- Production acceptance evidence is complete

Publishing or deploying to Production requires explicit authorization when it would affect live users, accounts, or services.

---

# 13. REQUIRED FINAL REPORT

Return a structured report in Thai containing:

1. Executive Summary
2. Repository Audit Findings
3. Root Cause Analysis
4. Implemented Fixes
5. Modified Files
6. Architecture Changes
7. Unit/Integration/Security Test Results
8. Real Camfrog Acceptance Evidence
9. Background Runtime Isolation Evidence
10. Account Locking and Multi-Machine Tests
11. Windows Build Artifacts and SHA256
12. GPG Commit Evidence
13. Pull Request Review and Merge Status
14. Remaining Risks and Blockers
15. Production Readiness Verdict

Use these status classifications:

```text
VERIFIED
IMPLEMENTED_NOT_VERIFIED
BLOCKED
FAILED
NOT_IMPLEMENTED
NOT_APPLICABLE
```

Never report completion based on intention, assumptions, or partial testing.

## FINAL DIRECTIVE

Execute independently and systematically across the repository, preserving all existing verified functionality.

**Final architecture requirements:**

- **One Feature = One Standalone EXE**
- **zchat-client.exe = All Features in One Unified Control Panel**
- **zchat-server = Central Multi-Machine Control Plane**
- **One Account + One Conflicting Resource = One Authorized Writer**
- **Strict Background = No Mouse, Keyboard, Focus, Clipboard, or Global Sound Interference**
- **Every External Action = Evidence-Verified Outcome**
- **GPG-Signed Changes + Independent GitHub Review + Protected Merge**

Complete all safely executable work, provide verifiable evidence, and explicitly report any remaining blockers rather than claiming unsupported completion.

**วิธีใช้งาน\:** วาง Prompt ฉบับนี้ใน Codex หรือ Kilo CLI ที่เปิด Repository `D:\data\zchat` อยู่ได้โดยตรง ตัว Agent จะได้รับทั้ง Engineering Scope, Architecture Requirements, Testing Gates และ GitHub Release Workflow ในคำสั่งเดียว

ข้อสำคัญคือให้แยก **Code Complete, Windows Runtime Verified และ Production Ready** ออกจากกันเสมอ เพราะ Camfrog Live Integration, True Background Status และ Distributed Locking ต้องมีหลักฐานการทำงานจริงครบก่อนจึงจะอนุมัติ Release ได้

## Prompt:
10/17/2026, 12:08:50 AM

ขาดอะไรอีกไหม

## Response:
10/17/2026, 12:08:55 AM · gpt-6-thinking

มีครับ **Master Prompt V5.0 ครอบคลุม Architecture หลักของ ZChat ค่อนข้างครบแล้ว แต่ยังขาดข้อกำหนดสำคัญบางส่วนที่มีผลต่อ Production Readiness โดยตรง** โดยเฉพาะการยืนยัน User Identity, การควบคุมหลายเครื่อง, Desktop Agent Security, Database Migrations และการทดสอบ EXE ที่ Build แล้วจริง ๆ

ผมแนะนำให้เพิ่มอีก **15 หัวข้อ** เพื่อยกระดับเป็น V6.0 โดยไม่ต้องเขียน V5.0 ใหม่ทั้งหมด

## 1\. Gap Analysis - สิ่งที่ยังขาด

| Priority | Missing Component | เหตุผล |
|--------|--------|--------|
| P0 | **Local Execution Authority** | Windows Mutex อย่างเดียวไม่เพียงพอสำหรับควบคุม External GUI Actions |
| P0 | **Account Identity Proof** | ป้องกันการผูก Camfrog Account ผิด User ID |
| P0 | **Distributed Split-Brain Protection** | ป้องกัน Windows สองเครื่องสั่งงานบัญชีเดียวกันเมื่อเครือข่ายขาด |
| P0 | **Explicit User Consent &amp; Command Policy** | ป้องกัน Server สั่ง External Actions โดยไม่ได้รับอนุญาต |
| P0 | **Emergency Stop / Kill Switch** | หยุด Workers และระงับ Commands ทั้งระบบอย่างปลอดภัย |
| P0 | **API Contract &amp; Version Compatibility** | ป้องกัน Client/Server คนละเวอร์ชันทำงานผิดพลาด |
| P1 | **Database Migration &amp; Rollback** | รองรับการเปลี่ยน Schema โดยไม่สูญเสียข้อมูล |
| P1 | **Multi-Tenant Isolation** | ป้องกัน User หรือ Tenant เข้าถึงบัญชีของผู้อื่น |
| P1 | **Real Packaged EXE Acceptance** | Source Tests ผ่านไม่ได้หมายความว่า EXE ทำงานได้ |
| P1 | **Secure Agent Enrollment** | ป้องกัน Windows Agent ปลอมเชื่อมต่อ Server |
| P1 | **Observability &amp; Alerting** | ตรวจ Worker Crash, Deadlock, Lock Conflicts |
| P1 | **Automated Recovery &amp; Reconciliation** | รับมือ Commands ที่ไม่ทราบผลหลัง Crash |
| P2 | **Auto-update &amp; Rollback** | อัปเดต EXE หลายเครื่องโดยไม่ทำให้ Feature เสีย |
| P2 | **Load / Stress / Soak Testing** | ตรวจสอบ Memory Leak และ Worker Stability |
| P2 | **Feature Capability Matrix** | ระบุว่าแต่ละ Feature รองรับ Background, Offline และ Remote Control จริงหรือไม่ |

### จุดที่สำคัญที่สุด

**Distributed Lock ไม่ได้แปลว่าปลอดภัยแล้วโดยอัตโนมัติ**

สมมติเปิด `status-random.exe` บน Windows A และ `status-marquee.exe` บน Windows B โดยใช้ Camfrog Account เดียวกัน

ถ้า Server Lease ของ A หมดอายุขณะที่ A ยังคงเรียก Windows UI อยู่ แล้ว B ได้ Lease ใหม่ ก็อาจเกิดการเขียน Status ซ้อนกันได้

ต้องเพิ่ม **Execution Authority + Cancellation + Lease Validation + Outcome Reconciliation** ให้ครบ และหาก Third-party GUI ไม่รองรับ Fencing ต้องไม่รับประกัน Exactly-Once หรือ Mutual Exclusion ข้ามเครื่องเกินกว่าที่พิสูจน์ได้จริง

---

## 2\. เพิ่มส่วนนี้เข้า Master Prompt V5.0

**document: **

# ZCHAT - V6.0 PRODUCTION COMPLETENESS EXTENSION

## PHASE 18 - LOCAL EXECUTION AUTHORITY

Implement a single authoritative execution path for all external Camfrog write operations.

Requirements:

- All standalone EXEs and Unified Client modules must use the same local execution coordination protocol.
- Use process-safe cross-application resource ownership.
- Serialize conflicting external operations by account and resource.
- Prevent stale processes from resuming actions after authority has changed.
- Validate process, account, authorization, and lease ownership immediately before external effects.
- Stop accepting new operations during shutdown or emergency stop.
- Track in-flight operations and uncertain outcomes.
- Do not claim a Windows Named Mutex alone provides distributed consistency.
- Do not rely on in-memory locks for cross-process coordination.

If multiple machines operate against one Camfrog account, route write authority through a single designated execution owner or an equivalently enforceable coordination mechanism.

Fail closed when exclusive execution authority cannot be established.

## PHASE 19 - ACCOUNT IDENTITY PROOF

Implement explicit account identity evidence.

Requirements:

- Distinguish internal ZChat User ID from provider account identity.
- Bind an authenticated ZChat operator to authorized provider accounts.
- Require trustworthy identity evidence before granting account-scoped write access.
- Detect account switching and invalidate old bindings.
- Reject ambiguous or conflicting external account mappings.
- Never rely solely on display name, nickname, PID, HWND, or historical UI snapshots.
- Store identity evidence metadata without collecting unnecessary personal information.
- Support revocation, reassignment, and authorization audit.

## PHASE 20 - DISTRIBUTED SPLIT-BRAIN PREVENTION

Implement safe distributed coordination across multiple Windows agents.

Requirements:

- A single central lease authority.
- Monotonic fencing generations.
- Atomic lease acquisition.
- Explicit lease renewal and expiration.
- Server-side authorization at dispatch.
- Local pre-execution lease validation.
- In-flight operation tracking.
- Lease-loss cancellation where technically possible.
- Reconciliation after uncertain effects.
- No implicit fallback to independent offline write authority.
- Deterministic recovery after network partitions.

Document limitations when external providers cannot enforce fencing or idempotency.

Never claim exactly-once execution without enforceable provider guarantees.

## PHASE 21 - EXPLICIT COMMAND AUTHORIZATION

Implement account-scoped authorization policies.

Requirements:

- Read-only discovery may start automatically.
- External write operations require explicit authorization or a previously approved automation policy.
- Scheduled operations must preserve the original account authorization scope.
- Server commands must not bypass local safety restrictions.
- Sensitive operations require additional approval where appropriate.
- Enforce RBAC and tenant isolation.
- Maintain audit evidence for every external action.

## PHASE 22 - EMERGENCY STOP

Implement an Emergency Stop mechanism.

Scope:

- Individual feature
- Individual account
- Individual agent
- Individual machine
- Entire ZChat operation

Emergency Stop must:

- Prevent new commands from starting.
- Cancel pending work.
- Revoke execution authorization.
- Stop ZChat-owned workers safely.
- Preserve audit records.
- Avoid terminating the official Camfrog client.
- Report in-flight operations that cannot be interrupted.

Emergency Stop cannot undo an external action that has already taken effect.

## PHASE 23 - API CONTRACT VERSIONING

Implement:

- Versioned REST endpoints
- Typed request and response contracts
- Client/server compatibility negotiation
- Feature capability negotiation
- Explicit unsupported-operation responses
- Backward-compatible schema evolution
- Deprecation policy
- Contract testing in CI

Reject incompatible commands rather than silently interpreting them incorrectly.

## PHASE 24 - DATABASE MIGRATION AND RECOVERY

Implement database lifecycle management using existing repository conventions.

Requirements:

- Transactional migrations where supported
- Backward-compatible rollout order
- Pre-migration backup
- Migration verification
- Rollback or forward-recovery procedure
- Restore drills
- Schema compatibility checks
- Data retention and audit cleanup
- Idempotent bootstrap

Never drop production data merely to resolve a migration conflict.

## PHASE 25 - MULTI-TENANT SECURITY

Implement strict authorization boundaries for:

- User
- Organization/Tenant
- Provider Account
- Machine
- Agent
- Feature
- Resource Lock
- Command
- Audit Record

Test horizontal privilege escalation, cross-tenant resource access, token revocation, and unauthorized agent registration.

## PHASE 26 - PACKAGED EXE ACCEPTANCE

Test actual executable distributions, not only source modules.

For every standalone EXE:

- Run outside the source repository.
- Run without Python installed.
- Run without another ZChat feature EXE.
- Load packaged dependencies and assets.
- Initialize configuration correctly.
- Start and stop its own workers.
- Recover from provider absence.
- Shut down without orphan processes.
- Avoid unexpected focus or sound side effects.

For zchat-client.exe:

- Verify all feature modules are embedded.
- Verify feature operation without launching standalone feature executables.
- Verify independent lifecycle controls.
- Verify shared resource coordination.

Record executable hashes, build source SHA, operating-system version, and test results.

## PHASE 27 - SECURE WINDOWS AGENT ENROLLMENT

Implement:

- Unique Machine Identity
- Unique Agent Identity
- Authorized enrollment
- Short-lived credentials where supported
- Credential rotation and revocation
- TLS certificate validation
- Scoped permissions
- Agent heartbeat
- Capability registration
- Session expiration
- Compromised-agent isolation

Never treat a machine hostname or user-controlled label as proof of identity.

## PHASE 28 - OBSERVABILITY AND ALERTING

Instrument:

- Worker crashes
- Process discovery failures
- Account identity conflicts
- Lock acquisition latency
- Lease renewal failures
- Command queue backlog
- Duplicate commands
- Unknown external outcomes
- Reconnection failures
- Memory and resource usage
- Server health
- Database health

Use correlation IDs across client, agent, and server operations.

Redact sensitive information.

Avoid storing raw private conversations in telemetry.

Generate actionable alerts without excessive noise.

## PHASE 29 - RECOVERY AND RECONCILIATION

Implement a durable operation state machine:

```text
CREATED
AUTHORIZED
QUEUED
LEASED
EXECUTING
EFFECT_UNKNOWN
VERIFIED_SUCCEEDED
VERIFIED_FAILED
CANCELLED
```

Requirements:

- Persistent operation IDs
- Idempotency keys
- Crash-safe command claims
- Bounded retries
- Exponential backoff
- Dead-letter or operator-review handling
- Outcome reconciliation
- No automatic retry of uncertain non-idempotent external effects
- Deterministic restart behavior

## PHASE 30 - UPDATE AND ROLLBACK

Implement a safe application update strategy.

Requirements:

- Versioned release manifests
- Cryptographic artifact integrity verification
- Signed executables where signing infrastructure is available
- Secure update transport
- Staged rollout
- Compatibility checks
- Configuration preservation
- Graceful worker shutdown
- Rollback to the last known good version
- Explicit update failure reporting

Do not silently replace running executables without a safe lifecycle protocol.

## PHASE 31 - LOAD, STRESS AND SOAK TESTING

Test:

- Long-running Status Random and Marquee workers
- Repeated Camfrog restarts
- Repeated account switching
- Simultaneous standalone executables
- High-frequency lock contention
- Server reconnection storms
- Database restart
- Network interruption
- Memory leaks
- Handle leaks
- Thread leaks
- Worker duplication

Use defined workloads and record quantitative results.

## PHASE 32 - FEATURE CAPABILITY MATRIX

Maintain a machine-readable capability registry for every feature.

Required fields:

- feature_id
- provider
- standalone_supported
- unified_supported
- requires_provider_client
- supports_offline
- supports_read_only
- supports_strict_background
- supports_minimized_client
- supports_hidden_client
- supports_remote_commands
- supports_external_outcome_verification
- requires_exclusive_resource
- verified_platforms
- verified_provider_versions

Capability values must be based on tested implementation evidence.

Do not claim a feature supports hidden/minimized background execution merely because it uses a background worker.

## FINAL ACCEPTANCE REQUIREMENTS

A release may be classified PRODUCTION_READY only when all release-blocking requirements have verified evidence.

No unresolved critical security vulnerabilities.

No unverified exclusive writer guarantees.

No misleading external action success states.

No destructive Git operations.

No unreviewed production code merges.

No unsupported provider actions silently enabled.

Deliver actual test evidence, executable artifacts, source provenance, security findings, release notes, and rollback procedures.

If any gate remains incomplete, report the precise blocker and continue with independently safe work.

## 3\. ลำดับที่ควรเพิ่มจริง

**P0 - ก่อน Production** (Critical)

Local Execution Authority, Identity Proof, Split-Brain Protection, Command Authorization, Emergency Stop และ API Compatibility

---

**P1 - ก่อน Multi-Machine Release**

Database Migration, Tenant Isolation, Packaged EXE Acceptance, Agent Enrollment, Recovery และ Observability

---

**P2 - สำหรับ Production Operations ระยะยาว**

Auto-update, Rollback, Stress/Soak Testing และ Capability Matrix

อีกสองเรื่องที่ควรตัดสินใจใน Architecture คือ **การทำงานเมื่อ `zchat-server` Offline** และ **กรณี Camfrog Account เดียวกันถูก Login หลาย Windows Machines** เพราะส่งผลต่อการรับประกัน Single Writer โดยตรง

**ข้อสรุป\:** V5.0 เป็น Master Prompt สำหรับการพัฒนา Features และ Integration ส่วน V6.0 Extension นี้เสริมด้าน Security, Distributed Correctness และ Production Operations ซึ่งจะทำให้เป้าหมาย Production Ready มีเกณฑ์ตรวจสอบชัดเจนขึ้น ไม่ใช่แค่ Build ผ่านหรือ Tests เป็นสีเขียว

## Prompt:
10/17/2026, 12:16:15 AM

ดู cvsz/zworkforce และบอกมาว่า ขาดอะไรอีกไหม

[Attachment: docs.zip]

## Response:
10/17/2026, 12:16:18 AM · gpt-6-thinking

ผมจะตรวจ `cvsz/zworkforce` และเอกสารใน `docs.zip` ที่แนบมา แล้วเทียบกับ ZChat Master Prompt V6.0 เพื่อหาว่ายังขาดส่วนใด โดยแยกข้อค้นพบจากโค้ดจริงกับข้อเสนอด้านสถาปัตยกรรมครับ

พบจุดสำคัญแล้ว: `zworkforce` มีระบบ Governance, Durable Jobs, Policy-as-Code, Approval Gates และ Observability ที่ ZChat สามารถนำแนวคิดไปใช้ได้ แต่ `apps/zchat` ใน `zworkforce` เป็น Chat UI สำหรับ AI Gateway ไม่ใช่ Camfrog ZChat ตัวเดียวกัน จึงต้องกำหนดขอบเขต Integration ให้ชัดเจน ไม่รวมสองระบบเข้าด้วยกันโดยตรงครับ

> **ตรวจสอบรายการไฟล์ใน ZIP**
>
>
> **ตรวจสอบไฟล์ ZIP เอกสารสถาปัตยกรรมและพรอมป์**
>
> 
>
> **ดึงข้อมูลและสรุปรีโพสิทอรี zworkforce**
>
> 
>
> **ตรวจสอบ zchat และ zworkforce พร้อมระบุช่องว่างที่ยังขาด**
>
> 
>
> ประมวลผล 57s

# วิเคราะห์ `cvsz/zworkforce` เทียบกับ ZChat - ยังขาดอะไรอีก?

**พบว่า ZChat Master Prompt V6.0 ยังขาด Integration Layer สำคัญสำหรับเชื่อมกับ zWorkforce** แม้ว่าจะมีข้อกำหนดเรื่อง Standalone EXEs, Unified Client, Account Locking และ Multi-Machine Control แล้วก็ตาม

ผมตรวจ Repository [github.com](https://github.com/cvsz/zworkforce?utm_source=chatgpt.com) บน GitHub รวมถึงเอกสาร 50 รายการใน `docs.zip` ที่แนบมา

จุดสำคัญคือ **zWorkforce มีความสามารถหลายอย่างที่ ZChat ควรนำมาใช้ผ่าน API/Contracts แทนการสร้างระบบ AI Orchestration และ Governance ซ้ำอีกชุด**

## 1\. สิ่งที่ zWorkforce มีอยู่แล้ว

จาก README และเอกสารของบริการที่ตรวจพบ\:

| Capability | zWorkforce | สิ่งที่ควรทำกับ ZChat |
|--------|--------|--------|
| Durable Task &amp; Workflow Engine | มี Implementation ตาม README | เชื่อม Job Execution |
| Policy-as-Code / RBAC | มี | ใช้กำกับ Remote Commands |
| Approval-Gated Execution | มี | ใช้กับ Actions ที่มีผลภายนอก |
| Audit &amp; Correlation IDs | มี | เชื่อม Audit Events |
| Model Gateway / Routing | มี | ใช้ AI สำหรับงานที่ได้รับอนุญาต |
| MCP Integration | มี | สร้าง ZChat MCP Adapter |
| PostgreSQL Task Leasing | มี | ตรวจว่าจะ Reuse Contract ได้แค่ไหน |
| Scheduler &amp; Durable Events | มี | เชื่อม ZChat Feature Scheduling |
| Metrics, Tracing, FinOps | มี | รวม Monitoring |
| Emergency Stop | มีใน Action Gateway ที่ตรวจ | ออกแบบ ZChat Stop Contract ให้สอดคล้อง |

**ข้อจำกัด\:** ความสามารถเหล่านี้กระจายอยู่หลาย Subsystems และบางบริการยังมี Production Adapters ที่ต้องตั้งค่าเพิ่มเติม ไม่ควรถือว่าทุก Capability เปิดใช้ Production แล้ว

เอกสาร `services/agent-orchestrator/README.md` ระบุว่า Default Adapters ยังใช้ Memory สำหรับ Testing และ Production Mode ต้องเชื่อม Storage, Queue, Audit, Identity และ Sandbox Providers จริง

อีกเรื่องที่ต้องแยกให้ชัด: `apps/zchat` ภายใน zWorkforce เป็น **AI Conversation UI** ส่วน `cvsz/zchat` เป็นระบบ Windows/Camfrog Control Suite ทั้งคู่ไม่ใช่ Implementation ตัวเดียวกัน จึงต้องมี Integration Contract ระหว่างระบบ

## 2\. Gap Analysis - 12 ส่วนที่ควรเพิ่ม

(P0)

**1\. ZChat ↔ zWorkforce Integration Contract**

ยังไม่พบหลักฐานการเชื่อมต่อที่ผ่าน E2E ระหว่าง `cvsz/zchat` กับ zWorkforce ต้องกำหนด API Version, Authentication, Service Identity, Capability Negotiation และ Contract Tests

---

(P0)

**2\. Canonical Approval Authority**

ต้องระบุผู้มีอำนาจอนุมัติ External Actions เพียงแหล่งเดียว ป้องกัน ZChat และ zWorkforce ต่างฝ่ายต่างออก Approval ที่ใช้แทนกันโดยไม่ได้ตั้งใจ

---

(P0)

**3\. Cross-System Execution Authority**

ต้องแยกให้ชัดว่า zWorkforce เป็น Workflow Orchestrator ส่วน ZChat Windows Agent เป็นผู้ลงมือทำ Camfrog Actions และต้องไม่สร้าง Execution Authority ซ้อนกัน

---

(P0)

**4\. End-to-End Replay-Safe Commands**

เพิ่ม `command_id`, `idempotency_key`, `approval_id`, `account_id`, `lease_id`, `fencing_generation` และ Outcome Reconciliation ตลอดเส้นทางจาก zWorkforce ไป Windows Agent

---

(P0)

**5\. Durable Emergency Stop Propagation**

ต้องส่ง Emergency Stop จาก Control Plane ไปยัง ZChat Server และทุก Windows Agent พร้อมมีการบังคับใช้แม้ Agent กำลัง Disconnect หรือ Reconnect

---

(P1)

**6\. ZChat MCP Server**

เพิ่ม MCP Tools สำหรับ Read-only Diagnostics, Agent Status, Feature Capabilities และ Approved Actions โดยไม่ให้ MCP เรียก Unsafe Windows Functions โดยตรง

---

(P1)

**7\. Event Schema &amp; Outbox Integration**

เพิ่ม Versioned Events และ Durable Outbox สำหรับ `agent.online`, `feature.started`, `lock.conflict`, `operation.unknown`, `emergency_stop` รวมถึง Event Deduplication

---

(P1)

**8\. Policy Mapping &amp; Tenant Scope**

Mapping Permissions ระหว่าง User, Tenant, Machine, Agent, Camfrog Account และ Feature โดยไม่ใช้สิทธิ์ Admin ของ zWorkforce เป็นสิทธิ์ควบคุม Camfrog โดยอัตโนมัติ

---

(P1)

**9\. Shared Observability Contract**

กำหนด Trace IDs, Operation IDs, Metrics, Audit Correlation และ Status Dashboards ที่เชื่อมข้ามทั้งสอง Repository ได้

---

(P1)

**10\. Windows Agent Capability Attestation**

ให้ Agent รายงาน Runtime Version, Camfrog Version, Supported Actions, Feature Availability และ Test Evidence แทนการถือว่า Windows ทุกเครื่องรองรับเหมือนกัน

---

(P2)

**11\. AI Tool/Model Governance**

ถ้าจะใช้ AI สำหรับงานของ ZChat ให้ผ่าน zWorkforce AI Gateway พร้อม Model Budget, Rate Limit, Approval และ Data Minimization

---

(P2)

**12\. Cross-Repository Contract CI**

เมื่อเปลี่ยน ZChat หรือ zWorkforce ต้องมี Compatibility Tests ที่ตรวจ Shared Schema, MCP Tools, API Contracts และ Execution Safety ก่อน Merge

## 3\. Architecture ที่ควรกำหนด

**zWorkforce - AI Operating System**

Planning · Workflows · Policies · Approval · MCP · Audit · AI Gateway

Authenticated Versioned Integration Contract

**ZChat Server - Application Control Plane**

Accounts · Machines · Commands · Resource Leases · Execution Policy

**Windows Agent A**

Standalone EXEs

**Windows Agent B**

Unified Client

**Authorized External Provider Operations**

Camfrog / LINE - Verification &amp; Reconciliation

หลักการคือ **zWorkforce เป็นผู้วางแผนและกำกับ ส่วน ZChat เป็นผู้รับผิดชอบ Execution สำหรับ Camfrog/LINE โดยตรง** และทุกการกระทำต้องผ่าน Authorization, Approval และ Resource Coordination ที่เกี่ยวข้อง

## 4\. Add-on Master Prompt V7.0

เพิ่มส่วนนี้ต่อท้าย V6.0 ที่สร้างไว้ก่อนหน้าได้ทันที

**document: **

# ZCHAT + ZWORKFORCE - CROSS-PLATFORM INTEGRATION MASTER PROMPT V7.0

## Objective

Inspect and integrate:

- https://github.com/cvsz/zchat
- https://github.com/cvsz/zworkforce

Build a governed, authenticated, versioned integration between the ZChat application control plane and the zWorkforce AI Operating System.

Do not assume both repositories are the same product or share the same authorization boundary.

## Phase 1 - Cross-Repository Investigation

Inspect both repositories, current commits, architecture documents, AGENTS.md files, existing APIs, job stores, approval authorities, event schemas, MCP implementations, identity providers, and deployment boundaries.

Identify existing reusable contracts before introducing new services.

Compare actual implementation against documentation.

Do not duplicate zWorkforce scheduling, AI routing, governance, or workflow infrastructure unnecessarily.

## Phase 2 - Canonical Control Boundary

Establish:

- zWorkforce owns governed planning and workflow orchestration.
- ZChat Server owns application-specific execution policy and account mapping.
- Windows Agents own authorized Windows runtime effects.
- A single canonical approval authority is required for each external mutation.
- A single enforceable execution authority is required per conflicting provider resource.

Never allow a generic AI agent to bypass ZChat execution validation.

## Phase 3 - Versioned Integration Protocol

Define typed versioned contracts for:

- Agent registration
- Capability discovery
- Account assignment
- Command submission
- Approval binding
- Execution claims
- Result reporting
- Cancellation
- Emergency stop
- Audit events

Require authenticated service-to-service communication.

Use tenant, user, account, agent, command, and correlation identifiers consistently.

## Phase 4 - Canonical Approval Verification

Use explicit approval grants bound to:

- Exact action
- Exact account/resource
- Exact arguments or immutable payload digest
- Authorized operator
- Expiration
- Nonce or single-use authorization
- Current execution policy version

Validate approvals immediately before execution.

Reject stale, replayed, mismatched, or revoked approvals.

Do not allow server or agent adapters to fabricate an approval.

## Phase 5 - Durable Execution and Resource Ownership

Implement:

- Durable command storage
- Replay-safe idempotency
- Local execution coordinator
- Distributed lease management
- Fencing generations
- Lease-loss handling
- Bounded retries
- Unknown outcome reconciliation
- Cancellation and emergency stop
- Audit correlation

Do not assume external Camfrog GUI actions support exactly-once effects.

Fail closed when execution ownership cannot be proven.

## Phase 6 - ZChat MCP Integration

Implement MCP resources and tools for:

- List agent capabilities
- Inspect provider runtime
- Read worker state
- Inspect feature health
- Inspect resource lock ownership
- Inspect sanitized operation history
- Submit an approved command
- Request cancellation
- Inspect reconciliation state

Read-only operations may be available under scoped authorization.

External mutations require matching approval, identity, lease, and execution-policy checks.

MCP tools must not directly invoke ungoverned Windows keyboard, mouse, or clipboard actions.

## Phase 7 - Event and Observability Integration

Implement versioned event contracts with correlation IDs:

- zchat.agent.connected.v1
- zchat.agent.disconnected.v1
- zchat.feature.started.v1
- zchat.feature.failed.v1
- zchat.resource.lock_conflict.v1
- zchat.operation.unknown.v1
- zchat.operation.verified.v1
- zchat.emergency_stop.activated.v1

Use a durable event/outbox strategy where required.

Prevent duplicate event delivery from causing duplicate external actions.

Connect logs, metrics, and traces while protecting user privacy.

## Phase 8 - Agent Enrollment and Capability Attestation

Every Windows Agent must advertise:

- Agent instance ID
- Machine identity
- Supported protocol version
- Application version
- Supported features
- Verified provider versions
- Supported execution modes
- Tested background capabilities
- Approved account scope
- Current health

Capability claims must distinguish configured, implemented, and live-verified functionality.

## Phase 9 - Security and Compatibility Tests

Test:

- Cross-tenant authorization
- Cross-account resource access
- Invalid approval
- Expired approval
- Approval replay
- Stale execution lease
- Agent impersonation
- Duplicate command delivery
- Network partition
- Emergency stop propagation
- Version incompatibility
- MCP unauthorized mutation attempts
- External outcome reconciliation
- Windows foreground input isolation

Add cross-repository contract CI that does not require access to production secrets.

## Phase 10 - Release Governance

Use reviewable changes in each repository.

Respect each repository's AGENTS.md, CODEOWNERS, required CI, signing, and branch protection.

Use independent authorized review with policedbc and eligible merge with cvsz.

Never force merge or bypass required checks.

Do not deploy or modify live infrastructure without appropriate authorization and validated ownership.

## Final Deliverables

- Cross-repository architecture report
- Source-backed gap matrix
- Versioned integration contracts
- Identity and approval mapping
- ZChat MCP adapter
- Durable execution integration
- Event and observability schemas
- Windows Agent capability attestation
- Cross-repository CI tests
- Security findings
- Actual integration acceptance evidence
- Production readiness verdict

Do not report integration as complete based on README capabilities alone.

Execute the safe, authorized implementation steps and report any remaining blockers explicitly.

## 5\. ข้อค้นพบเพิ่มเติมจากเอกสารที่แนบ

ใน `docs/architecture.md` ของไฟล์ `docs.zip` มีคำเตือนที่สำคัญ: ZChat Control Server ในเอกสารนั้นยังไม่ถือเป็น Production Deployment เพราะมี Process-local Rate Limiting, Provider Contracts ที่ยังไม่ครบ และขาด Production Recovery กับ Windows Soak Evidence

นอกจากนี้ เอกสาร `docs/CODEX-MASTER-PROMPTS.md` ยังบันทึกข้อบกพร่องของ Status Changer รุ่นก่อน เช่น การจัดการ Unicode/Thai Combining Marks, Empty Marquee Frames และการจัดการ Config Errors ซึ่งควรนำมาทำ Regression Tests ก่อน Release แต่ยังต้องตรวจว่า Defects เหล่านี้ยังเกิดขึ้นใน Source ล่าสุดหรือไม่

**ข้อเสนอแนะสุดท้าย\:** ก่อนเพิ่ม AI Automation มากขึ้น ให้ปิด P0 ทั้ง 5 เรื่อง ได้แก่ Integration Contract, Canonical Approval, Execution Authority, Replay Safety และ Emergency Stop ก่อน เพราะเป็นรากฐานที่ทำให้ zWorkforce ควบคุม ZChat หลายเครื่องได้โดยไม่เปิดช่องให้คำสั่งซ้ำหรือผิดบัญชี

ส่วน `cvsz/zworkforce` เองก็ยังต้องตรวจ Production Adapter Configuration, การทดสอบ Cross-Repository จริง และ Deployment Evidence เพิ่มเติม ไม่ใช่สรุปว่า Production Ready จาก Feature Inventory เพียงอย่างเดียว