"""Scan profiles (quick/standard/deep/custom), exclusion rules, and resource
limits (max_workers, max_cpu, max_file_size, scan_timeout).

This package is intentionally a thin marker, not a container for the actual
code — each piece of "policy" naturally lives with the module that enforces
it, and duplicating it here would just be an indirection layer:

- Profile/exclusion schema and loading: `datasentinel_agent.config.scan_config`
  (`ScanProfile`, `RiskPolicyConfig`), backed by `agent/config/default.yaml`.
- Profile enforcement during discovery (max_file_size/max_depth/max_workers):
  `datasentinel_agent.discovery.config.DiscoveryConfig.from_profile`.
- Risk-scoring policy (aggregation thresholds, exposure/permission rules):
  `datasentinel_agent.risk.policy.RiskPolicy`, applied in `risk.engine`.
- Centrally-pushed policies (backend-authored, org-scoped overrides):
  `backend.datasentinel_backend.models.models.Policy` + the `/api/v1/policies`
  endpoints — not yet pulled/applied by the agent (see docs/PHASES.md).
"""
