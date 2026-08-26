"""Parser registry and the safe extraction entry point used by the rest of
the pipeline. One corrupted/unsupported file must never abort a scan.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from datasentinel_agent.parsers.archive_parser import ARCHIVE_EXTENSIONS, ArchiveParser
from datasentinel_agent.parsers.base import DocumentParser, ExtractedUnit, ParserError
from datasentinel_agent.parsers.csv_parser import CSVParser
from datasentinel_agent.parsers.docx_parser import DocxParser
from datasentinel_agent.parsers.json_parser import JSONParser
from datasentinel_agent.parsers.pdf_parser import PDFParser
from datasentinel_agent.parsers.pptx_parser import PPTXParser
from datasentinel_agent.parsers.text_parser import TextParser
from datasentinel_agent.parsers.xlsx_parser import XLSXParser
from datasentinel_agent.parsers.xml_parser import XMLParser

_PARSERS: list[DocumentParser] = [
    TextParser(),
    CSVParser(),
    JSONParser(),
    XMLParser(),
    PDFParser(),
    DocxParser(),
    XLSXParser(),
    PPTXParser(),
    ArchiveParser(),
]

SUPPORTED_EXTENSIONS = {".txt", ".csv", ".json", ".xml", ".log", ".md", ".pdf", ".docx", ".xlsx", ".pptx"} | ARCHIVE_EXTENSIONS


def get_parser(file_path: Path) -> DocumentParser | None:
    for parser in _PARSERS:
        if parser.can_parse(file_path):
            return parser
    return None


def safe_extract(file_path: Path) -> tuple[list[ExtractedUnit], ParserError | None]:
    """Never raises. Returns (units, error) — units is empty on failure."""
    parser = get_parser(file_path)
    if parser is None:
        return [], ParserError(f"No parser registered for {file_path.suffix}")

    try:
        units = list(parser.extract_units(file_path))
    except ParserError as exc:
        return [], exc
    except Exception as exc:  # noqa: BLE001 - a parser bug must not crash the scan
        return [], ParserError(f"Unexpected error parsing {file_path}: {exc}")

    return units, None


def safe_extract_streaming(file_path: Path) -> Iterator[ExtractedUnit]:
    """Streaming variant for large files — yields units as they're produced.
    On any error, logs nothing here (caller's responsibility) and simply
    stops yielding rather than raising.
    """
    parser = get_parser(file_path)
    if parser is None:
        return
    try:
        yield from parser.extract_units(file_path)
    except ParserError:
        return
    except Exception:  # noqa: BLE001 - a parser bug must not crash the scan
        return
