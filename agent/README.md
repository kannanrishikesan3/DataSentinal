# DataSentinel Agent

The endpoint agent: filesystem discovery, document parsing, PII/secret detection,
local risk scoring, and local SQLite storage. Runs on Windows 10/11 and
Ubuntu/Debian/RHEL-family Linux, packaged standalone with PyInstaller.

## Status

Under active development — see [`../docs/PHASES.md`](../docs/PHASES.md) for progress.

## Setup

```bash
cd agent
python3 -m venv .venv
source .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install -e ".[dev]"
python -m spacy download en_core_web_sm   # Presidio's NLP model (optional — see below)
cp .env.example .env
```

Presidio's NLP-based recognizer (mainly person names) is **optional**: if
`en_core_web_sm` isn't installed, `datasentinel_agent.pii.presidio_engine`
degrades to unavailable and the regex/validator detectors — which cover every
required category — carry full detection weight on their own. For better name
detection accuracy in production, install the larger model and point
`DATASENTINEL_SPACY_MODEL=en_core_web_lg` at it.

## Configuration

Two layers, kept separate on purpose:

- **`.env`** (see `.env.example`) — secrets and per-install values: OpenRouter API
  key, backend URL/token, local DB path, log level. Loaded by
  `datasentinel_agent.config.settings.get_settings()`.
- **`config/default.yaml`** — operational scan defaults: profiles (quick/standard/
  deep), default include/exclude paths per OS, supported extensions. Loaded by
  `datasentinel_agent.config.scan_config.load_scan_config()`. Safe to review/diff;
  contains no secrets.

## Database

The local SQLite schema (scans, files, findings, scan_errors, policies,
agent_events) is managed by Alembic:

```bash
alembic upgrade head        # create/update the local DB at DATASENTINEL_DB_PATH
alembic revision --autogenerate -m "..."   # after changing storage/models.py
```

## Running

```bash
datasentinel --version
datasentinel scan --path /home/user/Documents
datasentinel scan --profile deep
datasentinel scan --no-ai
datasentinel status
datasentinel report --scan-id <id> --format json   # text | json | csv | html
datasentinel config validate

datasentinel schedule add --name nightly --type daily --time 02:00 --profile deep --path /home/user
datasentinel schedule add --name weekly-audit --type weekly --time 03:00 --day-of-week 4
datasentinel schedule add --name onboarding-sweep --type once --run-at 2026-01-01T00:00:00
datasentinel schedule list
datasentinel schedule remove <schedule-id>
datasentinel schedule run            # foreground loop — the Phase 16 service/unit's entry point
datasentinel schedule run --once     # single check cycle, for cron/Task Scheduler instead of a daemon
```

## Pipeline

`datasentinel_agent.core.pipeline.run_scan()` is the single place every entry
point (today: the CLI; later: the scheduler and backend-triggered scans)
drives a scan through:

```text
discovery -> parsers -> pii + secrets detectors -> risk engine -> SQLite
                                                        ^
                                        optional OpenRouter review (low-confidence
                                        findings only; redacted evidence only;
                                        never blocks the scan if it fails)
```

## Running as a service

Both platforms drive the exact same `SchedulerService.run_forever()` loop
(`datasentinel_agent/scheduler/service.py`) — only the OS-level process
supervision differs.

**Linux (systemd):**
```bash
sudo scripts/install-linux-service.sh [/opt/datasentinel-agent]
systemctl status datasentinel-agent
journalctl -u datasentinel-agent -f
```
Installs a dedicated unprivileged `datasentinel` system account, a hardened
unit (`NoNewPrivileges`, `ProtectSystem=strict`, read-only `/home`), and
handles `SIGTERM` gracefully — see `scripts/datasentinel-agent.service`.

**Windows (Service):** from an elevated PowerShell prompt:
```powershell
scripts\install-windows-service.ps1 -InstallDir "C:\Program Files\DataSentinelAgent"
Get-Service DataSentinelAgent
```
Implemented in `datasentinel_agent/service/windows_service.py` (requires
`pywin32`; the module refuses to import on any non-Windows platform with a
clear error rather than failing on a missing dependency).

Neither service requires Administrator/root to *run* — only to install it.
Scanning itself only needs whatever permissions the configured scan paths
already require (spec section 33).

**Linux only — this has a real consequence for the default `/home` scan
location.** The dedicated `datasentinel` account is deliberately
unprivileged, and a normal user's home directory is `750`
(owner-only) by default. That means an out-of-the-box install will
discover **zero files** under `/home` — confirmed on a real system: the
scan correctly targets `/home`, correctly records a `permission_denied`
`scan_errors` row for each inaccessible home directory, and completes
without crashing, but finds nothing. To actually scan real user data, an
administrator must explicitly grant the service account read access, e.g.
per-user ACLs:
```bash
sudo setfacl -R -m u:datasentinel:rX /home/<user>
```
or add `datasentinel` to each user's primary group if your organization's
permission model allows it. There's no way to satisfy both "least
privilege by default" and "scans real home directories by default"
simultaneously — this documents the tradeoff rather than silently leaving
administrators to discover it via an empty scan report.

## Packaging (PyInstaller)

```bash
pip install pyinstaller
pyinstaller datasentinel-agent.spec --clean
./dist/datasentinel --version
```

Produces a single-file standalone binary (`dist/datasentinel`, ~80MB) with no
Python install required on the target machine. Presidio/spaCy are
deliberately **excluded** from the frozen build (see the spec file's
docstring) — the binary runs in the same "Presidio unavailable, regex-only
detection" mode the agent already supports and is tested against, covering
every required PII/secret category on its own. Deploy a full venv install
instead of the frozen binary if you need Presidio's NLP-based person-name
recognizer. Verified working end-to-end: `config validate` and a real `scan`
against synthetic PII/secrets both produce correct output from the frozen
binary.

A second spec, `datasentinel-agent-service.spec` (Windows-only — freezes
`service_main.py`), produces the Windows Service binary the MSI installer
installs; see `../installer/windows/README.md`. Not buildable/verifiable
outside Windows, so it isn't part of this section's Linux-oriented
walkthrough.

## Archive scanning (optional)

ZIP/TAR/GZIP files are only scanned when the active profile sets
`scan_archives: true` in `config/default.yaml` (the `deep` profile does by
default; `quick`/`standard`/`custom` don't). When enabled, each archive is
extracted into an isolated temp directory with member-count/uncompressed-
size/compression-ratio limits (`parsers/archive_parser.py`, reusing the
same bomb guard as the OOXML formats), path-traversal and symlink members
are skipped rather than extracted, and a member that is itself an archive
is never recursively extracted.

## Centrally-pushed policies

If `DATASENTINEL_BACKEND_URL` and `DATASENTINEL_ENDPOINT_TOKEN` are
configured, each scan fetches this endpoint's org-defined policies from
`GET /api/v1/policies/effective` and layers recognized fields (risk
thresholds, extra exclude paths, per-profile overrides) on top of the local
`config/default.yaml` before running (`sync/policy_sync.py`). Any failure —
backend unset, unreachable, or a malformed policy — falls back to the local
config unchanged; this never blocks a scan.

## Tests

```bash
pytest
```
