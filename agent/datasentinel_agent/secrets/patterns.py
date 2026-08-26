"""Known-vendor and generic secret patterns. Vendor-prefixed patterns (GitHub,
AWS, Slack, Stripe, Google, ...) are high-confidence on their own; generic
patterns (password assignments, connection strings) lean more on context.
"""

from __future__ import annotations

import re

from datasentinel_agent.core.enums import SecretCategory

# Each entry: (pattern, category, base_confidence)
VENDOR_PATTERNS: list[tuple[re.Pattern, SecretCategory, float]] = [
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), SecretCategory.AWS_CREDENTIALS, 0.95),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"), SecretCategory.ACCESS_TOKEN, 0.95),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,72}\b"), SecretCategory.ACCESS_TOKEN, 0.90),
    (re.compile(r"\b(?:sk|pk)_(?:live|test)_[A-Za-z0-9]{16,}\b"), SecretCategory.API_KEY, 0.92),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), SecretCategory.API_KEY, 0.90),
    (re.compile(r"\bya29\.[0-9A-Za-z_\-]{20,}\b"), SecretCategory.OAUTH_TOKEN, 0.90),
]

JWT_PATTERN = re.compile(r"\bey[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b")

PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN (?:RSA |EC |DSA |ENCRYPTED )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |DSA |ENCRYPTED )?PRIVATE KEY-----"
)
SSH_PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN OPENSSH PRIVATE KEY-----[\s\S]*?-----END OPENSSH PRIVATE KEY-----"
)

# scheme://user:password@host — only fires when credentials are embedded.
DATABASE_URL_PATTERN = re.compile(
    r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^:\s/@]+:[^@\s]+@[^\s'\"]+", re.IGNORECASE
)

CONNECTION_STRING_PATTERN = re.compile(
    r"(?i)\b(?:Server|Data Source|Host)\s*=\s*[^;]+;[^\n]*?(?:Password|Pwd)\s*=\s*[^;'\"\s]+"
)

PASSWORD_ASSIGNMENT_PATTERN = re.compile(
    r"""(?i)\b(password|passwd|pwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token)\s*[:=]\s*["']?([^\s"';]{4,})["']?"""
)

_PLACEHOLDER_VALUES = {
    "changeme", "change_me", "xxxx", "xxxxxxxx", "placeholder", "your_password_here",
    "password", "secret", "123456", "todo", "fixme", "none", "null", "example",
    "<password>", "${password}", "%password%",
}  # fmt: skip


def is_placeholder_value(value: str) -> bool:
    return value.strip("<>${}%").lower() in _PLACEHOLDER_VALUES
