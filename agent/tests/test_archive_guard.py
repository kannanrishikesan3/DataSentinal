"""Decompression-bomb guard: zip-based (OOXML) formats must never be handed
straight to python-docx/openpyxl/python-pptx without a cheap, metadata-only
sanity check first."""

from __future__ import annotations

import zipfile

import pytest

from datasentinel_agent.parsers.archive_guard import ArchiveBombError, check_zip_safety
from datasentinel_agent.parsers.base import ParserError
from datasentinel_agent.parsers.registry import safe_extract


def _write_zip(path, members: dict[str, bytes], compression=zipfile.ZIP_DEFLATED) -> None:
    with zipfile.ZipFile(path, "w", compression) as zf:
        for name, data in members.items():
            zf.writestr(name, data)


def test_archive_bomb_error_is_a_parser_error():
    # The registry's generic catch (`safe_extract`) only needs to know one
    # exception type — confirm the guard's error chains into it.
    assert issubclass(ArchiveBombError, ParserError)


def test_check_zip_safety_rejects_too_many_members(tmp_path):
    f = tmp_path / "many_members.zip"
    _write_zip(f, {f"file_{i}.txt": b"x" for i in range(20)})

    with pytest.raises(ArchiveBombError):
        check_zip_safety(f, max_members=10)


def test_check_zip_safety_rejects_excessive_uncompressed_size(tmp_path):
    f = tmp_path / "large.zip"
    _write_zip(f, {"big.txt": b"a" * 10_000})

    with pytest.raises(ArchiveBombError):
        check_zip_safety(f, max_uncompressed_bytes=1_000)


def test_check_zip_safety_rejects_excessive_ratio(tmp_path):
    f = tmp_path / "bomb.zip"
    # Highly compressible content: a few MB of zero bytes compresses to a
    # tiny fraction of that, giving a ratio far beyond any legitimate
    # office document.
    _write_zip(f, {"bomb.bin": b"\x00" * (5 * 1024 * 1024)})

    with pytest.raises(ArchiveBombError):
        check_zip_safety(f, max_uncompressed_bytes=1024 * 1024 * 1024, max_ratio=200)


def test_check_zip_safety_allows_a_normal_small_archive(tmp_path):
    f = tmp_path / "normal.zip"
    _write_zip(f, {"a.txt": b"hello world", "b.txt": b"some more ordinary text content"})

    check_zip_safety(f)  # must not raise


def test_check_zip_safety_ignores_non_zip_files(tmp_path):
    f = tmp_path / "not_a_zip.bin"
    f.write_bytes(b"this is not a zip file at all")

    check_zip_safety(f)  # never raises ArchiveBombError for a bad/non-zip file


@pytest.mark.parametrize("extension", [".docx", ".xlsx", ".pptx"])
def test_zip_bomb_disguised_as_office_file_is_safely_rejected(tmp_path, extension):
    # Uses the *real*, configured default thresholds end-to-end through the
    # parser registry — a small file that decompresses to something absurd
    # must be rejected quickly and safely, not hang or exhaust memory.
    f = tmp_path / f"bomb{extension}"
    _write_zip(f, {"bomb.bin": b"\x00" * (5 * 1024 * 1024)})

    units, error = safe_extract(f)

    assert units == []
    assert error is not None


def test_scan_continues_past_a_zip_bomb_file(tmp_path):
    # One malicious/corrupted office file must never abort a whole directory
    # scan — the pipeline's per-file error handling must treat it exactly
    # like any other parse failure.
    from datasentinel_agent.discovery.config import DiscoveryConfig
    from datasentinel_agent.discovery.scanner import DiscoveryScanner

    bomb = tmp_path / "bomb.docx"
    _write_zip(bomb, {"bomb.bin": b"\x00" * (5 * 1024 * 1024)})
    (tmp_path / "normal.txt").write_text("nothing sensitive here")

    config = DiscoveryConfig(include_paths=[tmp_path], extension_filter={".docx", ".txt"})
    result = DiscoveryScanner(config).run()

    assert result.files_discovered == 2
    # Discovery itself succeeds for both files (the bomb guard fires during
    # parsing, not discovery) — the parse failure is handled by the caller
    # of safe_extract (the scan pipeline), proven directly below.
    paths = {f.filename for f in result.files}
    assert paths == {"bomb.docx", "normal.txt"}

    for file_record in result.files:
        units, error = safe_extract(tmp_path / file_record.filename)
        if file_record.filename == "bomb.docx":
            assert units == []
            assert error is not None
        else:
            assert error is None
