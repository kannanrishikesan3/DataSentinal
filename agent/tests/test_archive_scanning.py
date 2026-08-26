"""Phase (archive scanning, spec section 43) tests: ZIP/TAR/GZIP as
scannable file types, opt-in per profile, safe against bombs, path
traversal, and recursive archives."""

import gzip
import tarfile
import zipfile

import pytest

from datasentinel_agent.discovery.config import DiscoveryConfig
from datasentinel_agent.parsers.registry import safe_extract


def _write_zip(path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in members.items():
            zf.writestr(name, data)


def test_zip_members_are_extracted_and_scanned(tmp_path):
    f = tmp_path / "records.zip"
    _write_zip(f, {"note.txt": b"Email: alex.synthetic@example.com"})

    units, error = safe_extract(f)
    assert error is None
    assert any("alex.synthetic@example.com" in u.text for u in units)
    assert any("note.txt" in u.text for u in units)  # member path surfaced as context


def test_tar_gz_members_are_extracted_and_scanned(tmp_path):
    inner = tmp_path / "note.txt"
    inner.write_text("SSN: 123-45-6789")
    f = tmp_path / "records.tar.gz"
    with tarfile.open(f, "w:gz") as archive:
        archive.add(inner, arcname="note.txt")

    units, error = safe_extract(f)
    assert error is None
    assert any("123-45-6789" in u.text for u in units)


def test_plain_gzip_member_is_extracted_and_scanned(tmp_path):
    f = tmp_path / "note.txt.gz"
    with gzip.open(f, "wb") as fh:
        fh.write(b"phone: 9876543210")

    units, error = safe_extract(f)
    assert error is None
    assert any("9876543210" in u.text for u in units)


def test_zip_path_traversal_members_are_skipped_not_extracted(tmp_path):
    f = tmp_path / "evil.zip"
    _write_zip(f, {"../../etc/passwd": b"pwned", "../escape.txt": b"pwned too"})

    units, error = safe_extract(f)
    assert error is None
    assert units == []
    # Nothing was written outside the isolated temp extraction directory.
    assert not (tmp_path.parent.parent / "etc" / "passwd").exists()


def test_zip_bomb_inside_a_zip_archive_is_rejected(tmp_path):
    f = tmp_path / "bomb.zip"
    _write_zip(f, {"bomb.bin": b"\x00" * (5 * 1024 * 1024)})

    units, error = safe_extract(f)
    assert units == []
    assert error is not None


def test_tar_bomb_is_rejected_on_uncompressed_size(tmp_path, monkeypatch):
    from datasentinel_agent.parsers import archive_parser as archive_parser_module
    from datasentinel_agent.config.scan_config import load_scan_config

    huge = tmp_path / "huge.bin"
    huge.write_bytes(b"\x00" * (2 * 1024 * 1024))
    f = tmp_path / "bomb.tar.gz"
    with tarfile.open(f, "w:gz") as archive:
        archive.add(huge, arcname="huge.bin")

    # A real deployment's default limit (500MB) wouldn't reject a 2MB
    # payload, so exercise the guard directly with a tight limit — proving
    # the size check itself works without relying on real gigabyte-scale
    # fixtures in the test suite.
    tight_config = load_scan_config()
    tight_config.archive_limits.max_uncompressed_bytes = 1024

    def fake_load_scan_config():
        return tight_config

    monkeypatch.setattr(archive_parser_module, "load_scan_config", fake_load_scan_config)

    units, error = safe_extract(f)
    assert units == []
    assert error is not None


def test_corrupted_zip_never_raises(tmp_path):
    f = tmp_path / "corrupt.zip"
    f.write_bytes(b"PK\x03\x04 not a real zip")
    units, error = safe_extract(f)
    assert units == []
    assert error is not None


def test_corrupted_tar_never_raises(tmp_path):
    f = tmp_path / "corrupt.tar"
    f.write_bytes(b"not a real tar file at all" * 20)
    units, error = safe_extract(f)
    assert units == []
    assert error is not None


def test_nested_archive_member_is_not_recursively_extracted(tmp_path):
    inner_zip = tmp_path / "inner.zip"
    _write_zip(inner_zip, {"secret.txt": b"AKIAABCD1234EFGH5678"})

    outer = tmp_path / "outer.zip"
    with zipfile.ZipFile(outer, "w") as zf:
        zf.write(inner_zip, arcname="inner.zip")

    units, error = safe_extract(outer)
    assert error is None
    # The inner archive is skipped, not recursed into — its content must
    # never surface.
    assert all("AKIAABCD1234EFGH5678" not in u.text for u in units)


def test_archive_extension_only_discovered_when_profile_enables_scan_archives(tmp_path):
    (tmp_path / "records.zip").write_bytes(b"PK\x03\x04")
    (tmp_path / "notes.txt").write_text("hello")

    standard_config = DiscoveryConfig.from_profile("standard", include_paths=[tmp_path])
    assert ".zip" not in standard_config.extension_filter

    deep_config = DiscoveryConfig.from_profile("deep", include_paths=[tmp_path])
    assert ".zip" in deep_config.extension_filter


def test_scan_pipeline_survives_a_zip_bomb_in_the_directory(tmp_path):
    from datasentinel_agent.core.enums import ScanStatus
    from datasentinel_agent.core.pipeline import ScanOptions, run_scan
    from datasentinel_agent.storage.database import init_db, make_engine, make_session_factory

    _write_zip(tmp_path / "bomb.zip", {"bomb.bin": b"\x00" * (5 * 1024 * 1024)})
    (tmp_path / "notes.txt").write_text("Email: still.works@example.com\n")

    engine = make_engine(tmp_path / "agent_test.db")
    init_db(engine)
    session_factory = make_session_factory(engine)

    options = ScanOptions(profile="deep", paths=[tmp_path], use_presidio=False)
    summary = run_scan(options, session_factory)

    assert summary.status == ScanStatus.COMPLETED
    assert summary.files_skipped >= 1
    assert summary.pii_findings >= 1
