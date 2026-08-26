#!/usr/bin/env python3
"""Performance testing harness (spec section 46): generates a synthetic
dataset of N files with a realistic mix of PII/secret content, runs a real
scan through the full pipeline, and reports CPU/memory/duration/disk usage.

Not a pytest test — durations and memory ceilines are host-dependent, so
this is a manual/CI-scheduled tool, not a pass/fail gate. Run it directly:

    python scripts/perf_test.py --files 1000 --out /tmp/perf-1k

Writes a small markdown report to <out>/report.md and prints a summary.
"""

from __future__ import annotations

import argparse
import random
import shutil
import string
import sys
import threading
import time
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datasentinel_agent.core.pipeline import ScanOptions, run_scan  # noqa: E402
from datasentinel_agent.storage.database import init_db, make_engine, make_session_factory  # noqa: E402

_SYNTHETIC_EMAILS = [f"synthetic.user{i}@example.com" for i in range(200)]
_SYNTHETIC_PHONES = [f"98765{i:05d}" for i in range(200)]
_SYNTHETIC_SECRET = "AKIAABCD1234EFGH5678"


def _random_text_content(index: int) -> str:
    kind = index % 4
    if kind == 0:
        return f"Employee record #{index}\nEmail: {random.choice(_SYNTHETIC_EMAILS)}\nPhone: {random.choice(_SYNTHETIC_PHONES)}\n"
    if kind == 1:
        return f"aws_access_key_id = {_SYNTHETIC_SECRET}\naws_secret_access_key = {''.join(random.choices(string.ascii_letters + string.digits, k=40))}\n"
    if kind == 2:
        return "Nothing sensitive here, just ordinary log output.\n" + ("line filler\n" * 5)
    return f"Notes for project {index}: no PII, just internal planning text.\n"


def generate_dataset(root: Path, num_files: int) -> None:
    root.mkdir(parents=True, exist_ok=True)
    files_per_dir = 500
    for i in range(num_files):
        subdir = root / f"batch_{i // files_per_dir}"
        subdir.mkdir(exist_ok=True)
        (subdir / f"file_{i}.txt").write_text(_random_text_content(i))


class _MemorySampler:
    """Polls this process's RSS on a background thread so we capture the
    peak during the scan, not just before/after snapshots."""

    def __init__(self, interval: float = 0.2):
        self._interval = interval
        self._proc = psutil.Process()
        self._peak_rss = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                rss = self._proc.memory_info().rss
                self._peak_rss = max(self._peak_rss, rss)
            except Exception:
                pass
            self._stop.wait(self._interval)

    def __enter__(self) -> "_MemorySampler":
        self._thread.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._stop.set()
        self._thread.join(timeout=2)

    @property
    def peak_rss_mb(self) -> float:
        return self._peak_rss / (1024 * 1024)


def _dir_size_bytes(root: Path) -> int:
    return sum(f.stat().st_size for f in root.rglob("*") if f.is_file())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", type=int, default=1000, help="number of synthetic files to generate")
    parser.add_argument("--out", type=Path, default=Path("/tmp/datasentinel-perf"), help="working directory")
    parser.add_argument("--profile", default="quick", choices=["quick", "standard", "deep"])
    parser.add_argument("--presidio", action="store_true", help="use Presidio instead of the regex-only detector")
    parser.add_argument("--workers", type=int, default=None, help="override worker count for this run")
    args = parser.parse_args()

    out_dir = args.out
    if out_dir.exists():
        shutil.rmtree(out_dir)
    dataset_dir = out_dir / "dataset"

    print(f"Generating {args.files} synthetic files under {dataset_dir} ...")
    gen_start = time.monotonic()
    generate_dataset(dataset_dir, args.files)
    gen_duration = time.monotonic() - gen_start
    dataset_bytes = _dir_size_bytes(dataset_dir)

    db_path = out_dir / "agent.db"
    engine = make_engine(db_path)
    init_db(engine)
    session_factory = make_session_factory(engine)

    options = ScanOptions(profile=args.profile, paths=[dataset_dir], use_presidio=args.presidio)

    process = psutil.Process()
    process.cpu_percent(interval=None)  # prime the counter

    print(f"Running scan (profile={args.profile}, presidio={args.presidio}) ...")
    scan_start = time.monotonic()
    with _MemorySampler() as sampler:
        summary = run_scan(options, session_factory)
    scan_duration = time.monotonic() - scan_start
    cpu_percent = process.cpu_percent(interval=None)

    db_bytes = db_path.stat().st_size if db_path.exists() else 0

    report_lines = [
        "# DataSentinel performance test",
        "",
        f"- Files generated: {args.files}",
        f"- Dataset generation time: {gen_duration:.2f}s",
        f"- Dataset size on disk: {dataset_bytes / (1024 * 1024):.2f} MiB",
        f"- Scan profile: {args.profile} (presidio={args.presidio}, workers override={args.workers})",
        f"- Scan status: {summary.status.value}",
        f"- Files discovered: {summary.files_discovered}",
        f"- Files scanned: {summary.files_scanned}",
        f"- Files skipped: {summary.files_skipped}",
        f"- PII findings: {summary.pii_findings}",
        f"- Secret findings: {summary.secret_findings}",
        f"- Scan wall-clock duration: {scan_duration:.2f}s",
        f"- Throughput: {summary.files_scanned / scan_duration:.1f} files/sec" if scan_duration > 0 else "- Throughput: n/a",
        f"- Peak RSS during scan: {sampler.peak_rss_mb:.1f} MiB",
        f"- Process CPU% (avg over scan window): {cpu_percent:.1f}%",
        f"- Local SQLite DB size after scan: {db_bytes / (1024 * 1024):.2f} MiB",
        "- Network usage: 0 (no backend configured for this run — local-only scan)",
        "",
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "report.md"
    report_path.write_text("\n".join(report_lines))

    print("\n".join(report_lines))
    print(f"Report written to {report_path}")


if __name__ == "__main__":
    main()
