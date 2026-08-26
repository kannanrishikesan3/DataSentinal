# Windows validation (self-contained)

Run the whole stack — backend, dashboard, and agent — on the Windows
laptop itself. No networking between machines, no WSL2 port forwarding.
Two agent paths are given: a **quick path** (run from Python source, no
installer, ~10 minutes) to validate scanning/detection actually works on
Windows, and the **full MSI path** (needs the WiX toolchain) for testing
the real installer end to end.

This mirrors the Linux validation already done, adapted for things that
are genuinely different on Windows: default scan locations, path syntax,
and service management commands.

## 0. Get the code onto the Windows laptop

Any of these work — pick whichever is easiest for you:
- `git clone` the repo if it's in a reachable remote
- Copy the whole `DataSentinal/` folder over a network share / USB drive
- `git clone` isn't required just to *run* it — a plain copy is fine since
  nothing here needs git history

## 1. Prerequisites

- **Python 3.12+** from [python.org](https://www.python.org/downloads/) —
  check "Add python.exe to PATH" during install
- **Node.js 20+** from [nodejs.org](https://nodejs.org/)
- (Full MSI path only) **WiX v4 CLI**: `dotnet tool install --global wix`,
  then `wix extension add WixToolset.Util.wixext` (needs the .NET SDK)

Verify:
```powershell
python --version
node --version
npm --version
```

## 2. Backend (PowerShell)

```powershell
cd DataSentinal\backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .

# SQLite for this validation — no PostgreSQL needed
$env:DATASENTINEL_DATABASE_URL = "sqlite:///$PWD\validation.db"
$env:DATASENTINEL_SECRET_KEY = (python -c "import secrets; print(secrets.token_urlsafe(48))")
$env:DATASENTINEL_CORS_ORIGINS = "http://127.0.0.1:4173"

alembic upgrade head

# Create the first org/admin (no signup UI by design)
python scripts\create_org_admin.py --org "Windows Validation" --email admin@validation.example.com --password "correct horse battery staple"

# Start the API (leave this window open)
uvicorn datasentinel_backend.main:app --host 127.0.0.1 --port 8000
```

Verify in a second PowerShell window:
```powershell
curl http://127.0.0.1:8000/health
```
Expect `{"status":"ok",...}`.

## 3. Frontend (new PowerShell window)

```powershell
cd DataSentinal\frontend
npm ci
$env:VITE_API_BASE_URL = "http://127.0.0.1:8000"
npm run build
npm run preview -- --port 4173 --host 127.0.0.1
```

Open **http://127.0.0.1:4173** in a browser, log in with
`admin@validation.example.com` / `correct horse battery staple`. Dashboard
will be empty until the agent (below) reports a scan.

## 4a. Agent — quick path (no installer, new PowerShell window)

```powershell
cd DataSentinal\agent
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .

datasentinel --version
datasentinel config validate
```

Then register an endpoint from the dashboard's API to get a real token
(there's no "Register endpoint" UI on the login screen — do it via
`curl`/PowerShell using the admin session, or just skip backend upload for
now and validate scanning alone first):

```powershell
# Get an admin token
$login = Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/auth/login -Method Post -ContentType "application/json" -Body '{"email":"admin@validation.example.com","password":"correct horse battery staple"}'
$token = $login.access_token

# Register this machine as an endpoint
$reg = Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/endpoints/register -Method Post -Headers @{Authorization="Bearer $token"} -ContentType "application/json" -Body (@{name=$env:COMPUTERNAME; hostname=$env:COMPUTERNAME; os="windows"; os_version="11"; agent_version="1.0.0"} | ConvertTo-Json)
$endpointToken = $reg.api_token

$env:DATASENTINEL_BACKEND_URL = "http://127.0.0.1:8000"
$env:DATASENTINEL_ENDPOINT_TOKEN = $endpointToken
```

**Create synthetic test data** (same pattern as the Linux validation — never real personal data):
```powershell
mkdir C:\Temp\datasentinel-test
@"
Name: Test User
Email: test.user@example.com
Phone: 9876543210
"@ | Out-File C:\Temp\datasentinel-test\test.txt

@"
aws_access_key_id = AKIAABCD1234EFGH5678
aws_secret_access_key = wJalrXUtnFEMIsyntheticKEYbPxRfiCYEXAMPLEKEY
"@ | Out-File C:\Temp\datasentinel-test\secrets.txt
```

**Run a scan against just that folder first** (safe, bounded):
```powershell
datasentinel scan --path C:\Temp\datasentinel-test --profile quick --no-ai
```
Expect PII findings (email/phone) and a CRITICAL secret finding (AWS
credentials), same shape as the Linux results.

**Then try a real default-location scan** (spec section 15 — Windows
defaults to `%USERPROFILE%\Documents`, `Downloads`, `Desktop`, `Pictures`,
and `C:\Users\Public`; never `C:\Windows`/`Program Files` unless you add
them):
```powershell
datasentinel scan --profile quick --no-ai
```
This touches your **real files** in those folders — same caveat as the
Linux `/home` test. Unlike Linux, Windows won't hit the least-privilege
permission wall we found there (you're running as your own user account
here, which already owns `%USERPROFILE%`), so this should discover real
files. Check the output for `Files discovered` > 0.

Check it actually reported in:
```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/dashboard/overview -Headers @{Authorization="Bearer $token"}
```
Then refresh the dashboard in your browser — the new endpoint and findings
should appear.

## 4b. Agent — full MSI path (needs WiX)

See `installer/windows/README.md` for the complete build + install +
test-checklist process. Point `SERVERURL` at `http://127.0.0.1:8000` and
use the `$endpointToken` from step 4a's registration call. This is the
one that's genuinely never been built or run anywhere — if you get this
far, you'll be the first real signal on whether `Product.wxs` actually
compiles.

## 5. Things worth checking specifically on Windows

- **Service management** (if you did the MSI path):
  ```powershell
  Get-Service "DataSentinelAgent"
  Restart-Service "DataSentinelAgent"
  ```
- **Long paths / Unicode paths** — create a deeply nested folder or a
  filename with non-ASCII characters under your test directory and confirm
  the scan doesn't choke on it.
- **Locked files** — open a file in another program (e.g. Excel with a
  `.xlsx` open) and confirm the scan records a permission/lock error and
  continues rather than crashing.
- **Windows Defender / AV** — if you build the MSI, expect a SmartScreen
  or Defender prompt on the unsigned binaries; that's expected (no code
  signing yet), not a functional bug.
- **`config validate`** should show `Presidio: unavailable (regex-only
  detection)` unless you've separately installed Presidio's spaCy model —
  this is the same graceful-degradation behavior as Linux, not
  Windows-specific.

## 6. Cleanup

```powershell
Remove-Item -Recurse -Force C:\Temp\datasentinel-test
# Ctrl+C the uvicorn and npm preview windows
# If you did the MSI path: uninstall via Settings > Apps, or `msiexec /x DataSentinel-Agent-Setup-x64.msi`
```

## 7. Report back

Whatever you find, the same categories matter as the Linux report:
version/config-validate output, scan summary (discovered/scanned/skipped/
errors), whether findings appear correctly redacted in the dashboard, and
anything that crashes, hangs, or looks visually broken. Screenshots are
easy to grab yourself directly (Win+Shift+S) since you have a real screen
on that machine — no Playwright needed for this one.
