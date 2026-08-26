"""Filesystem discovery: recursive walk with include/exclude, depth, size, and
extension filters, symlink safety, and cancellation/timeout support.
"""

from datasentinel_agent.discovery.config import (
    DiscoveryConfig,
    resolve_default_exclude_paths,
    resolve_default_include_paths,
)
from datasentinel_agent.discovery.scanner import DiscoveryResult, DiscoveryScanner
from datasentinel_agent.discovery.walker import Candidate, walk

__all__ = [
    "DiscoveryConfig",
    "resolve_default_include_paths",
    "resolve_default_exclude_paths",
    "DiscoveryScanner",
    "DiscoveryResult",
    "Candidate",
    "walk",
]
