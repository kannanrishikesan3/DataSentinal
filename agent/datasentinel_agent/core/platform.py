"""Platform detection: the one place the agent decides whether it's running
on Windows, Linux, or macOS.

Replaces the ad-hoc `platform.system() == "Windows"` binary ternaries that
used to live separately in `discovery/config.py` and `cli/main.py`'s
`enroll()` — both only ever distinguished Windows from "everything else"
(i.e. they'd have misreported macOS as Linux). Every other OS check in the
codebase (`filesystem/metadata.py`'s `_IS_WINDOWS`,
`service/windows_service.py`'s Windows-only guard,
`core/pipeline.py`'s `sys.platform == "win32"` RLIMIT_AS guard) is a
Windows-vs-not-Windows check where macOS is correctly meant to fall into
the "not Windows" branch already, so those are deliberately left alone.
"""

from __future__ import annotations

import platform as _platform
from enum import StrEnum


class Platform(StrEnum):
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"


def detect_platform() -> Platform:
    system = _platform.system()
    if system == "Windows":
        return Platform.WINDOWS
    if system == "Darwin":
        return Platform.MACOS
    return Platform.LINUX
