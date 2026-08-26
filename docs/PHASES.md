# Implementation phases

Tracks progress against the 18-phase plan. Each phase is implemented, tested, and
stabilized before the next one starts.

| # | Phase | Status |
|---|---|---|
| 1 | Project structure + configuration | ✅ Done |
| 2 | Windows/Linux filesystem discovery | ✅ Done |
| 3 | File metadata + SHA-256 | ✅ Done |
| 4 | Document extraction | ✅ Done |
| 5 | Presidio + custom PII detectors | ✅ Done |
| 6 | Secret detection | ✅ Done |
| 7 | Risk engine | ✅ Done |
| 8 | SQLite storage | ✅ Done |
| 9 | CLI | ✅ Done |
| 10 | Reports | ✅ Done |
| 11 | OpenRouter integration | ✅ Done |
| 12 | FastAPI backend | ✅ Done |
| 13 | PostgreSQL | ✅ Done |
| 14 | React dashboard | ✅ Done |
| 15 | Scheduling | ✅ Done |
| 16 | Windows Service + Linux systemd | ✅ Done |
| 17 | Security hardening | ✅ Done |
| 18 | Testing + packaging + documentation | ✅ Done |

## Phase 1 — what was built

- Repository skeleton for `agent/`, `backend/`, `frontend/`, `tests/`, `docs/`, `docker/`
  per the required top-level layout, with the agent/backend module lists from the spec
  (discovery, filesystem, parsers, pii, secrets, risk, ai, storage, reporting, policy,
  scheduler, logging, cli / api, models, services, repositories, security) scaffolded as
  empty, importable packages ready for later phases.
- Working configuration systems for both the agent and the backend (Pydantic Settings,
  `.env` support, `default.yaml` scan-profile/exclusion defaults for the agent), covered
  by smoke tests.
- Independent dependency manifests (`pyproject.toml`) for the agent and backend, each
  installable into its own virtual environment.
- Frontend scaffolded with Vite + React + TypeScript + Tailwind CSS.
- Git repository initialized.

Explicitly **not** in Phase 1 (deferred to their named phases): filesystem walking, file
parsing, PII/secret detection logic, the risk engine, the SQLite schema, CLI commands
beyond `--version`, the FastAPI routes, and the dashboard UI.

## Phases 2–11 — what was built

The full endpoint agent pipeline, real (not mocked) end to end:

- **Discovery** (`agent/datasentinel_agent/discovery/`): safe recursive walk with
  include/exclude paths, extension/size/depth filters, no-blind-symlink-following with
  cycle detection, permission-error handling, worker-pool concurrency, cancellation, and
  a wall-clock timeout.
- **Filesystem** (`filesystem/`): streaming SHA-256 (bounded memory), MIME detection
  (`python-magic` with a `mimetypes` fallback), owner/permissions/timestamps.
- **Parsers** (`parsers/`): the `DocumentParser` interface plus txt/csv/json/xml/log/md/
  pdf/docx/xlsx/pptx implementations (PyMuPDF, python-docx, openpyxl, python-pptx,
  defusedxml for XXE/entity-bomb safety), all wrapped so one corrupted file never aborts
  a scan.
- **PII** (`pii/`): Presidio (optional — the scanner works fully without it) plus a
  dependency-free regex+validator layer covering every required category, with real
  checksum validators (Luhn, Verhoeff/Aadhaar, IBAN mod-97, PAN holder codes, SSN area
  rules) and context-based confidence scoring.
- **Secrets** (`secrets/`): vendor patterns (AWS, GitHub, Stripe, Google, Slack), JWT
  structural validation, private/SSH key block detection, DB URL/connection-string
  detection, and Shannon-entropy fallback for unrecognized high-randomness tokens.
- **Risk** (`risk/`): deterministic, policy-configurable scoring — secrets force
  CRITICAL, category aggregation and over-permissive/high-exposure files escalate
  severity, all thresholds live in `config/default.yaml`.
- **Storage** (`storage/`): SQLAlchemy models for all six spec tables, managed by
  Alembic; raw sensitive values are never persisted, only redacted evidence.
- **CLI** (`cli/`): `scan`, `status`, `report`, `config validate`, matching the spec's
  output format.
- **Reporting** (`reporting/`): JSON/CSV/HTML/text report generation plus an advisory
  (never file-modifying) recommendations engine.
- **AI** (`ai/`): OpenRouter client with timeout/retry/rate-limiting, used only as an
  optional confidence refinement on low-confidence findings — sends redacted evidence
  only, never raw values or whole files, and any failure leaves the finding unchanged.

