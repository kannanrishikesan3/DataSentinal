"""Phase 7 tests: deterministic risk scoring."""

from datetime import datetime, timezone

from datasentinel_agent.core.enums import DetectionMethod, Severity
from datasentinel_agent.core.schema import FileRecord, Finding
from datasentinel_agent.risk.engine import (
    aggregate_severity_counts,
    assess_file_risk,
    finalize_finding_severity,
)
from datasentinel_agent.risk.policy import RiskPolicy


def _finding(category="email", severity=Severity.LOW, confidence=0.9, occurrence_count=1, is_secret=False):
    return Finding(
        finding_id="f1",
        scan_id="scan-1",
        file_path="/home/user/Documents/file.txt",
        category=category,
        is_secret=is_secret,
        severity=severity,
        confidence=confidence,
        occurrence_count=occurrence_count,
        detection_method=DetectionMethod.REGEX,
        redacted_evidence="re***ed",
        detected_at=datetime.now(timezone.utc),
    )


def _file_record(path="/home/user/Documents/file.txt", permissions="-rw-r--r--"):
    return FileRecord(path=path, filename="file.txt", extension=".txt", size_bytes=100, permissions=permissions)


def test_low_confidence_steps_severity_down():
    finding = _finding(severity=Severity.MEDIUM, confidence=0.2)
    policy = RiskPolicy(low_confidence_threshold=0.5)
    assert finalize_finding_severity(finding, policy) == Severity.LOW


def test_email_with_strong_positive_context_escalates_to_medium():
    # Spec section 17's literal example: "Email -> LOW/MEDIUM depending on
    # context." A high-confidence email match (0.95+, the confidence the
    # regex detector actually produces when a positive-context keyword like
    # "email:"/"contact:" is found nearby — see pii/context.py) signals a
    # genuine PII-dense record rather than an incidental value.
    finding = _finding(category="email", severity=Severity.LOW, confidence=0.98)
    assert finalize_finding_severity(finding, RiskPolicy()) == Severity.MEDIUM


def test_bare_ambiguous_email_stays_low():
    # A bare email match with no supporting context keyword nearby (the
    # regex detector's base confidence for EMAIL with no context, 0.90)
    # must stay at its LOW baseline rather than being escalated.
    finding = _finding(category="email", severity=Severity.LOW, confidence=0.90)
    assert finalize_finding_severity(finding, RiskPolicy()) == Severity.LOW


def test_high_occurrence_steps_severity_up():
    finding = _finding(severity=Severity.MEDIUM, confidence=0.9, occurrence_count=50)
    policy = RiskPolicy(high_occurrence_threshold=10)
    assert finalize_finding_severity(finding, policy) == Severity.HIGH


def test_secret_forces_file_to_critical_regardless_of_other_findings():
    findings = [_finding(category="email", severity=Severity.LOW), _finding(category="api_key", severity=Severity.CRITICAL, is_secret=True)]
    assessment = assess_file_risk(findings, _file_record())
    assert assessment.severity == Severity.CRITICAL
    assert assessment.has_secret is True
    assert "secret_present" in assessment.contributing_factors


def test_no_findings_yields_informational_zero_score():
    assessment = assess_file_risk([], _file_record())
    assert assessment.severity == Severity.INFORMATIONAL
    assert assessment.score == 0


def test_aggregation_of_many_categories_escalates_severity():
    findings = [
        _finding(category="email", severity=Severity.MEDIUM),
        _finding(category="phone_number", severity=Severity.MEDIUM),
        _finding(category="address", severity=Severity.MEDIUM),
    ]
    assessment = assess_file_risk(findings, _file_record())
    assert assessment.severity == Severity.HIGH
    assert assessment.distinct_categories == 3


def test_over_permissive_file_escalates_severity():
    findings = [_finding(category="email", severity=Severity.LOW)]
    permissive_file = _file_record(permissions="-rw-rw-rw-")
    strict_file = _file_record(permissions="-rw-------")

    permissive_assessment = assess_file_risk(findings, permissive_file)
    strict_assessment = assess_file_risk(findings, strict_file)

    assert permissive_assessment.over_permissive is True
    assert strict_assessment.over_permissive is False
    from datasentinel_agent.core.enums import SEVERITY_ORDER

    assert SEVERITY_ORDER[permissive_assessment.severity] >= SEVERITY_ORDER[strict_assessment.severity]


def test_high_exposure_location_escalates_severity():
    findings = [_finding(category="email", severity=Severity.LOW)]
    downloads_file = _file_record(path="/home/user/Downloads/export.csv")
    assessment = assess_file_risk(findings, downloads_file)
    assert assessment.high_exposure_location is True


def test_score_is_bounded_0_to_100():
    findings = [_finding(category="api_key", severity=Severity.CRITICAL, is_secret=True) for _ in range(20)]
    assessment = assess_file_risk(findings, _file_record(permissions="-rw-rw-rw-", path="/home/user/Public/dump.txt"))
    assert 0 <= assessment.score <= 100


def test_aggregate_severity_counts():
    findings = [_finding(severity=Severity.HIGH), _finding(severity=Severity.HIGH), _finding(severity=Severity.LOW)]
    counts = aggregate_severity_counts(findings)
    assert counts[Severity.HIGH] == 2
    assert counts[Severity.LOW] == 1
    assert counts[Severity.CRITICAL] == 0
