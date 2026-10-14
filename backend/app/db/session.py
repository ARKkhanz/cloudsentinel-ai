import logging
import os
from typing import Generator
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session

from backend.app.config import settings
from backend.app.db.base import Base

logger = logging.getLogger(__name__)

# Ensure parent directory for SQLite database exists
if settings.database_url.startswith("sqlite:///"):
    db_file_path = settings.database_url.replace("sqlite:///", "")
    if ":memory:" not in db_file_path:
        db_dir = os.path.dirname(os.path.abspath(db_file_path))
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
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
    """
    Initialize all database tables registered on Base metadata and ensure schema synchronization.
    
    Guarantees:
    - Creates missing tables without altering or dropping existing data.
    - Idempotently adds missing required columns ('metric_sample_id', 'dedup_key') to existing tables.
    - Verifies and creates unique index 'ix_incidents_dedup_key' even if columns already exist.
    - Repeated initialization is safe and idempotent.
    - Never conceals schema errors: operational failures are logged and raised.
    """
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)

    try:
        with eng.connect() as conn:
            inspector = inspect(conn)
            if "incidents" in inspector.get_table_names():
                cols = {c["name"] for c in inspector.get_columns("incidents")}
                if "metric_sample_id" not in cols:
                    logger.info("Migrating schema: adding column metric_sample_id to incidents table")
                    conn.execute(text("ALTER TABLE incidents ADD COLUMN metric_sample_id INTEGER"))
                if "dedup_key" not in cols:
                    logger.info("Migrating schema: adding column dedup_key to incidents table")
                    conn.execute(text("ALTER TABLE incidents ADD COLUMN dedup_key VARCHAR(160)"))
                
                # Check for unique index existence
                existing_indexes = {idx["name"] for idx in inspector.get_indexes("incidents")}
                if "ix_incidents_dedup_key" not in existing_indexes:
                    logger.info("Ensuring unique index ix_incidents_dedup_key exists on incidents(dedup_key)")
                    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_incidents_dedup_key ON incidents (dedup_key)"))
                conn.commit()
    except Exception as exc:
        logger.error(f"Database schema initialization failed on {eng.url}: {exc}", exc_info=True)
        raise

