import os
from typing import Generator
from sqlalchemy import create_engine, inspect, text
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
    """Initialize all database tables registered on Base metadata and ensure column synchronization."""
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)

    try:
        with eng.connect() as conn:
            inspector = inspect(conn)
            if "incidents" in inspector.get_table_names():
                cols = {c["name"] for c in inspector.get_columns("incidents")}
                if "metric_sample_id" not in cols:
                    conn.execute(text("ALTER TABLE incidents ADD COLUMN metric_sample_id INTEGER"))
                if "dedup_key" not in cols:
                    conn.execute(text("ALTER TABLE incidents ADD COLUMN dedup_key VARCHAR(160)"))
                    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_incidents_dedup_key ON incidents (dedup_key)"))
                conn.commit()
    except Exception:
        pass
