"""Optional OpenRouter classification layer. Only redacted, minimal-context
snippets are ever sent — never whole files or directories. Scanning must
continue normally if OpenRouter is disabled, unreachable, or errors.
"""

from datasentinel_agent.ai.openrouter_client import OpenRouterClient, OpenRouterUnavailable
from datasentinel_agent.ai.redaction_context import build_redacted_context
from datasentinel_agent.ai.schema import AIClassification
from datasentinel_agent.ai.service import AIReviewService

__all__ = [
    "OpenRouterClient",
    "OpenRouterUnavailable",
    "build_redacted_context",
    "AIClassification",
    "AIReviewService",
]
