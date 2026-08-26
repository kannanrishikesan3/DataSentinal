"""Document content extraction: the `DocumentParser` interface, per-format
implementations, and the safe registry entry point (`safe_extract`)."""

from datasentinel_agent.parsers.base import DocumentParser, ExtractedUnit, ParserError
from datasentinel_agent.parsers.registry import (
    SUPPORTED_EXTENSIONS,
    get_parser,
    safe_extract,
    safe_extract_streaming,
)

__all__ = [
    "DocumentParser",
    "ExtractedUnit",
    "ParserError",
    "SUPPORTED_EXTENSIONS",
    "get_parser",
    "safe_extract",
    "safe_extract_streaming",
]
