"""Phase 2 tests: safe recursive walk — filters, excludes, depth, symlink
safety, and permission-error handling."""

import os

import pytest

from datasentinel_agent.discovery.config import DiscoveryConfig
from datasentinel_agent.discovery.scanner import DiscoveryScanner
from datasentinel_agent.discovery.walker import walk


def _make_tree(root):
    (root / "docs").mkdir()
    (root / "docs" / "a.txt").write_text("alpha")
    (root / "docs" / "b.csv").write_text("1,2,3")
    (root / "docs" / "skip_me.exe").write_bytes(b"\x00\x01")
    (root / "excluded").mkdir()
    (root / "excluded" / "c.txt").write_text("should not appear")
    (root / "nested" / "deep" / "deeper").mkdir(parents=True)
    (root / "nested" / "deep" / "deeper" / "d.txt").write_text("deep file")
    return root


def test_walk_applies_extension_filter(tmp_path):
    _make_tree(tmp_path)
    config = DiscoveryConfig(include_paths=[tmp_path], extension_filter={".txt", ".csv"})
    found = {c.path.name for c in walk(config)}
    assert found == {"a.txt", "b.csv", "c.txt", "d.txt"}
    assert "skip_me.exe" not in found


def test_walk_applies_exclude_paths(tmp_path):
    _make_tree(tmp_path)
    config = DiscoveryConfig(
        include_paths=[tmp_path],
        exclude_paths=[tmp_path / "excluded"],
        extension_filter={".txt", ".csv"},
    )
    found = {c.path.name for c in walk(config)}
    assert "c.txt" not in found
    assert "a.txt" in found


def test_walk_applies_max_depth(tmp_path):
    _make_tree(tmp_path)
    # depth 0 = include root itself; nested/deep/deeper/d.txt is 3 levels down
    config = DiscoveryConfig(include_paths=[tmp_path], extension_filter={".txt"}, max_depth=1)
    found = {c.path.name for c in walk(config)}
    assert "d.txt" not in found


def test_walk_applies_max_file_size(tmp_path):
    (tmp_path / "small.txt").write_text("a")
    (tmp_path / "large.txt").write_text("a" * 1000)
    config = DiscoveryConfig(
        include_paths=[tmp_path], extension_filter={".txt"}, max_file_size_bytes=10
    )
    found = {c.path.name for c in walk(config)}
    assert found == {"small.txt"}


def test_walk_does_not_follow_symlinks_by_default(tmp_path, tmp_path_factory):
    # The target lives OUTSIDE the scanned tree so the only way to reach it
    # is through the symlink — proving the walker really doesn't follow it,
    # rather than just finding the file via some other real path.
    outside = tmp_path_factory.mktemp("outside_target")
    (outside / "linked.txt").write_text("data")

    scanned_root = tmp_path / "scanned"
    scanned_root.mkdir()
    link = scanned_root / "link_dir"
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported in this environment")

    config = DiscoveryConfig(include_paths=[scanned_root], extension_filter={".txt"}, follow_symlinks=False)
    found = {c.path.name for c in walk(config)}
    assert "linked.txt" not in found


def test_walk_prevents_symlink_cycles_when_following(tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    (a / "file.txt").write_text("x")
    loop_link = a / "loop"
    try:
        os.symlink(tmp_path, loop_link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported in this environment")

    config = DiscoveryConfig(include_paths=[tmp_path], extension_filter={".txt"}, follow_symlinks=True)
    # Must terminate (no infinite recursion) and still find the real file.
    found = {c.path.name for c in walk(config)}
    assert "file.txt" in found


def test_walk_symlink_outside_root_skipped_even_when_following(tmp_path, tmp_path_factory):
    # A symlink whose target resolves outside every include_path's real tree
    # must never be followed, even with follow_symlinks=True — otherwise an
    # attacker-controlled symlink could pull arbitrary filesystem content
    # into the scan.
    outside = tmp_path_factory.mktemp("outside_target2")
    (outside / "linked.txt").write_text("data")

    scanned_root = tmp_path / "scanned"
    scanned_root.mkdir()
    link = scanned_root / "link.txt"
    try:
        os.symlink(outside / "linked.txt", link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported in this environment")

    errors = []
    config = DiscoveryConfig(include_paths=[scanned_root], extension_filter={".txt"}, follow_symlinks=True)
    found = {c.path.name for c in walk(config, on_error=errors.append)}

    assert "link.txt" not in found
    assert any(e.error_type == "symlink_escapes_root" for e in errors)


def test_walk_symlink_to_special_file_skipped_when_following(tmp_path):
    # A symlink pointing at a device/socket/FIFO must be excluded based on
    # the *resolved target's* type, not the symlink's own (irrelevant) type.
    if not hasattr(os, "mkfifo"):
        pytest.skip("mkfifo not available on this platform")

    fifo_path = tmp_path / "myfifo"
    try:
        os.mkfifo(fifo_path)
    except OSError:
        pytest.skip("mkfifo not supported on this filesystem")

    link = tmp_path / "link_to_fifo.txt"
    os.symlink(fifo_path, link)

    config = DiscoveryConfig(include_paths=[tmp_path], extension_filter={".txt"}, follow_symlinks=True)
    found = {c.path.name for c in walk(config)}

    assert "link_to_fifo.txt" not in found


def test_walk_permission_denied_is_recorded_not_raised(tmp_path):
    protected = tmp_path / "protected"
    protected.mkdir()
    (protected / "secret.txt").write_text("nope")
    protected.chmod(0o000)

    errors = []
    config = DiscoveryConfig(include_paths=[tmp_path], extension_filter={".txt"})
    try:
        found = list(walk(config, on_error=errors.append))
    finally:
        protected.chmod(0o755)  # allow pytest tmp cleanup

    assert any(e.error_type == "permission_denied" for e in errors)
    # The scan must not have crashed — it's still a valid (possibly empty) list.
    assert isinstance(found, list)


def test_discovery_scanner_collects_metadata_for_all_files(tmp_path):
    _make_tree(tmp_path)
    config = DiscoveryConfig(include_paths=[tmp_path], extension_filter={".txt", ".csv"}, max_workers=2)
    result = DiscoveryScanner(config).run()

    assert result.files_scanned == 4
    assert result.files_discovered == 4
    assert not result.errors
    hashes = {f.filename: f.sha256 for f in result.files}
    assert hashes["a.txt"] is not None


def test_discovery_scanner_respects_cancellation(tmp_path):
    for i in range(20):
        (tmp_path / f"f{i}.txt").write_text("x" * 100)
    config = DiscoveryConfig(include_paths=[tmp_path], extension_filter={".txt"}, max_workers=2)
    scanner = DiscoveryScanner(config)
    scanner.cancel()  # cancel before running
    result = scanner.run()
    assert result.cancelled is True
