"""Heuristic for whether a file's location is a high-exposure one (shared
drives, Downloads, temp folders, ...) — one of the risk engine's inputs."""

from __future__ import annotations

from datasentinel_agent.risk.policy import RiskPolicy


def is_high_exposure_location(path: str, policy: RiskPolicy) -> bool:
    lowered = path.lower().replace("\\", "/")
    parts = set(lowered.split("/"))
    return any(keyword in parts or keyword in lowered for keyword in policy.high_exposure_location_keywords)
