"""XLSX parser (openpyxl) — sheet- and row-addressable."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from datasentinel_agent.config.scan_config import load_scan_config
from datasentinel_agent.parsers.archive_guard import check_zip_safety
from datasentinel_agent.parsers.base import DocumentParser, ExtractedUnit, ParserError

_MAX_ROWS_PER_SHEET = 200_000  # guard against pathologically large sheets


class XLSXParser(DocumentParser):
    def can_parse(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".xlsx"

    def extract_units(self, file_path: Path) -> Iterator[ExtractedUnit]:
        limits = load_scan_config().archive_limits
        check_zip_safety(
            file_path,
            max_members=limits.max_members,
            max_uncompressed_bytes=limits.max_uncompressed_bytes,
            max_ratio=limits.max_ratio,
        )

        try:
            import openpyxl
        except ImportError as exc:
            raise ParserError("openpyxl is not installed") from exc

        try:
            # read_only + data_only keep memory bounded and skip formula text
            workbook = openpyxl.load_workbook(str(file_path), read_only=True, data_only=True)
        except Exception as exc:
            raise ParserError(f"Failed to open XLSX {file_path}: {exc}") from exc

        try:
            for sheet in workbook.worksheets:
                for row_number, row in enumerate(sheet.iter_rows(values_only=True), start=1):
                    if row_number > _MAX_ROWS_PER_SHEET:
                        break
                    values = [str(cell) for cell in row if cell is not None and str(cell).strip()]
                    if values:
                        yield ExtractedUnit(
                            text=", ".join(values),
                            line_number=row_number,
                            sheet_name=sheet.title,
                        )
        finally:
            workbook.close()
