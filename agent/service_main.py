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
"""

import platform

if __name__ == "__main__":
    if platform.system() != "Windows":
        raise SystemExit("datasentinel-agent-service is Windows-only. Use scripts/datasentinel-agent.service (systemd) on Linux.")

    import win32serviceutil

    from datasentinel_agent.service.windows_service import DataSentinelWindowsService

    win32serviceutil.HandleCommandLine(DataSentinelWindowsService)
