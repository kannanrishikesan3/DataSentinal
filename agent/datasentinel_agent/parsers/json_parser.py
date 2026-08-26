"""JSON parser. Flattens the document into `key: value` lines so downstream
PII/secret detectors — which operate on text — see both the value and its
key as context (e.g. `"ssn": "123-45-6789"` scores higher than a bare number).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from datasentinel_agent.parsers.base import DocumentParser, ExtractedUnit, ParserError

_MAX_DEPTH = 50  # guard against pathological/adversarial nesting


def _flatten(value: Any, prefix: str = "", depth: int = 0) -> Iterator[str]:
    if depth > _MAX_DEPTH:
        return
    if isinstance(value, dict):
        for key, sub_value in value.items():
            new_prefix = f"{prefix}.{key}" if prefix else str(key)
            yield from _flatten(sub_value, new_prefix, depth + 1)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _flatten(item, f"{prefix}[{index}]", depth + 1)
    elif value is not None:
        yield f"{prefix}: {value}" if prefix else str(value)


class JSONParser(DocumentParser):
    def can_parse(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".json"

    def extract_units(self, file_path: Path) -> Iterator[ExtractedUnit]:
        try:
            with file_path.open("r", encoding="utf-8", errors="replace") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise ParserError(f"Failed to parse JSON file {file_path}: {exc}") from exc

        for line_number, line in enumerate(_flatten(data), start=1):
            yield ExtractedUnit(text=line, line_number=line_number)
