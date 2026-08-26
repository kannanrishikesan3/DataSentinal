"""The `DocumentParser` interface every format-specific parser implements.

Every parser must handle malformed files safely: raise `ParserError` (never a
raw library exception) so the registry/orchestrator can always catch a single
exception type and move on to the next file without aborting the scan.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path

from pydantic import BaseModel


class ParserError(Exception):
    """Raised when a file cannot be parsed. Always chains the original
    library exception via `raise ParserError(...) from exc` for debugging,
    but callers only ever need to catch this one type."""


class ExtractedUnit(BaseModel):
    """One addressable chunk of extracted text, with location metadata for
    findings (`page_number` / `line_number` / `sheet_name` on `Finding`)."""

    text: str
    page_number: int | None = None
    line_number: int | None = None
    sheet_name: str | None = None


class DocumentParser(ABC):
    """Spec interface: `can_parse` / `extract`. `extract_units` is an
    additional, richer method most parsers implement directly (giving
    per-page/per-row/per-line location tracking); `extract` then falls back
    to joining those units, satisfying the plain-text interface for free.
    """

    @abstractmethod
    def can_parse(self, file_path: Path) -> bool: ...

    def extract(self, file_path: Path) -> str:
        return "\n".join(unit.text for unit in self.extract_units(file_path))

    def extract_units(self, file_path: Path) -> Iterator[ExtractedUnit]:
        yield ExtractedUnit(text=self.extract(file_path))
