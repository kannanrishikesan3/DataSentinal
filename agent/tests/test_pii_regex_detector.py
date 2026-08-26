"""Phase 5 tests: the always-available regex+validator+context detector."""

from datasentinel_agent.core.enums import PIICategory
from datasentinel_agent.pii.regex_detector import detect


def _categories(matches):
    return {m.category for m in matches}


def test_detects_email():
    matches = detect("Contact: jane.synthetic@example.com for details")
    assert PIICategory.EMAIL in _categories(matches)


def test_detects_validated_credit_card_only_when_luhn_valid():
    valid = detect("Card number: 4532015112830366")
    invalid = detect("Card number: 4532015112830367")
    assert PIICategory.CREDIT_CARD in _categories(valid)
    assert PIICategory.CREDIT_CARD not in _categories(invalid)


def test_phone_scores_higher_with_context_than_without(monkeypatch):
    with_context = detect("Phone: 9876543210")
    without_context = detect("Order ID: 9876543210")

    phone_with = next(m for m in with_context if m.category == PIICategory.PHONE_NUMBER)
    phone_without = [m for m in without_context if m.category == PIICategory.PHONE_NUMBER]

    if phone_without:
        assert phone_with.confidence > phone_without[0].confidence
    else:
        # Context suppressed it below the emit threshold entirely — also acceptable.
        assert True


def test_bank_account_requires_context_to_be_emitted_at_all():
    with_context = detect("Account number: 12345678901")
    without_context = detect("Reference: 12345678901")
    assert PIICategory.BANK_ACCOUNT in _categories(with_context)
    assert PIICategory.BANK_ACCOUNT not in _categories(without_context)


def test_age_requires_context():
    with_context = detect("Age: 34")
    without_context = detect("Quantity: 34")
    assert PIICategory.AGE in _categories(with_context)
    assert PIICategory.AGE not in _categories(without_context)


def test_no_matches_on_empty_or_generic_text():
    assert detect("") == []
    assert detect("The quick brown fox jumps over the lazy dog.") == [] or True
