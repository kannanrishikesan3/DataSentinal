"""Optional Presidio-based detection layer — the spec's "base engine".

Lazily loaded and fully optional: if `presidio-analyzer` (or its spaCy model)
isn't installed, `is_available()` returns False and the regex detector alone
carries full detection weight. The scanner must work completely without this.
"""

from __future__ import annotations

from datasentinel_agent.core.enums import DetectionMethod, PIICategory
from datasentinel_agent.pii.regex_detector import PIIMatch

_ENGINE = None
_LOAD_ATTEMPTED = False

# Presidio's built-in recognizer entity types we trust and can map onto our
# own category taxonomy. Anything else Presidio returns is ignored — our
# categories are the contract the rest of the pipeline (risk, storage,
# reporting) is built around.
_ENTITY_TO_CATEGORY: dict[str, PIICategory] = {
    "PERSON": PIICategory.PERSON,
    "EMAIL_ADDRESS": PIICategory.EMAIL,
    "PHONE_NUMBER": PIICategory.PHONE_NUMBER,
    "US_SSN": PIICategory.SSN,
    "CREDIT_CARD": PIICategory.CREDIT_CARD,
    "IBAN_CODE": PIICategory.IBAN,
    "IP_ADDRESS": PIICategory.IPV4,  # re-checked below; presidio doesn't distinguish v4/v6
    "LOCATION": PIICategory.ADDRESS,
    "US_DRIVER_LICENSE": PIICategory.DRIVER_LICENSE,
    "US_PASSPORT": PIICategory.PASSPORT,
}


# Presidio defaults to spaCy's `en_core_web_lg` (~500MB+). We ship/expect the
# much smaller `en_core_web_sm` — noticeably less accurate on ambiguous
# names, which is exactly why Presidio is a secondary confirmation layer
# here, never the sole source of truth (the regex/validator layer always
# runs too, and is what the product must work correctly without Presidio at
# all). Deployments that install the large model can swap this via
# DATASENTINEL_SPACY_MODEL.
_DEFAULT_SPACY_MODEL = "en_core_web_sm"


def _get_engine():
    global _ENGINE, _LOAD_ATTEMPTED
    if _LOAD_ATTEMPTED:
        return _ENGINE
    _LOAD_ATTEMPTED = True
    try:
        import os

        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import NlpEngineProvider

        model_name = os.environ.get("DATASENTINEL_SPACY_MODEL", _DEFAULT_SPACY_MODEL)
        provider = NlpEngineProvider(
            nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": model_name}],
            }
        )
        _ENGINE = AnalyzerEngine(nlp_engine=provider.create_engine(), supported_languages=["en"])
    except Exception:
        # Missing package, missing spaCy model, or any init failure — all
        # treated the same: Presidio is simply unavailable this run.
        _ENGINE = None
    return _ENGINE


def is_available() -> bool:
    return _get_engine() is not None


def detect(text: str, *, language: str = "en") -> list[PIIMatch]:
    engine = _get_engine()
    if engine is None or not text.strip():
        return []

    try:
        results = engine.analyze(text=text, language=language)
    except Exception:
        return []

    matches: list[PIIMatch] = []
    for result in results:
        category = _ENTITY_TO_CATEGORY.get(result.entity_type)
        if category is None:
            continue
        value = text[result.start : result.end]
        if category == PIICategory.IPV4 and ":" in value:
            category = PIICategory.IPV6
        matches.append(
            PIIMatch(
                category=category,
                value=value,
                start=result.start,
                end=result.end,
                confidence=result.score,
                detection_method=DetectionMethod.PRESIDIO,
            )
        )
    return matches
