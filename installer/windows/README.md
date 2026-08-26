# Windows MSI installer

Builds `DataSentinel-Agent-Setup-x64.msi` (spec sections 8, 20, 44, 61, 64)
from `Product.wxs`, using two PyInstaller-frozen binaries:

- `datasentinel.exe` — the CLI / on-demand-scan binary (`agent/main.py` via
  `agent/datasentinel-agent.spec`).
- `datasentinel-agent-service.exe` — the Windows Service binary
  (`agent/service_main.py` via `agent/datasentinel-agent-service.spec`),
  wrapping `datasentinel_agent.service.windows_service`.

## ⚠️ Build status

This installer source was authored and reviewed in a Linux sandbox with
**no Windows machine, no WiX toolset, and no way to compile or run an
`.msi` available**. It has not been built, installed, or exercised. Treat
`Product.wxs`/`build.ps1` as a carefully-written starting point that still
needs the following before it ships anywhere:

1. Install prerequisites on a real Windows 10/11 dev machine: Python
   matching `agent/pyproject.toml`'s requirement, the agent's dependencies
   (`pip install -e ".[dev]"` plus `pywin32`'s post-install script), and the
   WiX v4 CLI (`dotnet tool install --global wix`, then
   `wix extension add WixToolset.Util.wixext`).
2. Run `.\build.ps1` and fix whatever the WiX compiler flags — component
   GUIDs, directory refs, and custom-action sequencing were written by hand
   against the WiX v4 schema from documentation, not validated by an actual
   `wix build` run.
3. Work through the full test checklist below on a clean VM.

## Prerequisites to actually build

- Windows 10/11 x64
- Python 3.12+ with the agent's dependencies installed, including
  `pywin32` (run `python Scripts/pywin32_postinstall.py -install` once so
  `servicemanager`/`win32service` imports work inside the frozen binary)
- PyInstaller (`pip install pyinstaller`, already an agent dev dependency)
- WiX v4 CLI: `dotnet tool install --global wix`, then
  `wix extension add WixToolset.Util.wixext`

## Building

```powershell
cd installer\windows
.\build.ps1
```

Produces `installer\windows\DataSentinel-Agent-Setup-x64.msi`.

## Installing

Interactive:

```powershell
DataSentinel-Agent-Setup-x64.msi
```

Silent (spec section 8) — two ways to give this machine backend
credentials, pick **one**:

**(a) Pre-registered, one token per device** — an admin registers each
endpoint from the dashboard first and distributes its own token:

```powershell
msiexec /i DataSentinel-Agent-Setup-x64.msi /quiet ^
    ORGANIZATION="Acme Corp" ^
    SERVERURL="https://dashboard.example.com" ^
    ENDPOINTTOKEN="<token from POST /api/v1/endpoints/register>"
```

`SERVERURL`/`ENDPOINTTOKEN` are written directly as this machine's
`DATASENTINEL_BACKEND_URL` / `DATASENTINEL_ENDPOINT_TOKEN` machine
environment variables — the exact names
`agent/datasentinel_agent/config/settings.py` already reads, so nothing
installer-specific exists on the agent side, and no network call happens
at install time.

**(b) Self-service enrollment, one reusable token for a whole fleet** — an
admin creates one enrollment token once
(`POST /api/v1/enrollment-tokens`), then hands the same value to a fleet
deployment tool (SCCM/Intune/GPO) for every machine:

```powershell
msiexec /i DataSentinel-Agent-Setup-x64.msi /quiet ^
    ORGANIZATION="Acme Corp" ^
    SERVERURL="https://dashboard.example.com" ^
    ENROLLMENTTOKEN="<token from POST /api/v1/enrollment-tokens>"
```

This runs `datasentinel.exe enroll` as part of the install (the
`EnrollAgent` custom action in `Product.wxs`), which calls
`POST /api/v1/endpoints/enroll` and writes the **resulting per-endpoint
credential** to `%ProgramData%\DataSentinelAgent\agent.env` — the reusable
enrollment token itself is never written to disk. A
`DATASENTINEL_ENV_FILE` machine environment variable points the agent at
that file regardless of the service process's working directory (see the
comment on `Settings`/`DATASENTINEL_ENV_FILE` in
`agent/datasentinel_agent/config/settings.py` for why a relative `.env`
alone isn't reliable for a Windows Service). Ignored if `ENDPOINTTOKEN` is
also given — (a) always wins.

Neither token is required — installing with neither still succeeds and
produces a fully functional, backend-disconnected agent (local-first
design; see `docs/ARCHITECTURE.md`).

**Known limitation, not yet solved (be aware before relying on this for
compliance-audited installs):** MSI verbose logging
(`msiexec /l*v log.txt`) can capture the resolved command line of a
deferred custom action, including `ENROLLMENTTOKEN`'s/`ENDPOINTTOKEN`'s
value, even with `Hidden="yes" Secure="yes"` set on the property — those
attributes keep a value out of the property-table dump and restricted UI,
not necessarily out of `/l*v` output for the action that consumes it. If
your environment mandates verbose logging for audit reasons, avoid passing
either token on the command line and instead push
`%ProgramData%\DataSentinelAgent\agent.env` directly via your deployment
tool's file-copy step, skipping both properties entirely.

## What the installer does

```text
MSI
 -> Install datasentinel.exe + datasentinel-agent-service.exe
 -> Install config\default.yaml, alembic.ini
 -> Write DATASENTINEL_* machine environment variables
 -> [if ENROLLMENTTOKEN and no ENDPOINTTOKEN] Run `datasentinel.exe enroll`
 -> Run `datasentinel.exe config validate`
 -> Run `datasentinel-agent-service.exe install`
 -> Run `datasentinel-agent-service.exe start`
```

Fresh install, upgrade, and repair are native MSI behavior via the
`MajorUpgrade` element — no custom scripting needed for those three.
Uninstall runs `stop` then `remove` on the service before deleting files.

## Test checklist (spec section 44 — run on a clean Windows VM)

- [ ] Fresh install (interactive)
- [ ] Silent install with `ENDPOINTTOKEN` (flow (a) above)
- [ ] Silent install with `ENROLLMENTTOKEN` (flow (b) above) — confirm
      `datasentinel.exe enroll` actually ran (check for
      `%ProgramData%\DataSentinelAgent\agent.env`), the endpoint appears on
      the dashboard, and `datasentinel.exe status` shows it's connected
- [ ] Both `ENDPOINTTOKEN` and `ENROLLMENTTOKEN` given — confirm (a) wins
      and `EnrollAgent` did not run
- [ ] Invalid/revoked/exhausted `ENROLLMENTTOKEN` — install fails loudly
      (per `EnrollAgent`'s `Return="check"`), not a silent partial install
- [ ] Service registered: `Get-Service DataSentinelAgent` shows it
- [ ] Service running after install
- [ ] Reboot — service starts automatically
- [ ] `datasentinel.exe scan --profile quick` succeeds against the
      installed config
- [ ] Upgrade: build a `1.0.1.0` MSI, install over the `1.0.0.0` install
- [ ] Repair (`msiexec /fa DataSentinel-Agent-Setup-x64.msi`)
- [ ] Uninstall — service stops, is removed, files are gone
- [ ] Invalid `ENDPOINTTOKEN` — agent logs an auth failure, does not crash
- [ ] Server unreachable at install time — install still succeeds (backend
      connectivity is optional, per the agent's offline-first design)
- [ ] A locked file in a scanned directory doesn't abort a scan
- [ ] Antivirus/EDR compatibility spot-check (the frozen binaries are
      unsigned in this build — expect SmartScreen/AV prompts until code
      signing is added; that's a separate, deliberate follow-up, not
      something this installer source addresses)
- [ ] Service crash / restart: `Stop-Service DataSentinelAgent -Force` then
      confirm `Restart-Service` recovers it

None of the above have been exercised — they're the checklist to run, not a
report of what passed.
