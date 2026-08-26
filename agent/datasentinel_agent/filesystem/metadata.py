"""Per-file metadata collection: size, timestamps, owner, permissions, MIME
type, and streaming SHA-256 hashing. Never loads a whole file into memory.
"""

from __future__ import annotations

import hashlib
import platform
import stat as stat_module
from datetime import datetime, timezone
from pathlib import Path

from datasentinel_agent.core.schema import FileRecord
from datasentinel_agent.filesystem.mime import detect_mime_type

HASH_CHUNK_SIZE = 1024 * 1024  # 1 MiB — bounded memory regardless of file size
_IS_WINDOWS = platform.system() == "Windows"


def sha256_file(path: Path, chunk_size: int = HASH_CHUNK_SIZE) -> str:
    """Stream a file through SHA-256 in fixed-size chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _permissions_string(mode: int) -> str:
    if _IS_WINDOWS:
        # POSIX permission bits aren't meaningful on Windows; ACLs are a
        # separate, much larger concern out of scope for Phase 3. Report the
        # coarse read-only bit instead, which stat() does surface reliably.
        return "readonly" if not (mode & stat_module.S_IWRITE) else "read-write"
    return stat_module.filemode(mode)


def _owner_name(path: Path, uid: int) -> str | None:
    if _IS_WINDOWS:
        return None  # requires pywin32 / win32security; not attempted here
    try:
        import pwd

        return pwd.getpwuid(uid).pw_name
    except (ImportError, KeyError, OSError):
        return str(uid)


def collect_metadata(
    path: Path,
    *,
    compute_hash: bool = True,
    detect_mime: bool = True,
) -> FileRecord:
    """Collect metadata for a single file. Raises OSError/PermissionError to
    the caller — callers are expected to catch and record these as scan
    errors rather than aborting the whole scan.
    """
    st = path.stat()

    created_at = getattr(st, "st_birthtime", None)  # macOS/BSD only
    if created_at is None:
        # Linux has no reliable creation time via stat(); ctime is metadata-
        # change time, not creation time, but it's the closest cross-platform
        # approximation stdlib stat() offers without extra syscalls.
        created_at = st.st_ctime

    return FileRecord(
        path=str(path),
        filename=path.name,
        extension=path.suffix.lower(),
        mime_type=detect_mime_type(path) if detect_mime else None,
        size_bytes=st.st_size,
        created_at=datetime.fromtimestamp(created_at, tz=timezone.utc),
        modified_at=datetime.fromtimestamp(st.st_mtime, tz=timezone.utc),
        owner=_owner_name(path, st.st_uid) if hasattr(st, "st_uid") else None,
        permissions=_permissions_string(st.st_mode),
        sha256=sha256_file(path) if compute_hash else None,
    )
