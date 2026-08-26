"""CPU-aware throttling: a scheduled scan is skipped (and retried on the next
poll) if the system is already under heavy load, per spec section 32 ("avoid
consuming excessive CPU")."""

from __future__ import annotations


def is_cpu_over_threshold(max_cpu_percent: int, *, interval: float = 0.5) -> bool:
    try:
        import psutil
    except ImportError:
        return False  # psutil unavailable — never block scanning because of it

    try:
        return psutil.cpu_percent(interval=interval) > max_cpu_percent
    except Exception:
        return False
