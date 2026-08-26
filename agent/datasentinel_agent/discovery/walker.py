"""Safe recursive filesystem walker.

Design constraints (from the spec):
- Do not follow symbolic links blindly.
- Prevent infinite recursion (symlink loops, bind-mount cycles).
- Apply include/exclude paths, extension filter, size limit, and max depth.
- A permission error on one file/dir must never abort the walk.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from datasentinel_agent.core.schema import ScanError
from datasentinel_agent.discovery.config import DiscoveryConfig

# Special/pseudo filesystem entries that must never be treated as regular
# files even if an administrator's include_paths accidentally covers them.
_SKIP_SPECIAL_TYPES = True


@dataclass(frozen=True)
class Candidate:
    """A file that passed all discovery-time filters and is ready for
    metadata collection / content extraction."""

    path: Path
    size_bytes: int


def _is_excluded(path: Path, exclude_roots: list[Path]) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    for root in exclude_roots:
        try:
            root_resolved = root.resolve()
        except OSError:
            root_resolved = root
        if resolved == root_resolved or root_resolved in resolved.parents:
            return True
    return False


def _is_special_file(entry: os.DirEntry, *, follow_symlinks: bool = False) -> bool:
    import stat as stat_module

    try:
        st = entry.stat(follow_symlinks=False)
    except OSError:
        return True

    if stat_module.S_ISLNK(st.st_mode) and follow_symlinks:
        # When we're going to follow this symlink, what matters is the type
        # of the *resolved target* — a symlink pointing at a device/socket/
        # FIFO must still be excluded even though the link itself is a
        # perfectly ordinary symlink.
        try:
            target_st = entry.stat(follow_symlinks=True)
        except OSError:
            return True
        return not (stat_module.S_ISREG(target_st.st_mode) or stat_module.S_ISDIR(target_st.st_mode))

    return not (
        stat_module.S_ISREG(st.st_mode) or stat_module.S_ISDIR(st.st_mode) or stat_module.S_ISLNK(st.st_mode)
    )


def _resolve_roots(paths: list[Path]) -> list[Path]:
    resolved = []
    for path in paths:
        try:
            resolved.append(path.resolve())
        except OSError:
            resolved.append(path)
    return resolved


def _is_within_roots(resolved_target: Path, resolved_roots: list[Path]) -> bool:
    for root in resolved_roots:
        try:
            if resolved_target == root or resolved_target.is_relative_to(root):
                return True
        except OSError:
            continue
    return False


def walk(
    config: DiscoveryConfig,
    *,
    on_error: Callable[[ScanError], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> Iterator[Candidate]:
    """Yield `Candidate` files under `config.include_paths`, honoring excludes,
    depth, extension, and size filters. Symlinked directories are never
    descended into unless `follow_symlinks=True`, and even then a
    visited-real-path set prevents cycles.
    """
    visited_real_dirs: set[str] = set()
    resolved_roots = _resolve_roots(config.include_paths)

    def record_error(path: Path, error_type: str, message: str) -> None:
        if on_error:
            from datetime import datetime, timezone

            on_error(
                ScanError(
                    path=str(path),
                    error_type=error_type,
                    message=message,
                    occurred_at=datetime.now(timezone.utc),
                )
            )

    def walk_dir(directory: Path, depth: int) -> Iterator[Candidate]:
        if should_stop and should_stop():
            return
        if depth > config.max_depth:
            return
        if _is_excluded(directory, config.exclude_paths):
            return

        try:
            real_dir = str(directory.resolve())
        except OSError as exc:
            record_error(directory, "resolve_error", str(exc))
            return

        if real_dir in visited_real_dirs:
            return  # cycle guard (symlink loop / bind mount)
        visited_real_dirs.add(real_dir)

        try:
            entries = list(os.scandir(directory))
        except PermissionError as exc:
            record_error(directory, "permission_denied", str(exc))
            return
        except OSError as exc:
            record_error(directory, "os_error", str(exc))
            return

        for entry in entries:
            if should_stop and should_stop():
                return

            if _SKIP_SPECIAL_TYPES and _is_special_file(entry, follow_symlinks=config.follow_symlinks):
                continue

            entry_path = Path(entry.path)

            if entry.is_symlink():
                if not config.follow_symlinks:
                    continue
                # Even when following symlinks, never follow one that points
                # outside all include_paths' real trees, or one that resolves
                # to something already visited (loop).
                try:
                    resolved_target = entry_path.resolve()
                    if not resolved_target.exists():
                        continue
                except OSError:
                    continue
                if not _is_within_roots(resolved_target, resolved_roots):
                    record_error(
                        entry_path,
                        "symlink_escapes_root",
                        f"Symlink resolves outside all scanned roots: {resolved_target}",
                    )
                    continue

            try:
                is_dir = entry.is_dir(follow_symlinks=config.follow_symlinks)
            except OSError as exc:
                record_error(entry_path, "stat_error", str(exc))
                continue

            if is_dir:
                yield from walk_dir(entry_path, depth + 1)
                continue

            if _is_excluded(entry_path, config.exclude_paths):
                continue

            if config.extension_filter is not None and entry_path.suffix.lower() not in config.extension_filter:
                continue

            try:
                size = entry.stat(follow_symlinks=config.follow_symlinks).st_size
            except OSError as exc:
                record_error(entry_path, "stat_error", str(exc))
                continue

            if size > config.max_file_size_bytes:
                continue

            yield Candidate(path=entry_path, size_bytes=size)

    for root in config.include_paths:
        if not root.exists():
            record_error(root, "not_found", "include path does not exist")
            continue
        if root.is_file():
            if not _is_excluded(root, config.exclude_paths):
                try:
                    size = root.stat().st_size
                except OSError as exc:
                    record_error(root, "stat_error", str(exc))
                    continue
                if size <= config.max_file_size_bytes:
                    yield Candidate(path=root, size_bytes=size)
            continue
        yield from walk_dir(root, depth=0)
