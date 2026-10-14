import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from backend.app.config import settings
from backend.app.db.base import Base

# Ensure parent directory for default SQLite database exists
if settings.database_url.startswith("sqlite:///"):
    os.makedirs(settings.data_dir, exist_ok=True)

# Create engine with check_same_thread=False for SQLite multithreaded requests
connect_args = {"check_same_thread": False} if "sqlite" in settings.database_url else {}
engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=False,
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding a SQLAlchemy session.
    Guarantees rollback on error and proper session closure in all cases.
    """
    db: Session = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db(target_engine=None) -> None:
    """Initialize all database tables registered on Base metadata."""
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)
