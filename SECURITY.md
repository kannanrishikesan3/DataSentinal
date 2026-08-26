# Security

DataSentinel is a **defensive** data-discovery tool for authorized enterprise
security teams. This document covers its own security posture — not a
detection-methodology guide (see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
for that).

## Scope and authorized use

Deploy DataSentinel only on endpoints you are authorized to scan (owned or
explicitly approved by your organization's security/IT leadership, e.g. as
part of a DLP or data-risk program). The agent performs **read-only**
discovery — it never writes to, moves, or deletes a scanned file, and never
executes anything found while scanning.

## What DataSentinel does NOT do

By design, none of the following exist anywhere in this codebase:
credential theft, keylogging, browser-password extraction, persistence
mechanisms other than the legitimate Windows Service / systemd unit
installation described in [agent/README.md](agent/README.md), stealth or
anti-detection behavior, privilege escalation, remote shell access,
destructive file operations, or bypassing another security control. A
`grep` audit for `eval`/`exec`/`os.system`/`subprocess`/`shell=True`/
`pickle.load`/raw-SQL-string-formatting across both `agent/` and `backend/`
returns nothing — the codebase has no code-execution or shell-out surface at
all today.

## Hardening measures, by layer

### Endpoint agent

- **Local-first, read-only.** Extraction, detection, and risk scoring all
  happen on the endpoint; the agent never uploads whole files (see
  [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#privacy--security-architecture)).
- **Symlink safety**: symlinks are never followed by default; when enabled,
  a visited-real-path set prevents cycles (`discovery/walker.py`).
- **XXE / entity-bomb protection**: XML is parsed with `defusedxml`, never
  the stdlib parser (`parsers/xml_parser.py`).
- **Bounded resource use**: streaming SHA-256 (constant memory regardless of
  file size), per-profile `max_file_size_mb`/`max_depth`/`max_workers`, and a
  hard `scan_timeout_seconds` (`discovery/config.py`, `config/default.yaml`).
- **CPU-aware scheduling**: a scheduled scan is skipped (and retried next
  poll) if the system is already under load, rather than piling on
  (`scheduler/cpu_guard.py`).
- **No raw sensitive values persisted or logged.** `Finding` objects are
  constructed with redacted evidence only (`pii/redaction.py`) — there is no
  code path that stores or logs a complete PII/secret value. A logging
  filter (`logging/redaction_filter.py`) additionally scrubs anything
  email/SSN/card/key-shaped from every log line as defense in depth, even
  though the pipeline's own log calls never include finding evidence.
- **Optional AI is genuinely optional and minimal.** `AI_ENABLED=false` by
  default; when enabled, only a finding's already-redacted evidence +
  category (never a raw value or file content) is sent, and any
  OpenRouter failure leaves the finding unchanged rather than blocking the
  scan (`ai/service.py`, `ai/openrouter_client.py`).
- **Least privilege service installation.** The systemd unit runs as a
  dedicated unprivileged account with `NoNewPrivileges`, `ProtectSystem=strict`,
  and read-only `/home` (`scripts/datasentinel-agent.service`); the Windows
  Service needs Administrator only to *install*, not to run.

### Backend

- **No unauthenticated administrative endpoint.** Every route other than
  `GET /health` requires either a JWT (dashboard users) or a per-endpoint API
  token (agents) — see `security/dependencies.py`.
- **Organization-scoped data access.** Every query filters by the
  authenticated principal's `org_id`; covered by
  `test_findings_are_scoped_to_organization`.
- **Password/token hashing**: bcrypt via `passlib` for both user passwords
  and endpoint API tokens (`security/passwords.py`, `security/tokens.py`).
  Endpoint tokens embed only their (non-secret) endpoint ID in plaintext,
  never the secret material — the token itself is never stored, only its
  bcrypt hash.
- **Fails loud on insecure production config**: the backend refuses to
  start with `DATASENTINEL_ENV=production` and the default
  `DATASENTINEL_SECRET_KEY` rather than silently signing JWTs with a
  publicly-known key (`core/config.py`).
- **No raw SQL string formatting anywhere** — every query goes through
  SQLAlchemy's parameterized query builder.
- **Audit logging**: every mutating action (endpoint registration, scan
  ingestion, finding status changes, policy changes) writes an
  `audit_logs` row (`services/audit.py`).
- Schema migrations are applied explicitly via Alembic, never implicitly on
  app boot (see `main.py`'s docstring) — avoids races between concurrently
  starting replicas and keeps migration history authoritative.
- **IDOR coverage across every by-ID route** (endpoints, scans, findings,
  reports): `backend/tests/test_security_hardening.py` and the existing
  `test_findings_are_scoped_to_organization` confirm a second organization's
  admin gets 404, never data, when guessing/enumerating another org's
  resource IDs.
- **Adversarial input handling verified, not just assumed**: SQL-injection-
  shaped query parameters and login input, and stored-XSS-shaped input in
  finding fields rendered into the HTML report, are exercised directly in
  `test_security_hardening.py` — the app already handled all of them
  correctly (parameterized queries, `html.escape` in `services/reports.py`);
  these tests exist so a future regression is caught automatically.
- **The manual grep audit above is now an enforced test**, not just a
  README claim: `tests/test_security_static_audit.py` fails the build if
  `eval`/`exec`/`os.system`/`subprocess`/`shell=True`/`pickle.load`/raw-SQL-
  string-formatting is ever introduced into `agent/` or `backend/`.

### Agent → backend sync

- **Policy fetch and scan upload are both real HTTP clients now**
  (`agent/datasentinel_agent/sync/`), not just configured-but-unused
  settings. Both authenticate with the endpoint's own bearer token, both
  time out and retry a bounded number of times, and both degrade to "stays
  local" — never raising into the scan — on any failure: backend not
  configured, unreachable, or returning a malformed response. Covered by
  `agent/tests/test_policy_sync.py` and `agent/tests/test_scan_uploader.py`.
- **A failed upload is queued and retried, safely** (spec section 53):
  `agent/datasentinel_agent/sync/upload_queue.py` persists failed uploads
  (bounded by `retention.local_days`, default 7) and the scheduler retries
  them every tick. "Safely" is load-bearing here — retrying a request whose
  first attempt may have actually succeeded server-side (response merely
  lost) is only safe if the server can tell it's the same request. The
  backend's `Scan.agent_scan_id` (unique per endpoint) is that idempotency
  key: `services.scans.ingest_scan_report` returns the existing scan
  unchanged on a repeat submission rather than creating a duplicate.
  Verified with a real double-submission over an actual socket in
  `tests/test_agent_to_backend_integration.py`, not just unit-tested.

## Reporting a vulnerability

This is a demonstration/reference implementation, not a maintained public
project with a security contact. If you fork or deploy it, review the
hardening measures above against your own threat model before production
use — in particular, generate real secrets (`DATASENTINEL_SECRET_KEY`,
database credentials) and never reuse the values in `.env.example`.
