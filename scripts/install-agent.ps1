# SQ1 Security — install DataSentinel Agent on a Windows laptop.
#
# The enrollment token is created on the SERVER, not invented here.
# After the dashboard is up:
#   1. Open http://192.168.8.99:5173
#   2. Log in as admin
#   3. Endpoints → Create enrollment token
#   4. Copy the string that starts with dset_
#   5. Run this script as Administrator:
#
#        .\scripts\install-agent.ps1 -EnrollmentToken "dset_...."
#
param(
    [Parameter(Mandatory = $true)]
    [string]$EnrollmentToken,

    [string]$ServerUrl = "http://192.168.8.99:8000",
    [string]$Organization = "SQ1 Security",
    [string]$MsiPath = ""
)

$ErrorActionPreference = "Stop"

if ($EnrollmentToken -notlike "dset_*") {
    Write-Error "That does not look like an enrollment token. It must start with dset_ and come from the dashboard (or ./server.sh token). Do not use the endpoint token from agent\.env (dsat_)."
}

if (-not $MsiPath) {
    $MsiPath = Join-Path $PSScriptRoot "..\installer\windows\DataSentinel-Agent-Setup-x64.msi"
}

if (-not (Test-Path $MsiPath)) {
    Write-Error "MSI not found: $MsiPath. Copy DataSentinel-Agent-Setup-x64.msi next to this script or pass -MsiPath."
}

Write-Host "Installing DataSentinel Agent"
Write-Host "  Organization: $Organization"
Write-Host "  Server:       $ServerUrl"
Write-Host "  MSI:          $MsiPath"

$msi = (Resolve-Path $MsiPath).Path
$args = @(
    "/i", $msi,
    "/quiet",
    "ORGANIZATION=$Organization",
    "SERVERURL=$ServerUrl",
    "ENROLLMENTTOKEN=$EnrollmentToken"
)

$proc = Start-Process -FilePath "msiexec.exe" -ArgumentList $args -Wait -PassThru
if ($proc.ExitCode -ne 0) {
    Write-Error "msiexec failed with exit code $($proc.ExitCode). Confirm the laptop can reach $ServerUrl (API port 8000, not dashboard 5173)."
}

Write-Host "Install finished. Check: Get-Service DataSentinelAgent"
