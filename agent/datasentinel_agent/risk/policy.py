"""Risk policy loading — thresholds live in `agent/config/default.yaml` under
`risk:` so they're reviewable/diffable and can later be overridden by policy
pushed from the backend, without touching code."""

from __future__ import annotations

from datasentinel_agent.config.scan_config import RiskPolicyConfig, load_scan_config

RiskPolicy = RiskPolicyConfig  # re-exported under the risk-module name


def load_risk_policy() -> RiskPolicy:
    return load_scan_config().risk
