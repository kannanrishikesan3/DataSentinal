"""The deterministic risk engine (spec section 17). Two levels:

1. `finalize_finding_severity` — adjusts a single finding's baseline severity
   using its own confidence and occurrence count.
2. `assess_file_risk` — aggregates every finding in a file into one file-level
   severity + numeric score, factoring in secrets co-presence, how many
   distinct sensitive categories are present, and the file's location/
   permissions.

No ML anywhere in this path — every step is an explicit, reviewable rule.
"""

from __future__ import annotations

from pydantic import BaseModel

from datasentinel_agent.core.enums import SEVERITY_ORDER, Severity, max_severity
from datasentinel_agent.core.schema import FileRecord, Finding
from datasentinel_agent.risk.location import is_high_exposure_location
from datasentinel_agent.risk.permissions import is_over_permissive
from datasentinel_agent.risk.policy import RiskPolicy, load_risk_policy

_ORDERED_SEVERITIES = sorted(SEVERITY_ORDER, key=lambda s: SEVERITY_ORDER[s])

_SCORE_BASE: dict[Severity, int] = {
    Severity.CRITICAL: 90,
    Severity.HIGH: 70,
    Severity.MEDIUM: 45,
    Severity.LOW: 20,
    Severity.INFORMATIONAL: 5,
}


def _step(severity: Severity, delta: int) -> Severity:
    index = SEVERITY_ORDER[severity]
    new_index = max(0, min(len(_ORDERED_SEVERITIES) - 1, index + delta))
    return _ORDERED_SEVERITIES[new_index]



# Categories whose baseline severity is deliberately low because, on their
# own, a bare match is highly ambiguous (spec section 17's literal example:
# "Email -> LOW/MEDIUM depending on context"). When the detector's own
# context signal (pii/context.py, already folded into `finding.confidence`
# at detection time) is strong, that's evidence of a genuine PII-dense
# record rather than an incidental value, and the finding earns one step up
# from its LOW baseline. This reuses the confidence the detector already
# computed — it does not re-run context detection here.
_CONTEXT_ESCALATION_CATEGORIES = {"email"}
_HIGH_CONTEXT_CONFIDENCE_THRESHOLD = 0.95


def finalize_finding_severity(finding: Finding, policy: RiskPolicy | None = None) -> Severity:
    """A finding's stored `severity` is the category baseline; this applies
    the per-finding adjustments (confidence, occurrence count) on top."""
    policy = policy or load_risk_policy()
    severity = finding.severity

    if finding.confidence < policy.low_confidence_threshold:
        severity = _step(severity, -1)

    if finding.occurrence_count >= policy.high_occurrence_threshold:
        severity = _step(severity, +1)

    if (
        severity == Severity.LOW
        and finding.category in _CONTEXT_ESCALATION_CATEGORIES
        and finding.confidence >= _HIGH_CONTEXT_CONFIDENCE_THRESHOLD
    ):
        severity = _step(severity, +1)

    return severity


class FileRiskAssessment(BaseModel):
    file_path: str
    severity: Severity
    score: int  # 0-100
    has_secret: bool
    distinct_categories: int
    over_permissive: bool
    high_exposure_location: bool
    contributing_factors: list[str]


def assess_file_risk(
    findings: list[Finding],
    file_record: FileRecord,
    policy: RiskPolicy | None = None,
) -> FileRiskAssessment:
    policy = policy or load_risk_policy()

    if not findings:
        return FileRiskAssessment(
            file_path=file_record.path,
            severity=Severity.INFORMATIONAL,
            score=0,
            has_secret=False,
            distinct_categories=0,
            over_permissive=False,
            high_exposure_location=False,
            contributing_factors=[],
        )

    finding_severities = [finalize_finding_severity(f, policy) for f in findings]
    base_severity = max_severity(finding_severities)

    has_secret = any(f.is_secret for f in findings)
    distinct_categories = len({f.category for f in findings})
    over_permissive = is_over_permissive(file_record.permissions)
    high_exposure = is_high_exposure_location(file_record.path, policy)

    severity = base_severity
    factors: list[str] = []

    if has_secret and policy.secret_forces_critical:
        severity = Severity.CRITICAL
        factors.append("secret_present")
    elif distinct_categories >= policy.aggregation_category_threshold and SEVERITY_ORDER[base_severity] >= SEVERITY_ORDER[Severity.MEDIUM]:
        severity = _step(severity, +1)
        factors.append(f"aggregation_of_{distinct_categories}_categories")

    if severity != Severity.CRITICAL and (over_permissive or high_exposure):
        severity = _step(severity, +1)
        if over_permissive:
            factors.append("over_permissive_file")
        if high_exposure:
            factors.append("high_exposure_location")

    score = _SCORE_BASE[severity]
    score += min(10, distinct_categories * 2)
    score += 5 if has_secret else 0
    score += 5 if over_permissive else 0
    score += 5 if high_exposure else 0
    score = min(100, score)

    return FileRiskAssessment(
        file_path=file_record.path,
        severity=severity,
        score=score,
        has_secret=has_secret,
        distinct_categories=distinct_categories,
        over_permissive=over_permissive,
        high_exposure_location=high_exposure,
        contributing_factors=factors,
    )


def aggregate_severity_counts(findings: list[Finding]) -> dict[Severity, int]:
    counts: dict[Severity, int] = {s: 0 for s in Severity}
    for finding in findings:
        counts[finding.severity] += 1
    return counts
