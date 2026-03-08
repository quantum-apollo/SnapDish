"""
Database layer: SQLAlchemy 2.x, sync engine + session factory.

Connection URL from AWS Secrets (SNAPDISH_DB_URL) or SNAPDISH_DB_URL env var.
In production, set SNAPDISH_DB_URL in AWS Secrets Manager (alongside OPENAI_API_KEY).

Connection pool tuned for a containerised backend: pool_size=10, max_overflow=20,
pool_pre_ping=True (stale connection health check on checkout).

Usage:
    from .db import get_db_session
    with get_db_session() as session:
        session.execute(...)

If DB is not configured, get_db_session() raises RuntimeError with a clear message.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import get_logger, get_secret

logger = get_logger(__name__)

_engine = None
_SessionLocal: sessionmaker | None = None
_db_lock = threading.Lock()


def _init_engine():
    global _engine, _SessionLocal
    if _engine is not None:
        return
    with _db_lock:
        if _engine is not None:
            return
        db_url = get_secret("SNAPDISH_DB_URL")
        if not db_url:
            logger.warning(
                "db_not_configured",
                extra={"detail": "SNAPDISH_DB_URL not set; database features disabled"},
            )
            return
        try:
            _engine = create_engine(
                db_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=False,
            )
            _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
            logger.info("db_engine_ready")
        except Exception as exc:
            logger.error("db_engine_init_failed", extra={"error": str(exc)})
            _engine = None
            _SessionLocal = None
            raise


def is_db_available() -> bool:
    """True when a DB URL is configured and engine initialised."""
    _init_engine()
    return _engine is not None


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Yield a SQLAlchemy Session; commit on success, rollback on error, always close.
    Raises RuntimeError if database is not configured.
    """
    _init_engine()
    if _SessionLocal is None:
        raise RuntimeError(
            "Database not configured. Set SNAPDISH_DB_URL in AWS Secrets Manager or environment."
        )
    session: Session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_all_tables() -> None:
    """Create all tables (idempotent). Call on startup in non-production or via migration script."""
    from .models import Base  # noqa: F401 — registers all models

    _init_engine()
    if _engine is None:
        logger.warning("create_all_tables_skipped", extra={"reason": "DB not configured"})
        return
    Base.metadata.create_all(bind=_engine)
    logger.info("db_tables_created")
