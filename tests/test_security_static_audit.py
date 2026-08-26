"""Turns SECURITY.md's manual grep audit into an enforced regression test:
if any of these patterns are ever introduced into `agent/` or `backend/`
production code, this test fails the build rather than relying on someone
re-running the audit by hand before each release.

Deliberately excludes tests/, virtualenvs, and build artifacts — the claim
in SECURITY.md is about the application's own code-execution/shell-out
surface, not about what a *test* might do to construct a fixture.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

SOURCE_ROOTS = [
    REPO_ROOT / "agent" / "datasentinel_agent",
    REPO_ROOT / "backend" / "datasentinel_backend",
]

# (pattern, human-readable reason)
BANNED_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\beval\s*\("), "eval() — arbitrary code execution"),
    (re.compile(r"\bexec\s*\("), "exec() — arbitrary code execution"),
    (re.compile(r"\bos\.system\s*\("), "os.system() — uncontrolled shell-out"),
    (re.compile(r"\bshell\s*=\s*True"), "shell=True — command-injection surface"),
    (re.compile(r"\bpickle\.loads?\s*\("), "pickle.load(s)() — arbitrary deserialization"),
    (re.compile(r"\bsubprocess\."), "subprocess module — unexpected process spawning"),
]


def _iter_python_files(root: Path):
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def _scan(root: Path) -> list[str]:
    violations = []
    for path in _iter_python_files(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern, reason in BANNED_PATTERNS:
            if pattern.search(text):
                violations.append(f"{path.relative_to(REPO_ROOT)}: matches {pattern.pattern!r} ({reason})")
    return violations


@pytest.mark.parametrize("root", SOURCE_ROOTS, ids=[str(r.relative_to(REPO_ROOT)) for r in SOURCE_ROOTS])
def test_no_code_execution_or_shell_out_surface(root: Path):
    assert root.is_dir(), f"expected source root to exist: {root}"
    violations = _scan(root)
    assert violations == [], "Banned pattern(s) found:\n" + "\n".join(violations)


def test_no_raw_string_formatted_sql_in_backend():
    """Every backend query must go through SQLAlchemy's expression API —
    a raw SQL string built with an f-string or % formatting is the
    classic SQL-injection surface this app must never have."""
    sql_keyword = re.compile(
        r"(f[\"'].{0,200}\b(SELECT|INSERT|UPDATE|DELETE)\b|%\s*\(.{0,80}\)\s*%|\.format\(.{0,80}\).{0,10}"
        r"\b(SELECT|INSERT|UPDATE|DELETE)\b)",
        re.IGNORECASE,
    )
    violations = []
    for path in _iter_python_files(REPO_ROOT / "backend" / "datasentinel_backend"):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in sql_keyword.finditer(text):
            violations.append(f"{path.relative_to(REPO_ROOT)}: {match.group(0)!r}")
    assert violations == [], "Possible raw-SQL string formatting found:\n" + "\n".join(violations)
