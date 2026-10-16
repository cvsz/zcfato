# Architecture

## Purpose and scope

This repository combines reusable repository-governance and project-bootstrap tooling with maintained Windows applications and the ZChat control-plane products. The governance and bootstrap layers stay portable; each application keeps its own runtime, dependencies, build, and acceptance boundaries.

## Systems

### Repository governance and template tooling

Root policy documents define contribution, security, release, and agent behavior. `.github/` contains CI, CodeQL, dependency review, Dependabot, issue templates, and ownership rules. `scripts/bootstrap.py` changes project identity and ownership routing; it does not create an application runtime or deploy infrastructure. `scripts/validate_repo.py` checks required repository structure and local Markdown links.

### Camfrog desktop applications

The root Python modules implement separate Windows desktop tools for Camfrog workflows. UI Automation targets the installed official client. Build specifications and `build.bat` package each feature as a separate executable. Browser and session material remains local; automated tests use mocks and do not prove compatibility with a live Camfrog client or service.

### LINE Status Changer

`line/` contains a separate Windows UI Automation application, configuration store, schedule engine, tray integration, and build pipeline. Its unit tests run in Linux CI and again from `line/build.bat` before packaging. UI Automation acceptance still depends on the supported LINE desktop version and an interactive Windows session.

### ZChat Control Server and agent client

`control-server/` contains the FastAPI control plane, PostgreSQL schema and Alembic migrations, operator dashboard, agent protocol, and provider seams. `zchat-client/` is a separate Windows desktop client for the internal ZChat agent-chat protocol. It does not implement Camfrog's network protocol.

The checked-in Compose stack is for local development and binds to loopback. The control server is not a production deployment: its limiter is process-local, live provider contracts are incomplete, and production database, secret rotation, recovery, Windows runtime, and soak evidence are outstanding. See [control-server/README.md](../control-server/README.md).

## Build and validation boundaries

- Root application tests run from `tests/`.
- ZChat client tests run from `zchat-client/tests/` with the control-server source on the import path.
- Control-server tests and Alembic PostgreSQL migration validation run from `control-server/`.
- LINE unit tests run from `line/tests/`; the Windows build executes them before packaging.
- `full-build.bat` builds the Windows application artifacts and records the source commit and cleanliness state.
- GitHub CI runs Python tests, dependency audits, format/lint checks, migration validation, and the Windows build. These checks do not replace interactive Windows acceptance or production deployment/recovery evidence.

`make validate-template` validates repository structure and local Markdown links. `make test` runs the root, control-server, ZChat client, and LINE unit suites. Package builds remain Windows-only.

## Deployment boundary

The root `Dockerfile` and generic task-runner conventions belong to the reusable template and are not a deployment configuration for these desktop products. No public control-server deployment workflow is configured. A successful build or protected-branch merge is not evidence of a production deployment or production readiness.
