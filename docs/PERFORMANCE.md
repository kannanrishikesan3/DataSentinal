# Performance testing (spec section 46)

Run with `agent/scripts/perf_test.py` — generates a synthetic dataset of N
files (a rotating mix of PII-bearing text, AWS-credential-bearing text, and
ordinary non-sensitive text, spread across subdirectories of 500 files each)
and runs a real scan through the full pipeline (discovery → parsing → regex
PII/secret detection → risk scoring → SQLite storage), measuring wall-clock
duration, peak RSS (sampled every 200ms on a background thread, not just a
before/after snapshot), and process CPU%.

```bash
cd agent && source .venv/bin/activate
python scripts/perf_test.py --files 1000 --out /tmp/perf-1k --profile quick
python scripts/perf_test.py --files 10000 --out /tmp/perf-10k --profile quick
python scripts/perf_test.py --files 100000 --out /tmp/perf-100k --profile quick
```

## Results

Measured on a 12-core / 7.6GiB container (shared host — not a dedicated
benchmarking machine, so treat absolute numbers as indicative of *scaling
behavior*, not a guaranteed SLA). `use_presidio=False` (regex+validator
detection only) for all three runs — Presidio's spaCy NLP pass is
substantially slower per file and is exercised separately in
`agent/tests/test_pii_presidio.py`, not at this scale.

| Files   | Duration | Throughput      | Peak RSS  | SQLite DB size |
|---------|----------|------------------|-----------|----------------|
| 1,000   | 5.5s     | 182.5 files/sec  | 81.3 MiB  | 0.89 MiB       |
| 10,000  | 54.7s    | 182.8 files/sec  | 117.6 MiB | 8.44 MiB       |
| 100,000 | 500.9s   | 199.7 files/sec  | 484.2 MiB | 85.94 MiB      |

Findings: half the files carry one PII match, half carry an AWS-credential
secret, so PII/secret counts scale ~1:1 with file count throughout.

## Reading these numbers

- **Throughput is stable** (~183–200 files/sec) from 1k to 100k files —
  no evidence of the pipeline degrading superlinearly as the dataset grows;
  the discovery walk and per-file parse/detect/store loop are all O(1) per
  file, not O(n) in the number of files already processed.
- **Memory grows sublinearly, not unbounded.** 100x more files (1k → 100k)
  used ~6x more peak RSS (81 → 484 MiB), not 100x — consistent with the
  streaming design (SQLAlchemy session batches are flushed continuously
  rather than the whole scan's findings living in memory), though
  `all_findings`/`all_errors` in `core/pipeline.py` do still accumulate as
  Python lists for the whole scan's duration, which is the ceiling this
  would eventually hit on a truly enormous single scan (see "Not tested"
  below).
- **Disk usage** (SQLite DB) scales roughly linearly with findings, as
  expected — no unexpected growth.
- **Network usage**: 0 in all three runs — no backend was configured, so
  this only measures the fully local scan-and-store path. Upload cost
  (`agent/datasentinel_agent/sync/scan_uploader.py`) is one HTTP POST per
  scan with the same JSON shape already covered in
  `agent/tests/test_scan_uploader.py`; it wasn't separately load-tested
  against a real backend at 100k-finding scale.

## Not tested (environment/scope limits)

- **CPU isolation**: this container shares its host with other work, so the
  reported CPU% is directional, not a clean single-tenant measurement.
- **Very large individual files** (spec asks for "large files" alongside
  "many small files") — not separately benchmarked here; the streaming
  SHA-256 and per-format parser bounds are unit-tested
  (`agent/tests/test_filesystem.py`, `test_parsers*.py`) but not measured
  for wall-clock/memory at, say, a multi-GB single file.
- **Concurrent multi-worker scaling** — `perf_test.py` accepts
  `--workers` but this run used each profile's configured default; the
  effect of worker count on throughput wasn't isolated as its own variable.
- **A true memory ceiling under sustained accumulation** — the
  `all_findings`/`all_errors` in-memory lists mentioned above would keep
  growing on a scan with millions of findings in one run; 100k files here
  produced ~100k findings without issue, but this wasn't pushed further to
  find where memory growth stops being sublinear.