122 tests pass across this pipeline, including a full end-to-end integration test
(discovery through storage) and adversarial cases (XML entity bombs, corrupted PDFs/
DOCX/XLSX, permission-denied directories, OpenRouter timeouts/malformed responses).

## Phases 12–14 — what was built

- **Backend** (`backend/`): FastAPI + PostgreSQL-targeted schema (SQLite-portable for
  tests — see `backend/README.md`'s "Database portability" section), Alembic migrations,
  JWT auth for dashboard users + per-endpoint API tokens for agents, org-scoped data
  access on every query, audit logging on every mutation, and a policy CRUD API. 30 tests.
- **Dashboard** (`frontend/`): all ten nav pages (Overview, Endpoints, Scans, Findings,
  PII Explorer, Secrets, Policies, Reports, Audit Logs, Settings) wired to the real
  backend via TanStack Query, JWT login with protected routes, shadcn/ui-style
  components on Tailwind v4, Recharts severity/category/endpoint charts. Verified with a
  headless-browser (Playwright) smoke test against a live backend + seeded data across
  every page, zero console errors — screenshots reviewed by hand during the build.

## Phases 15–18 — what was built

- **Scheduling** (`agent/datasentinel_agent/scheduler/`): one-time/daily/weekly/
  custom-interval schedules (JSON-persisted, not a spec-table addition — this is
  operational config like the scan profiles, not scan/finding data), CPU-aware
  throttling, catch-up-without-bursting for missed custom intervals, wired into the CLI
  (`datasentinel schedule add/list/remove/run`).
- **OS service integration** (`agent/datasentinel_agent/service/`,
  `agent/scripts/`): a hardened systemd unit (dedicated unpriv account,
  `ProtectSystem=strict`, graceful `SIGTERM` handling) and a Windows Service wrapper
  (pywin32, platform-guarded so it fails clearly rather than crashing on Linux) — both
  drive the identical `SchedulerService.run_forever()` loop.
- **Security hardening**: a grep-audited codebase (no `eval`/`exec`/`subprocess`/
  `shell=True`/raw-SQL-formatting anywhere), a structured JSON logging module with a
  redaction filter (defense in depth on top of findings never carrying raw values), and
  a backend startup check that refuses to run in production with the default JWT secret.
  Documented in [`../SECURITY.md`](../SECURITY.md). Caught and fixed two real bugs in
  the process: parse errors weren't being persisted to `scan_errors` (only returned in
  the summary object), and default 644 file permissions were being flagged as
  "over-permissive" (which would have made the signal useless — nearly every file
  defaults to 644).
- **Testing + packaging**: closed the two remaining gaps from spec section 37's test
  checklist (Windows-path handling, AI timeout) — every other item was already covered
  in earlier phases. Packaged the agent with PyInstaller
  (`agent/datasentinel-agent.spec`) into a single-file binary, verified by actually
  running it: `config validate` and a real `scan` against synthetic PII/secrets both
  produce correct output from the frozen binary. 156 agent tests, 32 backend tests, 188
  total, all green; frontend builds and typechecks cleanly.

## Post-18-phase hardening — what was built

Closing gaps found against the fuller (65-section) spec, beyond the condensed
18-phase roadmap above:

- **Archive scanning** (`agent/datasentinel_agent/parsers/archive_parser.py`):
  ZIP/TAR/GZIP as scannable file types, opt-in per profile
  (`scan.profiles.*.scan_archives` — on for `deep`, off elsewhere), extracted
  into an isolated temp directory with member-count/uncompressed-size/ratio
  limits, path-traversal and symlink members skipped, and no recursive
  archive-in-archive extraction. 11 new tests.
- **Centrally-pushed policy sync + real scan upload** (`agent/datasentinel_agent/sync/`):
  this was the point where it became clear the agent had *no* backend HTTP
  client at all yet — `backend_url`/`endpoint_token` settings existed but
  nothing in agent code ever called the backend; the only place a scan
  report reached the backend's ingestion API was
  `tests/test_agent_to_backend_integration.py` manually building the
  payload. Fixed both directions:
  - **Policy fetch**: `GET /api/v1/policies/effective` (new,
    endpoint-token-authenticated route) is fetched once per scan and merged
    onto the local config (risk thresholds, extra exclude paths,
    per-profile overrides).
  - **Scan upload**: `POST /api/v1/scans` is now called automatically at
    the end of every scan when the backend is configured, reusing the exact
    field mapping the integration test already proved works
    (`sync/scan_uploader.py`).
  Both directions degrade to "stays local" on any failure (backend unset,
  unreachable, or malformed policy/response) — wrapped in an outer
  `try/except` in `core/pipeline.py` as defense in depth so a bug in either
  client can never fail a scan that already completed and was persisted.
  17 new agent tests, 3 new backend tests.
