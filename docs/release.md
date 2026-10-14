# Release

## Scope

This repository includes project-specific Windows packaging and manual release tooling in `full-build.bat`, `full-build.ps1`, and `tools/release.py`; publishing credentials and approval policy remain operator-managed. The ZChat Control Server Compose stack is for local development, binds to loopback, and has no public deployment workflow.

## Versioning

Use an explicit versioning policy. Semantic Versioning is recommended for reusable software unless the project defines a better scheme.

## Release checklist

1. Confirm the release commit is the intended exact head.
2. Ensure required CI/security checks pass on that exact head.
3. Confirm protected-branch/admin controls are effective.
4. Update `CHANGELOG.md` and compatibility/migration notes.
5. Verify deployment and rollback procedures.
6. Verify migrations and data rollback/forward strategy when applicable.
7. Verify required backup/restore evidence for stateful systems.
8. Create/push the release tag according to project policy.
9. Publish artifacts only from trusted workflows/environments.
10. Generate provenance/signing/attestation where required.
11. Verify the published artifact and deployed environment.
12. Record release evidence and remaining known risk separately.

## Production readiness

Release authorization and production readiness are distinct.

A maintainer may authorize a release with accepted risk, but accepted risk does not convert `PARTIALLY VERIFIED`, `UNVERIFIED`, or `BLOCKED` readiness gates into `VERIFIED`.

Use the canonical evidence definitions in `../ZEAZ-INTRODUCTION.md`.

For ZChat Control Server, use [`../control-server/docs/architecture.md`](../control-server/docs/architecture.md) as the implementation boundary. The current server is an MVP; do not publish or expose it publicly until its listed Windows runtime, authenticated provider, observability, backup/restore, and soak gates have direct evidence.

## Rollback

Document and test, as appropriate:

- last known-good artifact/build
- application rollback
- safe database/data migration handling
- configuration rollback
- credential/artifact invalidation after compromise
- traffic/routing rollback
- operator and stakeholder communication

A rollback document without environment-appropriate execution evidence is not proof that recovery will work.
