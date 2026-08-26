"""PII detection: Presidio (optional, when installed) + always-available
regex/validator detection, merged and aggregated into `Finding` objects."""

from datasentinel_agent.pii.detector import detect_pii_in_units, merge_matches
from datasentinel_agent.pii.regex_detector import PIIMatch, detect as detect_regex

__all__ = ["detect_pii_in_units", "merge_matches", "PIIMatch", "detect_regex"]
