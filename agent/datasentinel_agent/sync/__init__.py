"""Agent -> backend HTTP integration: fetching centrally-pushed policies
(spec section 42). Optional and fail-safe — every call here degrades to
"use the local config" rather than blocking or failing a scan, matching the
agent's offline-first design (spec section 53)."""

from datasentinel_agent.sync.backend_client import BackendClient, BackendUnavailable
from datasentinel_agent.sync.policy_sync import apply_remote_policies, sync_policies
from datasentinel_agent.sync.scan_uploader import build_scan_report_payload, retry_pending_uploads, upload_scan
from datasentinel_agent.sync.upload_queue import PendingUpload, dequeue, enqueue, load_pending

__all__ = [
    "BackendClient",
    "BackendUnavailable",
    "apply_remote_policies",
    "sync_policies",
    "build_scan_report_payload",
    "upload_scan",
    "retry_pending_uploads",
    "PendingUpload",
    "dequeue",
    "enqueue",
    "load_pending",
]
