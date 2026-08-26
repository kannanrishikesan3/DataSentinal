"""XML parser. Uses `defusedxml` to parse untrusted XML safely — stdlib
`xml.etree.ElementTree` is vulnerable to XXE and entity-expansion ("billion
laughs") attacks on attacker-controlled input, which a scanned file always is.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from datasentinel_agent.parsers.base import DocumentParser, ExtractedUnit, ParserError

try:
    from defusedxml import ElementTree as _ET
except ImportError:  # pragma: no cover - exercised only if the dep is missing
    _ET = None


class XMLParser(DocumentParser):
    def can_parse(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".xml"

    def extract_units(self, file_path: Path) -> Iterator[ExtractedUnit]:
        if _ET is None:
            raise ParserError(
                "defusedxml is not installed; refusing to parse XML with the "
                "unsafe stdlib parser."
            )
        try:
            tree = _ET.parse(str(file_path))
        except Exception as exc:
            # Broad on purpose: OSError, ElementTree's ParseError, and every
            # DefusedXmlException subtype (entity bombs, XXE attempts, ...)
            # must all become a ParserError so one malformed/malicious XML
            # file never aborts the scan.
            raise ParserError(f"Failed to parse XML file {file_path}: {exc}") from exc

        line_number = 0
        for element in tree.getroot().iter():
            text = (element.text or "").strip()
            if text:
                line_number += 1
                tag = element.tag.split("}")[-1]  # strip XML namespace noise
                yield ExtractedUnit(text=f"{tag}: {text}", line_number=line_number)
            for attr_name, attr_value in element.attrib.items():
                if attr_value:
                    line_number += 1
                    yield ExtractedUnit(text=f"{attr_name}: {attr_value}", line_number=line_number)
