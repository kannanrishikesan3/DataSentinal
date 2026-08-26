"""FastAPI application entry point.

Schema creation/migration is deliberately NOT run on app startup — it's
Alembic's job (`alembic upgrade head`, run once as a deploy step), not an
implicit side effect of booting the API process. Auto-DDL-on-boot causes
races with multiple replicas starting concurrently and bypasses migration
history tracking; `core.database.init_db()` remains available as a utility
for tests and first-run bootstrap scripts that want it explicitly.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from datasentinel_backend import __version__
from datasentinel_backend.api.v1.router import api_v1_router
from datasentinel_backend.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="DataSentinel",
    description="Discover. Classify. Protect.",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "datasentinel-backend", "version": __version__}
