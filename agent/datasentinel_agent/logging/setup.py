"""Structured logging setup. Every logger the agent creates goes through
`get_logger()`, which attaches the redaction filter — there's no code path
that produces an agent log line without it.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from datasentinel_agent.logging.redaction_filter import RedactionFilter

_CONFIGURED = False


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(extra)
        return json.dumps(payload)


def configure_logging(level: str = "INFO", *, json_output: bool = True) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    root = logging.getLogger("datasentinel_agent")
    root.setLevel(level.upper())
    root.handlers.clear()

    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(JsonFormatter() if json_output else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(RedactionFilter())
    root.addHandler(handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()  # idempotent — safe to call from every module
    return logging.getLogger(f"datasentinel_agent.{name}")
