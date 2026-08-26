"""Structured shape of an OpenRouter classification response. Parsed and
validated — never executed, never used to touch the filesystem."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AIClassification(BaseModel):
    is_pii: bool
    category: str
    confidence: float = Field(ge=0.0, le=1.0)
    severity: str
    reason: str
