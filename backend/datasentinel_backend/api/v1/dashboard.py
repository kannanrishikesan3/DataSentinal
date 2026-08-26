"""GET /api/v1/dashboard/overview — the Overview page's stat tiles and
charts (spec section 25)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from datasentinel_backend.api.v1.schemas import DashboardOverview
from datasentinel_backend.core.database import get_db
from datasentinel_backend.models.models import User
from datasentinel_backend.security.dependencies import get_current_user
from datasentinel_backend.services.dashboard import compute_overview

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardOverview)
def get_overview(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> DashboardOverview:
    return DashboardOverview(**compute_overview(db, user.org_id))
