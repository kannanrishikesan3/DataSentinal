"""Format/checksum validators. A regex match alone is never enough to call
something sensitive (spec section 14) — these cut false positives by
verifying the candidate is structurally *possible*, not just pattern-shaped.
"""

from __future__ import annotations

import ipaddress
import re
from datetime import date

# --- Luhn (credit/debit card candidates) -----------------------------------

_CARD_PREFIX_LENGTHS = [
    (re.compile(r"^4\d*$"), (13, 16, 19)),  # Visa
    (re.compile(r"^(5[1-5]|22[2-9]|2[3-6]|27[01]|2720)\d*$"), (16,)),  # Mastercard
    (re.compile(r"^3[47]\d*$"), (15,)),  # Amex
    (re.compile(r"^(6011|65|64[4-9])\d*$"), (16, 19)),  # Discover
]


def luhn_checksum(digits: str) -> bool:
    if not digits.isdigit():
        return False
    total = 0
    reversed_digits = digits[::-1]
    for i, ch in enumerate(reversed_digits):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def validate_credit_card(candidate: str) -> bool:
    digits = re.sub(r"[\s-]", "", candidate)
    if not digits.isdigit() or not (13 <= len(digits) <= 19):
        return False
    if not luhn_checksum(digits):
        return False
    return any(prefix_re.match(digits) and len(digits) in lengths for prefix_re, lengths in _CARD_PREFIX_LENGTHS)


# --- Aadhaar (Verhoeff checksum) --------------------------------------------

_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


def _verhoeff_valid(number: str) -> bool:
    if not number.isdigit():
        return False
    c = 0
    for i, ch in enumerate(reversed(number)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(ch)]]
    return c == 0


def validate_aadhaar(candidate: str) -> bool:
    digits = re.sub(r"[\s-]", "", candidate)
    if not re.fullmatch(r"\d{12}", digits):
        return False
    if digits[0] in ("0", "1"):
        return False  # Aadhaar numbers never start with 0 or 1
    if len(set(digits)) == 1:
        return False  # reject e.g. 111111111111
    return _verhoeff_valid(digits)


# --- PAN (India) -------------------------------------------------------------

_PAN_HOLDER_CODES = set("ABCFGHJLPT")  # 4th character: entity type
_PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


def validate_pan(candidate: str) -> bool:
    value = candidate.strip().upper()
    if not _PAN_RE.fullmatch(value):
        return False
    return value[3] in _PAN_HOLDER_CODES


# --- Email -------------------------------------------------------------------

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def validate_email(candidate: str) -> bool:
    value = candidate.strip()
    if len(value) > 254 or value.count("@") != 1:
        return False
    return bool(_EMAIL_RE.fullmatch(value))


# --- IP addresses --------------------------------------------------------------


def validate_ipv4(candidate: str) -> bool:
    try:
        return isinstance(ipaddress.ip_address(candidate.strip()), ipaddress.IPv4Address)
    except ValueError:
        return False


def validate_ipv6(candidate: str) -> bool:
    try:
        return isinstance(ipaddress.ip_address(candidate.strip()), ipaddress.IPv6Address)
    except ValueError:
        return False


# --- IBAN (mod-97) -------------------------------------------------------------

_IBAN_RE = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}$")


def validate_iban(candidate: str) -> bool:
    value = re.sub(r"[\s-]", "", candidate).upper()
    if not _IBAN_RE.fullmatch(value):
        return False
    rearranged = value[4:] + value[:4]
    numeric = "".join(str(int(ch, 36)) for ch in rearranged)  # letters -> 10-35
    try:
        return int(numeric) % 97 == 1
    except ValueError:
        return False


# --- SWIFT / BIC ---------------------------------------------------------------

_SWIFT_RE = re.compile(r"^[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$")


def validate_swift_bic(candidate: str) -> bool:
    return bool(_SWIFT_RE.fullmatch(candidate.strip().upper()))


# --- SSN (US) --------------------------------------------------------------------

_SSN_RE = re.compile(r"^(\d{3})-?(\d{2})-?(\d{4})$")


def validate_ssn(candidate: str) -> bool:
    match = _SSN_RE.fullmatch(candidate.strip())
    if not match:
        return False
    area, group, serial = match.groups()
    if area in ("000", "666") or area.startswith("9"):
        return False
    if group == "00" or serial == "0000":
        return False
    return True


# --- MAC address -----------------------------------------------------------------

_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")


def validate_mac_address(candidate: str) -> bool:
    return bool(_MAC_RE.fullmatch(candidate.strip()))


# --- Date of birth / age ----------------------------------------------------------


def validate_date_of_birth(candidate: str) -> bool:
    for fmt_pattern in (
        re.compile(r"^(\d{4})-(\d{2})-(\d{2})$"),
        re.compile(r"^(\d{2})/(\d{2})/(\d{4})$"),
    ):
        match = fmt_pattern.fullmatch(candidate.strip())
        if not match:
            continue
        groups = match.groups()
        year, month, day = (groups if len(groups[0]) == 4 else (groups[2], groups[1], groups[0]))
        try:
            parsed = date(int(year), int(month), int(day))
        except ValueError:
            return False
        return date(1900, 1, 1) <= parsed <= date.today()
    return False


def validate_age(candidate: str) -> bool:
    try:
        age = int(candidate.strip())
    except ValueError:
        return False
    return 0 <= age <= 120
