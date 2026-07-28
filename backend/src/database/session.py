"""Engine and session factory helpers."""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings.api import ApiSettings


def normalize_database_url(url: str) -> str:
    """Map standard PostgreSQL URLs to the psycopg v3 SQLAlchemy driver."""

    if url.startswith("postgresql+psycopg://"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    return url


def get_database_url() -> str | None:
    """Resolve ``DATABASE_URL`` from environment or typed settings."""

    raw = os.environ.get("DATABASE_URL", "").strip()
    if raw:
        return raw
    return ApiSettings().database_url


def create_engine_from_url(url: str | None = None, *, echo: bool = False) -> Engine:
    """Create a sync SQLAlchemy engine for PostgreSQL."""

    resolved = url or get_database_url()
    if not resolved:
        msg = "DATABASE_URL is required to create a database engine"
        raise ValueError(msg)
    return create_engine(
        normalize_database_url(resolved),
        echo=echo,
        pool_pre_ping=True,
        future=True,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Build a session factory bound to ``engine``."""

    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """Transactional scope: commit on success, rollback on error."""

    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
