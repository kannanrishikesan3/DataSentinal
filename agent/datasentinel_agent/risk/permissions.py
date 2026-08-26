"""Heuristic for over-permissive file permissions (world-writable/readable)
— another risk engine input. POSIX only; Windows ACLs are out of scope here
(`filesystem.metadata` reports a coarse readonly/read-write string on
Windows, which this treats as never "world"-risky by itself)."""

from __future__ import annotations

_POSIX_MODE_LENGTH = 10  # e.g. "-rw-r--r--" from stat.filemode()


def is_world_writable(permissions: str | None) -> bool:
    if not permissions or len(permissions) != _POSIX_MODE_LENGTH:
        return False
    return permissions[8] == "w"


def is_world_readable(permissions: str | None) -> bool:
    if not permissions or len(permissions) != _POSIX_MODE_LENGTH:
        return False
    return permissions[7] == "r"


def is_over_permissive(permissions: str | None) -> bool:
    # World-*writable* is the genuinely elevated signal (anyone can modify
    # the file). World-*readable* alone is the standard default (644) for
    # most files on a typical system — flagging it would make this
    # essentially always true and useless as a risk signal.
    return is_world_writable(permissions)
