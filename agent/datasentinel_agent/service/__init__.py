"""OS service integration (spec section 33/34): Windows Service and Linux
systemd both drive the exact same `SchedulerService.run_forever()` loop used
by `datasentinel schedule run` — only the process-supervision glue differs.
`windows_service` is Windows-only (guarded; importing it elsewhere raises a
clear error instead of failing on a missing `pywin32`). The systemd unit
(`scripts/datasentinel-agent.service`) needs no Python-side wrapper — it
just execs the CLI directly.
"""