- **Backend API completeness + IDOR coverage**: added the spec's
  `GET /api/v1/endpoints/{id}` (previously missing entirely), plus a
  dedicated adversarial test file (`backend/tests/test_security_hardening.py`)
  covering expired/forged/unknown-subject JWTs, cross-org IDOR across every
  by-ID route (endpoints/scans/findings/reports), SQL-injection-shaped query
  params and login input, stored-XSS-shaped input in the HTML report
  (confirmed escaped), and path-traversal-shaped `scan_paths` (confirmed
  stored as an opaque string, never interpreted). All 9 passed without code
  changes — this was verification, not remediation. Also added
  `tests/test_security_static_audit.py`, turning SECURITY.md's manual
  `eval`/`exec`/`subprocess`/`shell=True`/`pickle.load`/raw-SQL-formatting
  grep audit into an enforced regression test.
- **Performance testing** (`agent/scripts/perf_test.py`): a synthetic-dataset
  generator + real pipeline run measuring wall-clock duration, peak RSS, and
  throughput at 1k/10k/100k files. See docs/PERFORMANCE.md for results.
- **Windows MSI installer scaffold** (`installer/windows/`): a WiX v4
  `Product.wxs` + `build.ps1`, plus a second PyInstaller build target
  (`agent/service_main.py` / `agent/datasentinel-agent-service.spec`) so the
  Windows Service has its own frozen binary rather than requiring a full
  Python venv. **Not built or run** — authored without a Windows/WiX
  toolchain available in this environment; see
  `installer/windows/README.md` for the build steps and test checklist
  that still need to run on a real Windows VM before this ships.

## Post-18-phase hardening, round 2 — what was built

A further pass against the checklist explicitly called out "Offline Queue + Retry",
"Windows MSI Installer", and "Linux systemd + Packages" as distinct deployment items —
prompting a closer look at each:

- **Offline queue + retry, made actually safe** (spec section 53): previously, a failed
  scan upload was just logged and forgotten — there was no retry at all. Now:
  `agent/datasentinel_agent/sync/upload_queue.py` persists failed uploads (JSON, same
  pattern as `scheduler/store.py`) with a `retention.local_days` expiry (new config field,
  also from the spec — section 54 — but previously unimplemented), and
  `scheduler/service.py`'s `tick()` retries the queue every poll. This surfaced a real
  correctness gap: the backend's `POST /api/v1/scans` had no idempotency key at all, so a
  retried upload of a report that had actually already succeeded (response merely lost)
  would have created a **duplicate** scan + duplicate findings. Fixed end to end: a new
  `agent_scan_id` column on the backend's `Scan` model (unique per endpoint, new Alembic
  migration `fe10d265a106`), the agent now sends its own scan id, and
  `services.scans.ingest_scan_report` returns the existing scan unchanged on a repeat
  submission instead of re-ingesting. 11 new agent tests, 3 new backend tests, plus a new
  cross-component test that submits the same scan twice over a real socket and asserts no
  duplicate.
- **A more honest end-to-end test**: the existing agent→backend integration test hand-built
  the request payload the way the backend expects; a new test instead drives the actual
  production code — `sync.scan_uploader.build_scan_report_payload` +
  `sync.backend_client.BackendClient` — over a real TCP socket against a real FastAPI app
  (`uvicorn` in a background thread), not an in-process test client. This is what caught the
  duplicate-upload gap above.
- **Linux `.rpm` package** (`installer/linux/rpm/`): mirrors the `.deb` for RHEL/Rocky/
  AlmaLinux/Amazon Linux — same binary, same systemd unit, RPM `%pre`/`%post`/`%preun`/
  `%postun` scriptlets instead of dpkg's maintainer scripts. Installed, upgraded, and
  erased for real on this project's own machine (`rpm -i`/`-U`/`-e` work standalone
  without an RPM-based host OS). Caught and fixed a real bug: the spec's `%files` didn't
  own the `/opt/datasentinel-agent` directory itself, only the file inside it, so erasing
  left an empty directory behind — fixed with `%dir` entries and re-verified clean.

**Still not built / out of scope for this environment**:
- Windows MSI installer — written (`installer/windows/`) but never built or run; no
  Windows machine or WiX toolchain exists here.
- Real installer/VM testing (spec sections 44/45) beyond what's documented in the `.deb`
  and `.rpm` READMEs, at-scale performance testing beyond docs/PERFORMANCE.md, and
  code-signing for the Windows binaries — all require infrastructure (Windows/Linux VMs,
  a signing cert) this sandboxed environment doesn't have.
