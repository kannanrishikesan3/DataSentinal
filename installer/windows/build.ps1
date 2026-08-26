<#
.SYNOPSIS
    Builds DataSentinel-Agent-Setup-x64.msi from source.

.DESCRIPTION
    Three stages: (1) PyInstaller-freeze the CLI binary, (2) PyInstaller-
    freeze the Windows Service binary, (3) compile the WiX installer
    referencing both. Run from an elevated PowerShell prompt on Windows
    with Python, the agent's dependencies, and the WiX v4 CLI (`dotnet tool
    install --global wix`) already installed.

.NOTES
    Not run/verified in this repository's build environment (Linux, no
    Windows/WiX toolchain available) — see README.md in this directory for
    the manual test checklist to run on a real Windows VM before shipping
    the resulting .msi anywhere.
#>
param(
    [string]$AgentDir = (Resolve-Path "$PSScriptRoot\..\..\agent"),
    [string]$OutDir = "$PSScriptRoot\build"
)

$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host "==> Freezing CLI binary (datasentinel.exe)..."
Push-Location $AgentDir
try {
    pyinstaller datasentinel-agent.spec --clean --distpath "$OutDir" --workpath "$OutDir\pyinstaller-work"
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed building the CLI binary" }
} finally {
    Pop-Location
}

Write-Host "==> Freezing Windows Service onedir (build\datasentinel-agent-service\)..."
Push-Location $AgentDir
try {
    pyinstaller datasentinel-agent-service.spec --clean --distpath "$OutDir" --workpath "$OutDir\pyinstaller-work"
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed building the service binary" }
} finally {
    Pop-Location
}

Write-Host "==> Compiling the MSI with WiX..."
Push-Location $PSScriptRoot
try {
    wix build Product.wxs -arch x64 -ext WixToolset.Util.wixext -ext WixToolset.UI.wixext -out DataSentinel-Agent-Setup-x64.msi
    if ($LASTEXITCODE -ne 0) { throw "wix build failed" }
} finally {
    Pop-Location
}

Write-Host "==> Done: $PSScriptRoot\DataSentinel-Agent-Setup-x64.msi"
Write-Host "Run through installer/windows/README.md's test checklist before shipping this."
