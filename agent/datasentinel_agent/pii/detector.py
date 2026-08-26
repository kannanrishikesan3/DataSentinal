"""PII detection orchestrator: runs the regex detector (always) and Presidio
(if available) over each extracted unit, resolves overlapping matches, and
aggregates the results into one `Finding` per (file, category) pair.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timezone
from uuid import uuid4

from datasentinel_agent.core.enums import PIICategory
from datasentinel_agent.core.schema import FileRecord, Finding
from datasentinel_agent.parsers.base import ExtractedUnit
from datasentinel_agent.pii import presidio_engine, regex_detector
from datasentinel_agent.pii.redaction import redact
from datasentinel_agent.pii.regex_detector import PIIMatch
from datasentinel_agent.risk.severity_map import get_baseline_severity


def _spans_overlap(a: PIIMatch, b: PIIMatch) -> bool:
    return a.start < b.end and b.start < a.end


def merge_matches(regex_matches: list[PIIMatch], presidio_matches: list[PIIMatch]) -> list[PIIMatch]:
    """Resolve overlapping candidates. Same-category overlaps from both
    engines merge into one higher-confidence match (method PRESIDIO_REGEX);
    different-category overlaps keep whichever has higher confidence.
    """
    from datasentinel_agent.core.enums import DetectionMethod

    candidates = sorted(regex_matches + presidio_matches, key=lambda m: (-m.confidence, m.start))
    selected: list[PIIMatch] = []

    for match in candidates:
        conflict_index = next(
            (i for i, existing in enumerate(selected) if _spans_overlap(match, existing)), None
        )
        if conflict_index is None:
            selected.append(match)
            continue

        existing = selected[conflict_index]
        if existing.category != match.category:
            continue  # lower-confidence overlap from a different category — drop it

        if existing.detection_method == match.detection_method:
            continue  # duplicate from the same engine — already have it

        selected[conflict_index] = PIIMatch(
            category=existing.category,
            value=existing.value if len(existing.value) >= len(match.value) else match.value,
            start=min(existing.start, match.start),
            end=max(existing.end, match.end),
            confidence=min(1.0, max(existing.confidence, match.confidence) + 0.05),
            detection_method=DetectionMethod.PRESIDIO_REGEX,
        )

    return sorted(selected, key=lambda m: m.start)


def detect_pii_in_units(
    units: Iterable[ExtractedUnit],
    *,
    scan_id: str,
    file_record: FileRecord,
    endpoint_id: str | None = None,
    use_presidio: bool = True,
) -> list[Finding]:
    """Aggregates matches across every unit in a file into one Finding per
    category, with `occurrence_count` and a single representative location
    (the highest-confidence occurrence)."""
    grouped: dict[PIICategory, list[tuple[PIIMatch, ExtractedUnit]]] = defaultdict(list)

    for unit in units:
        if not unit.text.strip():
            continue
        regex_matches = regex_detector.detect(unit.text)
        presidio_matches = presidio_engine.detect(unit.text) if use_presidio else []
        for match in merge_matches(regex_matches, presidio_matches):
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
                is_secret=False,
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
