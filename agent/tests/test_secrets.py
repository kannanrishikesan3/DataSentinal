"""Phase 6 tests. All credential-shaped values below are synthetic/fake —
generated to match a vendor's public format spec, never real secrets."""

from datasentinel_agent.core.enums import SecretCategory, Severity
from datasentinel_agent.core.schema import FileRecord
from datasentinel_agent.parsers.base import ExtractedUnit
from datasentinel_agent.secrets.detector import detect_secrets_in_units
from datasentinel_agent.secrets.entropy import is_high_entropy, shannon_entropy
from datasentinel_agent.secrets.regex_detector import detect
from datasentinel_agent.secrets.validators import validate_jwt


def _categories(matches):
    return {m.category for m in matches}


def test_entropy_low_for_repetitive_text():
    assert shannon_entropy("aaaaaaaaaaaaaaaaaaaa") < 1.0


def test_entropy_high_for_random_looking_token():
    assert shannon_entropy("kQ7z9Lp2mW8xR4tY1vN6bH3cJ0sD5fA") > 4.0


def test_is_high_entropy_requires_minimum_length():
    assert not is_high_entropy("aB3$")  # too short regardless of entropy


def test_detects_aws_access_key():
    # AKIA + exactly 16 uppercase-alnum chars, per AWS's public key ID format.
    matches = detect("aws_access_key_id = AKIAABCD1234EFGH5678")
    assert SecretCategory.AWS_CREDENTIALS in _categories(matches)


def test_detects_github_token():
    # ghp_ + exactly 36 alnum chars, per GitHub's classic PAT format.
    matches = detect("token: ghp_ABCDEFGHIJ1234567890ABCDEFGHIJ123456")
    assert SecretCategory.ACCESS_TOKEN in _categories(matches)


def test_detects_stripe_style_key():
    matches = detect("STRIPE_KEY=sk_live_FAKEexampleFAKEexampleFAKE")
    assert SecretCategory.API_KEY in _categories(matches)


def test_validate_jwt_structure():
    # header {"alg":"HS256","typ":"JWT"}, payload {"sub":"synthetic"} — fake signature
    fake_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzeW50aGV0aWMifQ.FAKESIGNATUREFAKESIGNATURE"
    assert validate_jwt(fake_jwt)
    assert not validate_jwt("not.a.jwt")
    assert not validate_jwt("only.two")


def test_detects_valid_jwt_in_text():
    fake_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzeW50aGV0aWMifQ.FAKESIGNATUREFAKESIGNATURE"
    matches = detect(f"Authorization: Bearer {fake_jwt}")
    assert SecretCategory.JWT in _categories(matches)


def test_detects_private_key_block():
    key_block = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIFAKEKEYCONTENTFAKEKEYCONTENTFAKEKEYCONTENT==\n"
        "-----END RSA PRIVATE KEY-----"
    )
    matches = detect(key_block)
    assert SecretCategory.PRIVATE_KEY in _categories(matches)


def test_detects_openssh_private_key_as_ssh_key_category():
    key_block = (
        "-----BEGIN OPENSSH PRIVATE KEY-----\n"
        "b3BlbnNzaC1rZXktdjEFAKEFAKEFAKEFAKEFAKEFAKE==\n"
        "-----END OPENSSH PRIVATE KEY-----"
    )
    matches = detect(key_block)
    assert SecretCategory.SSH_KEY in _categories(matches)


def test_detects_database_url_with_embedded_credentials():
    matches = detect("DATABASE_URL=postgresql://appuser:s3cr3tFakePass@db.internal:5432/appdb")
    assert SecretCategory.DATABASE_URL in _categories(matches)


def test_does_not_flag_database_url_without_credentials():
    matches = detect("DATABASE_URL=postgresql://db.internal:5432/appdb")
    assert SecretCategory.DATABASE_URL not in _categories(matches)


def test_detects_password_assignment_but_ignores_placeholders():
    real = detect('password = "FakeSuperSecret123!"')
    placeholder = detect('password = "changeme"')
    assert SecretCategory.PASSWORD_ASSIGNMENT in _categories(real)
    assert SecretCategory.PASSWORD_ASSIGNMENT not in _categories(placeholder)


def test_generic_entropy_fallback_catches_unrecognized_high_entropy_token():
    matches = detect("config_token: kQ7z9Lp2mW8xR4tY1vN6bH3cJ0sD5fA9zX2qE7rT4yU")
    assert SecretCategory.GENERIC_HIGH_ENTROPY in _categories(matches)


def test_no_secrets_in_clean_text():
    assert detect("This is a perfectly ordinary sentence with no credentials.") == []


def test_secret_findings_are_marked_is_secret_and_fully_redacted(tmp_path):
    f = tmp_path / "config.env"
    f.write_text("placeholder")
    record = FileRecord(path=str(f), filename=f.name, extension=".env", size_bytes=1)

    units = [ExtractedUnit(text="aws_access_key_id = AKIAABCD1234EFGH5678", line_number=1)]
    findings = detect_secrets_in_units(units, scan_id="scan-1", file_record=record)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.is_secret is True
    assert finding.severity == Severity.CRITICAL
    assert "AKIAFAKEEXAMPLE1234" not in finding.redacted_evidence
    assert finding.redacted_evidence.startswith("[REDACTED_")
