"""Plain-text parsers: .txt, .log, .md — line-addressable."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from datasentinel_agent.parsers.base import DocumentParser, ExtractedUnit, ParserError

TEXT_EXTENSIONS = {".txt", ".log", ".md"}


class TextParser(DocumentParser):
    def can_parse(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in TEXT_EXTENSIONS

    def extract_units(self, file_path: Path) -> Iterator[ExtractedUnit]:
        try:
            with file_path.open("r", encoding="utf-8", errors="replace") as fh:
                for line_number, line in enumerate(fh, start=1):
                    stripped = line.rstrip("\n")
                    if stripped:
                        yield ExtractedUnit(text=stripped, line_number=line_number)
        except OSError as exc:
            raise ParserError(f"Failed to read text file {file_path}: {exc}") from exc
