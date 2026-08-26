"""Secret detection orchestrator: aggregates matches across a file's
extracted units into one `Finding` per (file, category) pair, same shape as
PII findings but with `is_secret=True` and evidence that is always fully
masked — the raw secret value never appears anywhere downstream.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timezone
from uuid import uuid4

from datasentinel_agent.core.enums import SecretCategory
from datasentinel_agent.core.schema import FileRecord, Finding
from datasentinel_agent.parsers.base import ExtractedUnit
from datasentinel_agent.pii.redaction import redact
from datasentinel_agent.risk.severity_map import get_baseline_severity
from datasentinel_agent.secrets.regex_detector import SecretMatch, detect


def detect_secrets_in_units(
    units: Iterable[ExtractedUnit],
    *,
    scan_id: str,
    file_record: FileRecord,
    endpoint_id: str | None = None,
) -> list[Finding]:
    grouped: dict[SecretCategory, list[tuple[SecretMatch, ExtractedUnit]]] = defaultdict(list)

    for unit in units:
        if not unit.text.strip():
            continue
        for match in detect(unit.text):
            grouped[match.category].append((match, unit))

    now = datetime.now(timezone.utc)
    findings: list[Finding] = []
    for category, occurrences in grouped.items():
        best_match, best_unit = max(occurrences, key=lambda pair: pair[0].confidence)
        findings.append(
            Finding(
                finding_id=str(uuid4()),
                scan_id=scan_id,
                endpoint_id=endpoint_id,
                file_path=file_record.path,
                file_hash=file_record.sha256,
                category=category.value,
                is_secret=True,
                severity=get_baseline_severity(category),
                confidence=round(best_match.confidence, 4),
                occurrence_count=len(occurrences),
                page_number=best_unit.page_number,
                line_number=best_unit.line_number,
                sheet_name=best_unit.sheet_name,
                detection_method=best_match.detection_method,
                redacted_evidence=redact(category, best_match.value),
                detected_at=now,
            )
        )

    return findings
