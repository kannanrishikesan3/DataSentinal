"""Secret detection: vendor/structural patterns + entropy fallback, treated
as more severe than generic PII. Secrets are never shown in full."""

from datasentinel_agent.secrets.detector import detect_secrets_in_units
from datasentinel_agent.secrets.regex_detector import SecretMatch, detect

__all__ = ["detect_secrets_in_units", "SecretMatch", "detect"]
