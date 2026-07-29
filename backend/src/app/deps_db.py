"""Database session dependency for FastAPI."""

from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy.orm import Session, sessionmaker

from database.session import create_engine_from_url, create_session_factory, get_database_url


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker[Session] | None:
    url = get_database_url()
    if not url:
        return None
    engine = create_engine_from_url(url)
    return create_session_factory(engine)


def get_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session per request."""

    factory = _session_factory()
    if factory is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="Database is not configured.")
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_db_cache() -> None:
    """Clear cached engine/factory (tests)."""

    _session_factory.cache_clear()
