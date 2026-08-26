# DataSentinel Architecture

## System overview

```text
Windows / Linux Endpoint
        │
        ▼
  DataSentinel Agent  (Python, local SQLite)
        │  Filesystem discovery → file type detection → content extraction
        │  → PII detection (Presidio + custom) → secret detection → validation
        │  → context analysis → risk engine → optional OpenRouter AI classification
        │  → local result store
        ▼
   Secure REST API  (mutual TLS / API key + JWT)
        │
        ▼
  DataSentinel Backend  (FastAPI, PostgreSQL)
        │  endpoint registration, auth, scan management, finding ingestion,
        │  risk aggregation, policy management, reporting, audit logging
        ▼
  DataSentinel Dashboard  (React + TypeScript, SOC-style UI)
```

The three components are **loosely coupled**: the agent can run and produce a full local
scan report with zero connectivity to the backend, and the backend/frontend never reach
into an endpoint directly — all communication is agent-initiated, over the backend's
`/api/v1/*` HTTP API (self-documented via FastAPI's generated OpenAPI schema at
`/docs` when the server is running; request/response shapes also live in
`backend/datasentinel_backend/api/v1/schemas.py`).

## Component responsibilities

### Endpoint Agent (`agent/`)

Runs on the monitored Windows/Linux endpoint. Responsible for everything left of the
"Secure REST API" boundary above:

- **discovery/** — walks configured include/exclude paths, applies extension/size/depth
  filters, handles cancellation and timeouts.
- **filesystem/** — low-level file metadata (size, timestamps, owner, permissions,
  SHA-256), symlink/junction safety.
- **parsers/** — `DocumentParser` implementations per file type (txt, csv, json, xml, log,
  md, pdf, docx, xlsx, pptx); a malformed file must never abort a scan.
- **pii/** — Presidio-based + custom regex PII detectors, with validators (Luhn, format
  checks) to cut false positives.
- **secrets/** — entropy- and pattern-based secret detection (API keys, JWTs, private
  keys, connection strings, ...), treated as more severe than generic PII.
- **risk/** — deterministic risk scoring engine (category, confidence, occurrence count,
  location, permissions → LOW/MEDIUM/HIGH/CRITICAL). Policy-configurable, no ML in the
  critical path.
- **ai/** — optional OpenRouter client. Only redacted, minimal-context snippets are ever
  sent; failures degrade gracefully and never block scanning.
- **storage/** — local SQLite persistence (scans, files, findings, scan_errors, policies,
  agent_events) via SQLAlchemy + Alembic.
- **reporting/** — JSON/CSV/HTML report generation and remediation recommendations.
- **policy/** — scan profiles (quick/standard/deep/custom), exclusion rules, resource
  limits (max_workers, max_cpu, max_file_size, scan_timeout).
- **scheduler/** — one-time/daily/weekly/custom-interval scan scheduling.
- **logging/** — structured, secret-safe logging (no raw PII/secrets ever logged).
- **cli/** — the `datasentinel` command-line entry point.

The agent is designed to be packaged standalone with PyInstaller and installed as a
Windows Service or Linux systemd unit, independent of the central server.

### Backend (`backend/`)

Central FastAPI service. Owns the multi-tenant PostgreSQL database (organizations, users,
endpoints, scans, files, findings, policies, audit_logs), authentication, and all
dashboard-facing APIs. No detection logic runs here — it only ingests findings the agent
already produced and computes aggregate/organization-level risk views.

### Frontend (`frontend/`)

SOC-style React/TypeScript dashboard (Overview, Endpoints, Scans, Findings, PII Explorer,
Secrets, Policies, Reports, Audit Logs, Settings) built on Vite, Tailwind, shadcn/ui, and
Recharts, talking to the backend exclusively through its documented REST API via
TanStack Query.

## Privacy & security architecture

DataSentinel is **local-first by default**:

```text
File → local extraction → local PII/secret detection → local risk calculation
```

- Complete files are **never** uploaded anywhere, including to the central backend — only
  finding metadata and redacted evidence (e.g. `ri***@example.com`, `AB******23`) leave
  the endpoint.
- AI classification (OpenRouter) is **opt-in** (`AI_ENABLED=true`) and, when used, only
  receives redacted context for a single suspicious snippet — never whole files,
  directories, or unredacted values. If OpenRouter is unreachable or errors, scanning
  continues unaffected; AI is a pure enhancement, never a dependency of the detection
  pipeline.
- LLM responses are treated as untrusted structured data (parsed JSON with a fixed
  schema): they are never used to execute commands or modify files.
- Findings store **redacted evidence only** by policy; raw sensitive values are not
  persisted to disk or written to logs.
- Default scan locations exclude system/OS directories (`C:\Windows`,
  `/proc`, `/sys`, `/dev`, `/run`, etc.) unless explicitly configured by an administrator.

## Technology choices

| Layer | Technology | Why |
|---|---|---|
| Agent language | Python 3.12+ | Rich ecosystem for document parsing (PyMuPDF, python-docx, openpyxl, python-pptx) and PII detection (Presidio); single codebase for Windows + Linux via PyInstaller |
| Agent local store | SQLite + SQLAlchemy + Alembic | Zero-ops embedded DB appropriate for a single-endpoint agent; same ORM/migration tooling as the backend for consistency |
| Backend framework | FastAPI + Pydantic | Async-capable, typed request/response models, automatic OpenAPI schema the frontend/TanStack Query layer can rely on |
| Backend store | PostgreSQL + SQLAlchemy + Alembic | Multi-tenant relational data (orgs/users/endpoints/findings) with mature migration tooling |
| Frontend | React + TypeScript + Vite | Fast dev loop, typed component tree for a data-dense SOC UI |
| UI kit | Tailwind CSS + shadcn/ui | Accessible, unstyled-by-default primitives that avoid a "generic AI app" gradient-heavy look; consistent severity color system |
| Charts | Recharts | Composable charts for severity/category/endpoint/time breakdowns |
| Data fetching | TanStack Query | Caching, background refetch, and request dedup for dashboard polling |
| Optional AI | OpenRouter (model-agnostic) | Swappable model provider; structured JSON responses only, used purely as a secondary classifier |

## Why the agent's Python package is named `datasentinel_agent` (not bare `agent`)

The spec's module list for the agent includes a subpackage literally named `logging`.
Importing `agent.logging.something` is safe, but if the `agent/` directory itself were
ever placed on `sys.path` directly (a common footgun when running scripts from inside a
project folder), a top-level package named `logging` would shadow the Python standard
library's `logging` module for the whole process. To avoid that class of bug entirely,
the actual importable package lives at `agent/datasentinel_agent/` (with the same
`discovery/filesystem/parsers/pii/secrets/risk/ai/storage/reporting/policy/scheduler/
logging/cli/` submodules the spec calls for), while `agent/` itself remains the top-level
project folder (matching the required repository layout) containing `pyproject.toml`,
`main.py`, `config/`, `scripts/`, and `tests/`. The same nesting pattern is used for the
backend (`backend/datasentinel_backend/`) for consistency.
