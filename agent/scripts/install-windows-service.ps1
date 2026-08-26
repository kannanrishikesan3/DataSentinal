<#
.SYNOPSIS
    Installs and starts the DataSentinel agent as a Windows Service.

.DESCRIPTION
    Requires the agent to already be installed (pip install -e ".[dev]" into
    a venv, or a PyInstaller build) with pywin32's post-install script run
    (`python Scripts/pywin32_postinstall.py -install`) so servicemanager.exe
    is registered.

.PARAMETER InstallDir
    Path to the agent installation (containing .venv\Scripts\python.exe).
    Defaults to C:\Program Files\DataSentinelAgent.

.NOTES
    Run this script from an elevated (Administrator) PowerShell prompt —
    installing a service requires elevation. The service itself does not
    require Administrator to run; it scans user-writable default locations
    under whichever account it's configured to run as (LocalSystem by
    default, like most Windows services, or a dedicated low-privilege
    account for tighter least-privilege deployments).
#>
param(
    [string]$InstallDir = "C:\Program Files\DataSentinelAgent"
)

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "This script must be run as Administrator."
    exit 1
}

$PythonExe = Join-Path $InstallDir ".venv\Scripts\python.exe"
$DataDir = Join-Path $env:ProgramData "DataSentinelAgent"

if (-not (Test-Path $PythonExe)) {
    Write-Error "Agent not found at $PythonExe. Install it first (see agent\README.md)."
    exit 1
}

New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

[System.Environment]::SetEnvironmentVariable("DATASENTINEL_DB_PATH", (Join-Path $DataDir "datasentinel.db"), "Machine")
[System.Environment]::SetEnvironmentVariable("DATASENTINEL_SCHEDULES_PATH", (Join-Path $DataDir "schedules.json"), "Machine")

Write-Host "Applying local database migrations..."
& $PythonExe -m alembic -c (Join-Path $InstallDir "alembic.ini") upgrade head

Write-Host "Registering the Windows Service..."
& $PythonExe -m datasentinel_agent.service.windows_service install

Write-Host "Starting the service..."
& $PythonExe -m datasentinel_agent.service.windows_service start

Write-Host "Installed. Check status with: Get-Service DataSentinelAgent"
Write-Host "Manage schedules with: $PythonExe -m datasentinel_agent.cli.main schedule add ..."
