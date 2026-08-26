"""Database engine/session setup. Targets PostgreSQL in production
(`DATASENTINEL_DATABASE_URL`); the test suite overrides the `get_db`
dependency with an in-memory SQLite session — see `models.models.GUID` for
how the schema stays portable across both.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from datasentinel_backend.core.config import Settings, get_settings
from datasentinel_backend.models.models import Base

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def make_engine(settings: Settings) -> Engine:
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    return create_engine(settings.database_url, connect_args=connect_args)


def init_db(engine: Engine) -> None:
    """Creates all tables if they don't exist. Alembic (`backend/alembic/`)
    is the source of truth for schema evolution in real deployments; this is
    the convenience path for tests and first-run bootstrapping."""
    Base.metadata.create_all(engine)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = make_engine(get_settings())
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = make_session_factory(get_engine())
    return _session_factory


def reset_database_state() -> None:
    """Test-only escape hatch: forces the next get_engine()/get_session_factory()
    call to rebuild from current settings, instead of reusing a cached engine
    bound to a previous test's database."""
    global _engine, _session_factory
    _engine = None
    _session_factory = None


def get_db() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
