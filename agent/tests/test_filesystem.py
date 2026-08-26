"""Phase 3 tests: file metadata collection and streaming SHA-256 hashing."""

import hashlib

from datasentinel_agent.filesystem.metadata import collect_metadata, sha256_file


def test_sha256_matches_hashlib(tmp_path):
    f = tmp_path / "sample.txt"
    content = b"DataSentinel synthetic test content\n" * 1000
    f.write_bytes(content)

    assert sha256_file(f) == hashlib.sha256(content).hexdigest()


def test_sha256_streams_in_chunks_not_all_at_once(tmp_path):
    f = tmp_path / "big.bin"
    f.write_bytes(b"x" * (5 * 1024 * 1024))
    # A tiny chunk size forces many reads; result must still be correct.
    assert sha256_file(f, chunk_size=17) == hashlib.sha256(b"x" * (5 * 1024 * 1024)).hexdigest()


def test_collect_metadata_basic_fields(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("hello world")

    record = collect_metadata(f)

    assert record.filename == "notes.txt"
    assert record.extension == ".txt"
    assert record.size_bytes == len("hello world")
    assert record.sha256 == hashlib.sha256(b"hello world").hexdigest()
    assert record.modified_at is not None
    assert record.permissions is not None


def test_collect_metadata_without_hash(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("hello")
    record = collect_metadata(f, compute_hash=False)
    assert record.sha256 is None
