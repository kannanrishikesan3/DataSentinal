"""Aggregates every `/api/v1/*` router into one for `main.py` to mount."""

from __future__ import annotations

from fastapi import APIRouter

from datasentinel_backend.api.v1 import (
    audit,
    auth,
    dashboard,
    endpoints,
    enrollment_tokens,
    exclusion_rules,
    findings,
    policies,
    reports,
    scans,
    status,
)

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(status.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(endpoints.router)
api_v1_router.include_router(enrollment_tokens.router)
api_v1_router.include_router(scans.router)
api_v1_router.include_router(findings.router)
api_v1_router.include_router(reports.router)
api_v1_router.include_router(dashboard.router)
api_v1_router.include_router(audit.router)
api_v1_router.include_router(policies.router)
api_v1_router.include_router(exclusion_rules.router)
