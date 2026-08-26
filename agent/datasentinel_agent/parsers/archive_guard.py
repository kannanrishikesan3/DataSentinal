"""Zip/OOXML decompression-bomb guard.

.docx/.xlsx/.pptx are OOXML — zip archives handed straight to python-docx /
openpyxl / python-pptx. A crafted, small zip can claim (accurately, in its
own central directory metadata — this is not something extraction can
"validate away") to contain an enormous number of members or to decompress
to gigabytes of content, exhausting memory or CPU before the underlying
library ever gets a chance to reject it.

`check_zip_safety` performs a cheap, metadata-only pass over the zip's
central directory (`ZipFile.infolist()` never decompresses any member data)
and refuses to hand the file to a parser if it looks like a bomb. Call it at
the very start of a parser's `extract`/`extract_units`, before the archive
is opened by the real library.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from datasentinel_agent.parsers.base import ParserError

# Conservative defaults, overridable via `config/default.yaml`'s
# `archive_limits:` block (see `config.scan_config.ArchiveLimitsConfig`).
DEFAULT_MAX_MEMBERS = 10_000
DEFAULT_MAX_UNCOMPRESSED_BYTES = 500 * 1024 * 1024
DEFAULT_MAX_RATIO = 200


class ArchiveBombError(ParserError):
    """Raised when a zip-based (OOXML) file looks like a decompression bomb
    — too many members, too much claimed uncompressed content, or an
    implausible overall compression ratio.

    Subclasses `ParserError` so every existing catch site (notably
    `parsers.registry.safe_extract`) already handles it correctly: the file
    is skipped, an error is recorded, and the scan continues.
    """


def check_zip_safety(
    file_path: Path,
    *,
    max_members: int = DEFAULT_MAX_MEMBERS,
    max_uncompressed_bytes: int = DEFAULT_MAX_UNCOMPRESSED_BYTES,
    max_ratio: int = DEFAULT_MAX_RATIO,
) -> None:
    """Raise `ArchiveBombError` if the zip at `file_path` looks unsafe to
    decompress in full. Deliberately does *not* raise on a file that simply
    isn't a valid zip at all (`BadZipFile`) or can't be opened (`OSError`)
    — that's left for the caller's real parser to reject with its own,
    more specific error; this guard's only job is bomb detection.
    """
    try:
        with zipfile.ZipFile(file_path) as archive:
            infolist = archive.infolist()

            member_count = len(infolist)
            if member_count > max_members:
                raise ArchiveBombError(
                    f"{file_path}: archive has {member_count} members "
                    f"(limit {max_members}) — refusing to decompress"
                )

            total_uncompressed = sum(info.file_size for info in infolist)
            total_compressed = sum(info.compress_size for info in infolist)

            if total_uncompressed > max_uncompressed_bytes:
                raise ArchiveBombError(
                    f"{file_path}: archive claims {total_uncompressed} uncompressed bytes "
                    f"(limit {max_uncompressed_bytes}) — refusing to decompress"
                )

            if total_compressed > 0:
                ratio = total_uncompressed / total_compressed
                if ratio > max_ratio:
                    raise ArchiveBombError(
                        f"{file_path}: compression ratio {ratio:.1f}:1 exceeds limit "
                        f"{max_ratio}:1 — refusing to decompress"
                    )
    except zipfile.BadZipFile:
        return
    except OSError:
        return
