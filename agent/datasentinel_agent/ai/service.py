"""AI review: an optional, last-stage confidence refinement for findings the
deterministic detectors are already uncertain about (spec's pipeline order:
local detection -> validation -> context -> optional AI classification).

Only a finding's already-redacted evidence, category, and file extension are
ever sent — never the raw value, never surrounding file content, never a
whole file. If OpenRouter is disabled, unconfigured, or fails, findings pass
through completely unchanged; AI never gates or blocks a scan result.
"""

from __future__ import annotations

from pathlib import Path

from datasentinel_agent.ai.openrouter_client import OpenRouterClient
from datasentinel_agent.config.settings import Settings
from datasentinel_agent.core.schema import Finding
from datasentinel_agent.logging import get_logger

DEFAULT_REVIEW_THRESHOLD = 0.70

_logger = get_logger("ai.service")


class AIReviewService:
    def __init__(self, settings: Settings, *, threshold: float = DEFAULT_REVIEW_THRESHOLD, client: OpenRouterClient | None = None):
        self._threshold = threshold
        if client is not None:
            self._client = client
        elif settings.ai_configured:
            self._client = OpenRouterClient(settings.openrouter_api_key, settings.openrouter_model)
        else:
            self._client = None

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def close(self) -> None:
        if self._client is not None:
            self._client.close()

    def review_finding(self, finding: Finding) -> Finding:
        if self._client is None or finding.confidence >= self._threshold:
            return finding

        context = (
            f"Category: {finding.category}\n"
            f"Redacted evidence: {finding.redacted_evidence}\n"
            f"Occurrences in file: {finding.occurrence_count}\n"
            f"File extension: {Path(finding.file_path).suffix}\n"
            f"Detection method: {finding.detection_method.value}\n"
        )

        try:
            result = self._client.classify(context)
        except Exception as exc:  # noqa: BLE001 - AI must NEVER be able to abort a scan
            # The client already catches every failure mode it knows about
            # and returns None; this is the last line of defense against
            # any exception type outside that (a client bug, a dependency
            # raising something new, etc.) propagating up into the scan
            # loop. Per spec: "If OpenRouter fails, scanning must continue
            # normally" — so the finding is left completely unchanged.
            _logger.warning("AI review raised an unexpected exception; leaving finding unchanged: %s", exc)
            return finding

        if result is None:
            return finding  # provider unavailable this call — unchanged, scan continues

        blended_confidence = round(max(0.0, min(1.0, (finding.confidence + result.confidence) / 2)), 4)
        return finding.model_copy(update={"confidence": blended_confidence})
