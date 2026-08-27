"""Windows Service wrapper around the scheduler loop (spec section 33).

Windows-only — requires `pywin32` (declared as a Windows-only dependency in
pyproject.toml). Register/manage it with:

    python -m datasentinel_agent.service.windows_service install
    python -m datasentinel_agent.service.windows_service start
    python -m datasentinel_agent.service.windows_service stop
    python -m datasentinel_agent.service.windows_service remove

Does not require Administrator privileges to *run* (it scans the default
per-user locations under the service account's own permissions); installing/
removing the service itself does, same as any Windows service.

Heavy agent imports (scheduler, SQLAlchemy, parsers) are deferred until
SvcDoRun so the process can answer the Service Control Manager within
Windows' start timeout. Pulling that graph at module import time is what
caused error 1053 with the frozen EXE.
"""

from __future__ import annotations

import platform

if platform.system() != "Windows":
    raise ImportError(
        "datasentinel_agent.service.windows_service is Windows-only. "
        "On Linux, use the systemd unit in scripts/datasentinel-agent.service instead."
    )

import servicemanager  # type: ignore[import-not-found]
import win32service  # type: ignore[import-not-found]
import win32serviceutil  # type: ignore[import-not-found]


class DataSentinelWindowsService(win32serviceutil.ServiceFramework):
    _svc_name_ = "DataSentinelAgent"
    _svc_display_name_ = "DataSentinel Endpoint Agent"
    _svc_description_ = "Scheduled endpoint data risk discovery scans (PII/secret detection)."

    def __init__(self, args):
        super().__init__(args)
        self._scheduler = None

    def SvcStop(self) -> None:
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        if self._scheduler is not None:
            self._scheduler.stop()  # unblocks SvcDoRun's run_forever() promptly

    def SvcDoRun(self) -> None:
        # Tell SCM we are running *before* importing the rest of the agent.
        # The frozen process otherwise spends the start timeout loading numpy,
        # lxml, parsers, etc. and Windows kills it with error 1053.
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )

        from datasentinel_agent.config.settings import get_settings
        from datasentinel_agent.logging.redaction_filter import redact
        from datasentinel_agent.scheduler.service import SchedulerService
        from datasentinel_agent.storage.database import init_db, make_engine, make_session_factory

        settings = get_settings()
        engine = make_engine(settings.db_path)
        init_db(engine)
        session_factory = make_session_factory(engine)

        def on_event(name: str, data: dict) -> None:
            # `data` can include a raw exception message from a scan
            # failure (a file path, PII, or secret-shaped text), so this
            # must go through the same redaction the rest of the codebase
            # applies via `get_logger()`'s RedactionFilter — never straight
            # to the Windows event log unscrubbed.
            servicemanager.LogInfoMsg(redact(f"DataSentinel [{name}] {data}"))

        self._scheduler = SchedulerService(session_factory, on_event=on_event)
        try:
            self._scheduler.run_forever()
        except Exception:
            servicemanager.LogErrorMsg("DataSentinel scheduler loop crashed; service is stopping.")
            raise

        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STOPPED,
            (self._svc_name_, ""),
        )


def main() -> None:
    win32serviceutil.HandleCommandLine(DataSentinelWindowsService)


if __name__ == "__main__":
    main()
