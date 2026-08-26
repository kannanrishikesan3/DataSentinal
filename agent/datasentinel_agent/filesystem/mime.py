"""MIME type detection. Prefers `python-magic` (libmagic content sniffing) but
degrades to the stdlib `mimetypes` extension-based guess when libmagic isn't
available on the platform — detection must never hard-fail because of this.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

try:
    import magic as _magic  # type: ignore[import-untyped]

    _HAS_MAGIC = True
except (ImportError, OSError):
    # ImportError: package not installed. OSError: libmagic shared lib missing
    # even though python-magic itself is installed (common on minimal images).
    _magic = None
    _HAS_MAGIC = False


def detect_mime_type(path: Path) -> str | None:
    if _HAS_MAGIC:
        try:
            mime = _magic.from_file(str(path), mime=True)
            if mime:
                return mime
        except Exception:
            pass  # fall through to the extension-based guess

    guessed, _ = mimetypes.guess_type(path.name)
    return guessed
