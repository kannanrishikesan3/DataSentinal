"""Phase 5 tests: validators must reject weak/malformed candidates, not just
match a shape (spec section 14)."""

from datasentinel_agent.pii.validators import (
    validate_aadhaar,
    validate_age,
    validate_credit_card,
    validate_date_of_birth,
    validate_email,
    validate_iban,
    validate_ipv4,
    validate_ipv6,
    validate_mac_address,
    validate_pan,
    validate_ssn,
    validate_swift_bic,
    luhn_checksum,
)


def test_luhn_checksum_known_values():
    assert luhn_checksum("4532015112830366")  # valid test Visa number (Luhn-valid)
    assert not luhn_checksum("4532015112830367")


def test_validate_credit_card_rejects_non_luhn():
    assert not validate_credit_card("4532015112830367")
    assert validate_credit_card("4532015112830366")


def test_validate_aadhaar_verhoeff():
    # A synthetic Aadhaar-shaped number satisfying the Verhoeff checksum.
    assert validate_aadhaar("234123412346")
    assert not validate_aadhaar("111111111111")  # all-same-digit rejected
    assert not validate_aadhaar("023412341234")  # cannot start with 0/1
    assert not validate_aadhaar("12345")  # wrong length


def test_validate_pan_format_and_holder_code():
    assert validate_pan("ABCPE1234F")  # P = individual
    assert not validate_pan("ABCXE1234F")  # X is not a valid holder code
    assert not validate_pan("ABC1234567")  # wrong shape


def test_validate_email():
    assert validate_email("jane.synthetic@example.com")
    assert not validate_email("not-an-email")
    assert not validate_email("a@b")


def test_validate_ssn_rejects_invalid_area_numbers():
    assert validate_ssn("123-45-6789")
    assert not validate_ssn("000-45-6789")
    assert not validate_ssn("666-45-6789")
    assert not validate_ssn("900-45-6789")


def test_validate_ip_addresses():
    assert validate_ipv4("192.168.1.1")
    assert not validate_ipv4("999.999.999.999")
    assert validate_ipv6("2001:0db8:85a3:0000:0000:8a2e:0370:7334")
    assert not validate_ipv6("not-an-ipv6")


def test_validate_mac_address():
    assert validate_mac_address("00:1A:2B:3C:4D:5E")
    assert not validate_mac_address("00:1A:2B:3C:4D")


def test_validate_iban_mod97():
    assert validate_iban("GB82WEST12345698765432")  # well-known valid test IBAN
    assert not validate_iban("GB82WEST12345698765431")


def test_validate_swift_bic():
    assert validate_swift_bic("DEUTDEFF")
    assert validate_swift_bic("DEUTDEFF500")
    assert not validate_swift_bic("SHORT")  # below the 8-character minimum
    assert not validate_swift_bic("TOOLONGCODE1")  # not 8, 11, or a valid shape


def test_validate_date_of_birth():
    assert validate_date_of_birth("1990-05-14")
    assert not validate_date_of_birth("2999-01-01")  # future
    assert not validate_date_of_birth("1990-13-40")  # invalid month/day


def test_validate_age():
    assert validate_age("34")
    assert not validate_age("200")
    assert not validate_age("-5")
