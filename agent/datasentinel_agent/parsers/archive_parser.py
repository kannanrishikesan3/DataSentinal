"""Archive scanning (spec section 43): ZIP/TAR/GZIP as scannable file types.

Off by default (see `scan.profiles.*.scan_archives` in `config/default.yaml`
and `discovery.config.DiscoveryConfig.from_profile` — the `deep` profile
turns it on; discovery simply never hands this parser a `.zip`/`.tar`/`.gz`
file otherwise). When enabled, each archive is extracted into an isolated
temporary directory, each member is scanned with the ordinary parser
registry, and the directory is removed before `extract_units` returns.

Safety rules, all enforced before any member's bytes hit disk:
  - member count / total uncompressed size / compression ratio limits,
    reusing the same `archive_limits` config as the OOXML zip-bomb guard.
  - path-traversal and absolute-path members are skipped, not extracted.
  - symlink/hardlink members are skipped entirely (never followed).
  - a member that is itself an archive is never recursively extracted —
    one level of archive scanning only, per spec's "protect against
    recursive archives".
"""

from __future__ import annotations

import gzip
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from datasentinel_agent.config.scan_config import load_scan_config
from datasentinel_agent.parsers.archive_guard import ArchiveBombError, check_zip_safety
from datasentinel_agent.parsers.base import DocumentParser, ExtractedUnit, ParserError

ARCHIVE_EXTENSIONS = {".zip", ".tar", ".gz", ".tgz"}

_CHUNK_SIZE = 1024 * 1024


def _is_safe_member_path(name: str) -> PurePosixPath | None:
    normalized = PurePosixPath(name)
    if normalized.is_absolute() or ".." in normalized.parts:
        return None
    return normalized


def _extract_zip(file_path: Path, dest_dir: Path, limits) -> list[Path]:
    check_zip_safety(
        file_path,
        max_members=limits.max_members,
        max_uncompressed_bytes=limits.max_uncompressed_bytes,
        max_ratio=limits.max_ratio,
    )
    extracted: list[Path] = []
    try:
        with zipfile.ZipFile(file_path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                safe_name = _is_safe_member_path(info.filename)
                if safe_name is None:
                    continue
                target = dest_dir / safe_name
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst, _CHUNK_SIZE)
                extracted.append(target)
    except (zipfile.BadZipFile, OSError) as exc:
        raise ParserError(f"Failed to open ZIP {file_path}: {exc}") from exc
    return extracted


def _extract_tar(file_path: Path, dest_dir: Path, limits) -> list[Path]:
    try:
        with tarfile.open(file_path, mode="r:*") as archive:
            members = archive.getmembers()

            file_members = [m for m in members if m.isfile()]
            if len(file_members) > limits.max_members:
                raise ArchiveBombError(
                    f"{file_path}: archive has {len(file_members)} members "
                    f"(limit {limits.max_members}) — refusing to decompress"
                )
            total_uncompressed = sum(m.size for m in file_members)
            if total_uncompressed > limits.max_uncompressed_bytes:
                raise ArchiveBombError(
                    f"{file_path}: archive claims {total_uncompressed} uncompressed bytes "
                    f"(limit {limits.max_uncompressed_bytes}) — refusing to decompress"
                )
            compressed_size = file_path.stat().st_size or 1
            ratio = total_uncompressed / compressed_size
            if ratio > limits.max_ratio:
                raise ArchiveBombError(
                    f"{file_path}: compression ratio {ratio:.1f}:1 exceeds limit "
                    f"{limits.max_ratio}:1 — refusing to decompress"
                )

            extracted: list[Path] = []
            for member in file_members:
                if member.issym() or member.islnk():
                    continue
                safe_name = _is_safe_member_path(member.name)
                if safe_name is None:
                    continue
                target = dest_dir / safe_name
                target.parent.mkdir(parents=True, exist_ok=True)
                src = archive.extractfile(member)
                if src is None:
                    continue
                with src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst, _CHUNK_SIZE)
                extracted.append(target)
    except tarfile.TarError as exc:
        raise ParserError(f"Failed to open TAR {file_path}: {exc}") from exc
    except OSError as exc:
        raise ParserError(f"Failed to open TAR {file_path}: {exc}") from exc
    return extracted


def _extract_gzip(file_path: Path, dest_dir: Path, limits) -> list[Path]:
    # A plain single-file .gz (not .tar.gz — that's handled by _extract_tar
    # via tarfile's transparent gzip support). Strip the .gz suffix for the
    # inner filename so the ordinary parser registry can dispatch on it.
    inner_name = file_path.stem or "extracted"
    target = dest_dir / inner_name
    total = 0
    try:
        with gzip.open(file_path, "rb") as src, target.open("wb") as dst:
            while True:
                chunk = src.read(_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > limits.max_uncompressed_bytes:
                    raise ArchiveBombError(
                        f"{file_path}: gzip stream exceeds {limits.max_uncompressed_bytes} "
                        "uncompressed bytes — refusing to decompress"
                    )
                dst.write(chunk)
    except OSError as exc:
        raise ParserError(f"Failed to open GZIP {file_path}: {exc}") from exc
    return [target]


def _is_tar_like(file_path: Path) -> bool:
    name = file_path.name.lower()
    return name.endswith(".tar") or name.endswith(".tar.gz") or name.endswith(".tgz")


class ArchiveParser(DocumentParser):
    def can_parse(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in ARCHIVE_EXTENSIONS

    def extract_units(self, file_path: Path):
        # Deferred import: the registry imports this module to register
        # ArchiveParser, so importing registry back at module load time
        # would be circular.
        from datasentinel_agent.parsers.registry import get_parser

        limits = load_scan_config().archive_limits
        dest_dir = Path(tempfile.mkdtemp(prefix="datasentinel-archive-"))
        try:
            if file_path.suffix.lower() == ".zip":
                extracted = _extract_zip(file_path, dest_dir, limits)
            elif _is_tar_like(file_path):
                extracted = _extract_tar(file_path, dest_dir, limits)
            else:
                extracted = _extract_gzip(file_path, dest_dir, limits)

            for member_path in extracted:
                if not member_path.is_file():
                    continue
                parser = get_parser(member_path)
                if parser is None or isinstance(parser, ArchiveParser):
                    # Unsupported member, or a nested archive — never
                    # recurse into archives-within-archives.
                    continue
                try:
                    member_units = list(parser.extract_units(member_path))
                except ParserError:
                    continue
                except Exception:  # noqa: BLE001 - one bad member must not abort the archive
                    continue

                member_label = member_path.relative_to(dest_dir).as_posix()
                for unit in member_units:
                    yield ExtractedUnit(
                        text=f"[{member_label}] {unit.text}",
                        page_number=unit.page_number,
                        line_number=unit.line_number,
                        sheet_name=unit.sheet_name,
                    )
        finally:
            shutil.rmtree(dest_dir, ignore_errors=True)
