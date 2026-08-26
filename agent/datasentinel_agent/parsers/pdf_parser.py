"""PDF parser (PyMuPDF / fitz) — page-addressable."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from datasentinel_agent.parsers.base import DocumentParser, ExtractedUnit, ParserError

_MAX_PAGES = 5000  # guard against pathological page counts


class PDFParser(DocumentParser):
    def can_parse(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".pdf"

    def extract_units(self, file_path: Path) -> Iterator[ExtractedUnit]:
        try:
            import fitz  # PyMuPDF
        except ImportError as exc:
            raise ParserError("PyMuPDF is not installed") from exc

        try:
            doc = fitz.open(str(file_path))
        except Exception as exc:
            raise ParserError(f"Failed to open PDF {file_path}: {exc}") from exc

        try:
            for page_number, page in enumerate(doc, start=1):
                if page_number > _MAX_PAGES:
                    break
                try:
                    text = page.get_text()
                except Exception as exc:
                    raise ParserError(f"Failed to extract PDF page {page_number} of {file_path}: {exc}") from exc
                if text and text.strip():
                    yield ExtractedUnit(text=text, page_number=page_number)
        finally:
            doc.close()
