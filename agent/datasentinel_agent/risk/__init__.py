"""Deterministic risk scoring engine: category, confidence, occurrence count,
file location/permissions, and presence of secrets combine into a
LOW/MEDIUM/HIGH/CRITICAL severity. Policy-configurable; no ML in the
critical path.
"""

from datasentinel_agent.risk.engine import (
    FileRiskAssessment,
    aggregate_severity_counts,
    assess_file_risk,
    finalize_finding_severity,
)
from datasentinel_agent.risk.policy import RiskPolicy, load_risk_policy
from datasentinel_agent.risk.severity_map import get_baseline_severity

__all__ = [
    "FileRiskAssessment",
    "aggregate_severity_counts",
    "assess_file_risk",
    "finalize_finding_severity",
    "RiskPolicy",
    "load_risk_policy",
    "get_baseline_severity",
]
