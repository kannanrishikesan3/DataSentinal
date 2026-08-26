# DataSentinel

**AI-Powered Endpoint Data Risk Discovery Platform**

> Discover. Classify. Protect.

DataSentinel is a cross-platform endpoint data discovery and PII / security-sensitive-data
detection platform for **authorized enterprise security teams**. It scans Windows and Linux
endpoints, discovers files containing PII and sensitive information, classifies findings,
calculates risk, and surfaces everything in a centralized security dashboard.

This is a defensive security product intended for use in environments where scanning has
been explicitly authorized (e.g. by IT/security leadership, as part of a DLP or data-risk
program). It performs **read-only discovery** — it never modifies, exfiltrates, or deletes
scanned files.

## Repository layout

```text
datasentinel/
├── agent/      # Endpoint agent (Python) — filesystem discovery, PII/secret detection,
│               # local risk scoring, local SQLite store, CLI, Windows Service / systemd
├── backend/    # Central FastAPI server — endpoint registration, scan/finding ingestion,
│               # policy management, reporting, dashboard APIs, audit logging (PostgreSQL)
├── frontend/   # React + TypeScript SOC-style dashboard (Vite, Tailwind, shadcn/ui)
├── tests/      # Cross-component integration tests
├── docs/       # Architecture, phase plan, and design documentation
└── docker/     # Local development / deployment compose files
```

Each of `agent/`, `backend/`, and `frontend/` is an independently deployable project with
its own dependency manifest, environment, and test suite — they are loosely coupled and
communicate only over the documented HTTP API.

## Status

All 18 implementation phases are complete, plus two rounds of hardening against the fuller
spec: archive (ZIP/TAR/GZIP) scanning, real agent↔backend sync (centrally-pushed policies
*and* scan-report upload — both were previously configured-but-unused), an idempotent,
retrying offline upload queue (a scan whose upload fails is queued and safely retried —
"safely" meaning the backend now dedupes by the agent's own scan id, so a retry of an
upload that actually succeeded server-side can never create a duplicate), adversarial
security testing (cross-org IDOR, SQLi/XSS-shaped input, expired/forged JWTs), performance
testing at up to 100k files, both a Linux `.deb` and `.rpm` package, and an on-prem
(no-Docker, Apache-based) deploy script. 222 agent tests, 61 backend tests, 5 cross-component
tests (including a real end-to-end agent→live-backend-over-a-real-socket run), and the
frontend builds/typechecks cleanly. See [`docs/PHASES.md`](docs/PHASES.md) for what was
built in each phase and [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md) for performance results.

Genuinely not done (needs infrastructure this project wasn't built with access to): the
Windows MSI installer is written (`installer/windows/`) but never built/run — no Windows
machine or WiX toolchain was available; and no real Windows/Linux VM install-test matrix
has been run (the `.deb` and `.rpm`, however, *were* fully installed/upgraded/removed for
real on this project's own Ubuntu box — see their READMEs).

## Privacy & security posture

- **Local-first**: extraction, PII/secret detection, and risk scoring all happen on the
  endpoint. Only findings metadata and redacted evidence are ever sent to the central server.
- **AI is optional and never primary**: the scanner is fully functional with `AI_ENABLED=false`.
  When enabled, only redacted, minimal context is sent to OpenRouter for classification —
  never whole files or directories.
- **No raw sensitive values are persisted or logged** — findings store redacted evidence only
  (e.g. `ri***@example.com`).

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#privacy--security-architecture) for details.

## Security

See [SECURITY.md](SECURITY.md) for the threat model, hardening measures, and
authorized-use scope.

## Getting started

Component-level setup instructions live in each project's own README:

- [`agent/README.md`](agent/README.md)
- [`backend/README.md`](backend/README.md)
- [`frontend/README.md`](frontend/README.md)

## Installing the endpoint agent

- **Linux (`.deb`)**: [`installer/linux/deb/README.md`](installer/linux/deb/README.md) —
  build/install/upgrade/remove/purge all verified for real on Ubuntu 24.04. Installs a
  systemd service running as an unprivileged `datasentinel` account.
- **Linux (`.rpm`)**: [`installer/linux/rpm/README.md`](installer/linux/rpm/README.md) —
  the RHEL/Rocky/AlmaLinux/Amazon Linux equivalent, same install/upgrade/erase verification.
- **Windows (`.msi`)**: [`installer/windows/README.md`](installer/windows/README.md) —
  WiX v4 source + build script. **Not built or run** — written without a Windows machine
  or WiX toolchain available; work through that README's test checklist on a real Windows
  VM before using it.

## Deploying the backend + dashboard

- **Docker**: [`docker/README.md`](docker/README.md) — `docker compose up` brings up
  PostgreSQL, the backend, and the frontend.
- **On-prem, no Docker**: [`scripts/deploy-on-prem.sh`](scripts/deploy-on-prem.sh) —
  installs PostgreSQL/nginx/Node.js, runs the backend under systemd + uvicorn behind an
  nginx reverse proxy, and builds/serves the frontend as a static bundle. Idempotent
  (safe to re-run after `git pull`). Reviewed carefully but not executed end-to-end in
  this project's own sandbox (it makes system-wide changes — PostgreSQL roles, an nginx
  site, a new system user — that weren't applied here without explicit sign-off; the
  equivalent Linux `.deb` install *was* fully installed/upgraded/removed/purged for real,
  see above). Run it on your actual target server:

  ```bash
  sudo DOMAIN=dashboard.example.com ./scripts/deploy-on-prem.sh
  ```

  Then create the first admin (there's no signup UI by design):

  ```bash
  sudo -u datasentinel-backend bash -c \
    "set -a; source /etc/datasentinel-backend/backend.env; set +a; \
     exec /opt/datasentinel-backend/.venv/bin/python /opt/datasentinel-backend/scripts/create_org_admin.py \
     --org 'Your Org' --email admin@example.com"
  ```
