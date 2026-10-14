from datetime import datetime, timezone
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from backend.app.main import app
from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.models.metric import MetricSampleModel
from backend.app.services.metric_generator import generate_synthetic_metrics


# In-memory SQLite engine with StaticPool so all connections share the same memory DB
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """
    Function-scoped isolated test database session.
    Creates clean tables before each test and drops them immediately after.
    Guarantees zero test-to-test cross-contamination and complete isolation from production DB.
    """
    Base.metadata.create_all(bind=test_engine)
    session: Session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """
    Function-scoped FastAPI TestClient fixture wired to the isolated in-memory test database.
    """
    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        except Exception:
            db_session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def seeded_client(client: TestClient, db_session: Session) -> TestClient:
    """
    TestClient fixture with 50 deterministic synthetic metric samples pre-persisted in SQLite.
    Allows tests validating query limits, Pydantic schemas, sorting, and boundaries to read real persisted data.
    """
    raw_samples = generate_synthetic_metrics(service="demo-api", limit=50)
    for s in raw_samples:
        db_record = MetricSampleModel(
            service=s.service,
            timestamp=s.timestamp,
            latency_ms=s.latency_ms,
            error_rate=s.error_rate,
            request_count=s.request_count,
            cpu_usage_pct=s.cpu_usage_pct,
            memory_usage_pct=s.memory_usage_pct,
            is_synthetic=s.is_synthetic,
        )
        db_session.add(db_record)
    
    # Also add 15 samples for auth-service to support custom service query tests
    auth_samples = generate_synthetic_metrics(service="auth-service", limit=15)
    for s in auth_samples:
        db_record = MetricSampleModel(
            service=s.service,
            timestamp=s.timestamp,
            latency_ms=s.latency_ms,
            error_rate=s.error_rate,
            request_count=s.request_count,
            cpu_usage_pct=s.cpu_usage_pct,
            memory_usage_pct=s.memory_usage_pct,
            is_synthetic=s.is_synthetic,
        )
        db_session.add(db_record)

    db_session.commit()
    return client
