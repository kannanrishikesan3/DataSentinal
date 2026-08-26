"""Applies centrally-pushed policies (backend `Policy.config` blobs, spec
section 42) on top of the agent's local `config/default.yaml`. The local
file remains the source of truth for anything a policy doesn't mention —
this only ever narrows/tightens or overrides specific, recognized fields,
never replaces the whole config.

Recognized policy `config` shape (all keys optional):

```json
{
  "risk": {"aggregation_category_threshold": 2, "secret_forces_critical": true, ...},
  "exclude_paths": {"windows": ["C:\\\\Extra\\\\Path"], "linux": ["/extra/path"]},
  "profiles": {"standard": {"max_file_size_mb": 25, "scan_archives": true}}
}
```

A malformed or unrecognized policy is skipped, not fatal — one bad
administrator-authored policy must never block a scan any more than one bad
input file does.
"""

from __future__ import annotations

from datasentinel_agent.config.scan_config import RiskPolicyConfig, ScanConfig, ScanProfile, load_scan_config
from datasentinel_agent.config.settings import Settings
from datasentinel_agent.logging import get_logger
from datasentinel_agent.sync.backend_client import BackendClient, BackendUnavailable

_logger = get_logger("policy_sync")


def _apply_one_policy(config: ScanConfig, policy: dict) -> None:
    overrides = policy.get("config")
    if not isinstance(overrides, dict):
        return

    risk_overrides = overrides.get("risk")
    if isinstance(risk_overrides, dict):
        allowed = {k: v for k, v in risk_overrides.items() if k in RiskPolicyConfig.model_fields}
        if allowed:
            config.risk = config.risk.model_copy(update=allowed)

    exclude_overrides = overrides.get("exclude_paths")
    if isinstance(exclude_overrides, dict):
        for os_key, paths in exclude_overrides.items():
            if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
                continue
            existing = config.exclude_paths.get(os_key, [])
            config.exclude_paths[os_key] = list(dict.fromkeys([*existing, *paths]))

    profile_overrides = overrides.get("profiles")
    if isinstance(profile_overrides, dict):
        for name, fields in profile_overrides.items():
            if name not in config.scan.profiles or not isinstance(fields, dict):
                continue
            allowed = {k: v for k, v in fields.items() if k in ScanProfile.model_fields}
            if allowed:
                config.scan.profiles[name] = config.scan.profiles[name].model_copy(update=allowed)


def apply_remote_policies(config: ScanConfig, policies: list[dict]) -> ScanConfig:
    """Returns a new `ScanConfig` — the input `config` is never mutated."""
    merged = config.model_copy(deep=True)
    for policy in policies:
        if not isinstance(policy, dict):
            continue
        try:
            _apply_one_policy(merged, policy)
        except Exception as exc:  # noqa: BLE001 - one bad policy must not block the scan
            _logger.warning("Skipping malformed policy %r: %s", policy.get("name"), exc)
    return merged


def sync_policies(settings: Settings, config: ScanConfig | None = None) -> ScanConfig:
    """Fetches this endpoint's effective policies from the backend and
    applies them on top of `config` (the local config by default). Returns
    the local config unchanged whenever the backend isn't configured or
    isn't reachable — this must never raise or block a scan.
    """
    base_config = config or load_scan_config()
    if not settings.backend_url or not settings.endpoint_token:
        return base_config

    try:
        with BackendClient(settings.backend_url, settings.endpoint_token) as client:
            policies = client.fetch_effective_policies()
    except BackendUnavailable as exc:
        _logger.info("Policy sync skipped — backend unavailable: %s", exc)
        return base_config

    _logger.info("Applying %d centrally-pushed policies", len(policies))
    return apply_remote_policies(base_config, policies)
