"""Database engine, session factory, and the FastAPI session dependency.

We use SQLAlchemy's ORM. SQLite is the default (file-based, zero setup); the
same models work on PostgreSQL by changing DATABASE_URL. The `connect_args`
line is a SQLite-only requirement: SQLite otherwise refuses to be used from
more than one thread, and FastAPI serves requests on a threadpool.
"""
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    """Declarative base class that all ORM models inherit from."""


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a DB session and always closes it.

    Using a generator dependency guarantees the session is closed even if the
    request handler raises.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all_tables() -> None:
    """Create tables from the ORM models if they don't exist.

    This is enough for a project of this size. A production system with evolving
    schemas would use Alembic migrations instead (noted in docs/limitations.md).
    """
    # Import models so they are registered on Base.metadata before create_all.
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
