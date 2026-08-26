"""Structured, secret-safe logging. `get_logger(name)` returns a logger that
always runs through `RedactionFilter` — raw PII/secret values are never
written to logs, even if a caller accidentally includes one.
"""

from datasentinel_agent.logging.redaction_filter import RedactionFilter, redact
from datasentinel_agent.logging.setup import configure_logging, get_logger

__all__ = ["RedactionFilter", "redact", "configure_logging", "get_logger"]
