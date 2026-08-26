"""CSV parser — row-addressable. A malformed row is skipped, not fatal."""

from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path

from datasentinel_agent.parsers.base import DocumentParser, ExtractedUnit, ParserError

# Large-field guard: without a cap, a maliciously crafted CSV with one huge
# field can force the csv module to buffer unbounded memory.
_MAX_FIELD_SIZE = 1024 * 1024


class CSVParser(DocumentParser):
    def can_parse(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".csv"

    def extract_units(self, file_path: Path) -> Iterator[ExtractedUnit]:
        previous_limit = csv.field_size_limit()
        csv.field_size_limit(_MAX_FIELD_SIZE)
        try:
            with file_path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
                reader = csv.reader(fh)
                for line_number, row in enumerate(reader, start=1):
                    if not row:
                        continue
                    text = ", ".join(cell for cell in row if cell)
                    if text:
                        yield ExtractedUnit(text=text, line_number=line_number)
        except (OSError, csv.Error) as exc:
            raise ParserError(f"Failed to read CSV file {file_path}: {exc}") from exc
        finally:
            csv.field_size_limit(previous_limit)
