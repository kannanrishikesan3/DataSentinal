# DataSentinel Backend

Central FastAPI server: endpoint registration, authentication, scan management,
finding ingestion, risk aggregation, policy management, reporting, dashboard APIs,
and audit logging. Schema targets PostgreSQL in production; the test suite runs
against in-memory SQLite (see "Database portability" below).

## Status

See [`../docs/PHASES.md`](../docs/PHASES.md) for progress. Phases 12–13 (API +
schema) are complete.

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install -e ".[dev]"
cp .env.example .env
```

## Database

```bash
alembic upgrade head        # create/update the schema at DATASENTINEL_DATABASE_URL
alembic revision --autogenerate -m "..."   # after changing models/models.py
```

Tables (spec section 23): `organizations`, `users`, `endpoints`, `scans`, `files`,
`findings`, `policies`, `audit_logs`. Every endpoint belongs to an organization;
every finding is tied to an endpoint and a scan.

### Database portability

Production targets PostgreSQL. The test suite runs against in-memory SQLite for
speed and zero infrastructure dependency (this sandbox's Postgres instance has
no accessible credentials to provision a test role/database against). This is
made possible by `core/types.GUID` — a `TypeDecorator` that resolves to a native
`UUID` on PostgreSQL and `CHAR(36)` on SQLite — and by using SQLAlchemy's generic
`JSON` column type rather than PostgreSQL-specific `JSONB`. The schema, ORM
models, and every service function are otherwise identical between the two;
Alembic migrations are authored/tested against SQLite but contain only
dialect-generic `op.create_table(...)` calls, so the same migration file applies
cleanly to a real PostgreSQL deployment.

## Running

```bash
uvicorn datasentinel_backend.main:app --reload
curl http://localhost:8000/health
```

Schema creation/migration is **not** run automatically on startup — run
`alembic upgrade head` as an explicit deploy step first (see rationale in
`main.py`'s docstring: implicit DDL-on-boot races with multiple replicas and
bypasses migration history).

## API design notes

- **Two auth schemes**: dashboard users get a JWT from `POST /api/v1/auth/login`;
  each registered endpoint gets a long-lived API token (shown once, at
  registration) used to authenticate its own requests (`POST /api/v1/scans`).
  No unauthenticated administrative endpoint is ever exposed.
- **Scan ingestion is a single batch call.** The agent already runs a scan fully
  locally (its own SQLite-backed pipeline, Phases 2–11) before ever talking to
  this server — there's no live remote-control of an in-progress local scan in
  this phase. `POST /api/v1/scans` therefore accepts one full scan report
  (summary + files + findings) in one request rather than a separate
  finding-by-finding ingestion endpoint. `POST /api/v1/scans/{id}/cancel`
  records a cancellation request in the audit log; wiring that back to a
  running agent process is scheduler/agent-polling work for Phase 15.
- Every mutating route commits inside its own request and writes an
  `audit_logs` row via `services.audit.log_action`.
- All data access is **organization-scoped** — every query filters by the
  authenticated user's/endpoint's `org_id`, verified by tests
  (`test_findings_are_scoped_to_organization`).

## Tests

```bash
pytest
```
