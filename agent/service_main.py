"""Windows Service entry point (also the PyInstaller build target for
`datasentinel-agent-service.spec`) — separate from `main.py` (the CLI/
on-demand-scan entry point) because pywin32's `HandleCommandLine` expects to
own process argv for its own install/start/stop/remove/debug verbs, which
would conflict with the CLI's own `click` argument parsing if both lived in
one binary.

Usage (from an elevated prompt, same verbs as `python -m
datasentinel_agent.service.windows_service`):

    datasentinel-agent-service.exe install
    datasentinel-agent-service.exe start
    datasentinel-agent-service.exe stop
    datasentinel-agent-service.exe remove

When Windows SCM launches this EXE it passes no arguments. That path must
call StartServiceCtrlDispatcher immediately — HandleCommandLine() with an
empty argv does not, which is error 1053.
"""

import platform
import sys

if __name__ == "__main__":
    if platform.system() != "Windows":
        raise SystemExit("datasentinel-agent-service is Windows-only. Use scripts/datasentinel-agent.service (systemd) on Linux.")

    import servicemanager
    import win32serviceutil

    from datasentinel_agent.service.windows_service import DataSentinelWindowsService

    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(DataSentinelWindowsService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(DataSentinelWindowsService)
