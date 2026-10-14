import os
import tempfile
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError

from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.models.metric import MetricSampleModel
from backend.app.models.incident import IncidentModel
from backend.app.main import app


def test_metric_post_and_get_lifecycle(client: TestClient):
    """
    Verify POST /api/metrics successfully inserts a metric and
    subsequent GET /api/metrics retrieves it with HTTP 200.
    """
    metric_payload = {
        "service": "order-service",
        "timestamp": "2026-10-14T15:00:00Z",
        "latency_ms": 55.4,
        "error_rate": 0.012,
        "request_count": 210,
        "cpu_usage_pct": 34.5,
        "memory_usage_pct": 52.1,
        "is_synthetic": True,
    }
    
    # Ingestion via POST /api/metrics
    post_res = client.post("/api/metrics", json=metric_payload)
    assert post_res.status_code == 201
    created = post_res.json()
    assert created["service"] == "order-service"
    assert created["id"] is not None
    assert created["latency_ms"] == 55.4

    # Retrieval via GET /api/metrics
    get_res = client.get("/api/metrics?service=order-service&limit=10")
    assert get_res.status_code == 200
    retrieved = get_res.json()
    assert retrieved["service"] == "order-service"
    assert retrieved["total_samples"] == 1
    assert retrieved["data"][0]["id"] == created["id"]
    assert retrieved["data"][0]["service"] == "order-service"


def test_invalid_metric_payload_rejection(client: TestClient):
    """
    Verify that invalid metric samples (e.g., negative latency,
    error_rate > 1.0, cpu > 100%, empty service name) return HTTP 422.
    """
    # Negative latency
    res = client.post("/api/metrics", json={
        "service": "demo-api",
        "timestamp": "2026-10-14T12:00:00Z",
        "latency_ms": -5.0,
        "error_rate": 0.01,
        "request_count": 100,
        "cpu_usage_pct": 20.0,
        "memory_usage_pct": 30.0,
    })
    assert res.status_code == 422

    # Error rate > 1.0
    res = client.post("/api/metrics", json={
        "service": "demo-api",
        "timestamp": "2026-10-14T12:00:00Z",
        "latency_ms": 40.0,
        "error_rate": 1.5,
        "request_count": 100,
        "cpu_usage_pct": 20.0,
        "memory_usage_pct": 30.0,
    })
    assert res.status_code == 422

    # Empty service name
    res = client.post("/api/metrics", json={
        "service": "",
        "timestamp": "2026-10-14T12:00:00Z",
        "latency_ms": 40.0,
        "error_rate": 0.05,
        "request_count": 100,
        "cpu_usage_pct": 20.0,
        "memory_usage_pct": 30.0,
    })
    assert res.status_code == 422


def test_data_persistence_across_restart():
    """
    Verify that records survive an application restart using a persistent SQLite file.
    Creates a temporary database file, inserts records, disposes of engine and session,
    then initializes a brand-new engine and verifies the records remain intact.
    """
    temp_dir = tempfile.mkdtemp()
    temp_db_path = os.path.join(temp_dir, "restart_test.db")
    db_url = f"sqlite:///{temp_db_path.replace(os.sep, '/')}"

    try:
        # Run 1: Initialize schema and insert sample
        engine_1 = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine_1)
        Session_1 = sessionmaker(bind=engine_1)
        
        with Session_1() as session:
            metric = MetricSampleModel(
                service="restart-test-service",
                timestamp=datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc),
                latency_ms=45.2,
                error_rate=0.005,
                request_count=150,
                cpu_usage_pct=25.0,
                memory_usage_pct=40.0,
                is_synthetic=True,
            )
            session.add(metric)
            session.commit()
            inserted_id = metric.id

        # Simulate shutdown by disposing engine
        engine_1.dispose()

        # Run 2: Restart application with fresh connection to same database file
        engine_2 = create_engine(db_url, connect_args={"check_same_thread": False})
        Session_2 = sessionmaker(bind=engine_2)

        with Session_2() as session:
            retrieved = session.query(MetricSampleModel).filter_by(id=inserted_id).first()
            assert retrieved is not None
            assert retrieved.service == "restart-test-service"
            assert retrieved.latency_ms == 45.2
            assert retrieved.request_count == 150

        engine_2.dispose()
    finally:
        # Cleanup temporary database file
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)


def test_newest_first_ordering_and_service_filtering(client: TestClient, db_session: Session):
    """
    Verify persisted observations are returned in newest-first chronological order
    and correctly filtered by service name.
    """
    base_time = datetime(2026, 10, 14, 10, 0, 0, tzinfo=timezone.utc)
    
    # Insert 3 samples for service A at T, T+1m, T+2m
    for i in range(3):
        db_session.add(MetricSampleModel(
            service="service-a",
            timestamp=base_time + timedelta(minutes=i),
            latency_ms=30.0 + i,
            error_rate=0.01,
            request_count=100,
            cpu_usage_pct=20.0,
            memory_usage_pct=30.0,
            is_synthetic=True,
        ))
    
    # Insert 1 sample for service B
    db_session.add(MetricSampleModel(
        service="service-b",
        timestamp=base_time,
        latency_ms=90.0,
        error_rate=0.05,
        request_count=50,
        cpu_usage_pct=40.0,
        memory_usage_pct=60.0,
        is_synthetic=True,
    ))
    db_session.commit()

    # Query service-a: should return 3 items, newest first
    res_a = client.get("/api/metrics?service=service-a")
    assert res_a.status_code == 200
    data_a = res_a.json()["data"]
    assert len(data_a) == 3
    assert data_a[0]["latency_ms"] == 32.0  # T+2m (newest)
    assert data_a[1]["latency_ms"] == 31.0  # T+1m
    assert data_a[2]["latency_ms"] == 30.0  # T+0m (oldest)

    # Query service-b: should return only service-b
    res_b = client.get("/api/metrics?service=service-b")
    assert res_b.status_code == 200
    data_b = res_b.json()["data"]
    assert len(data_b) == 1
    assert data_b[0]["service"] == "service-b"


def test_transaction_rollback_on_session_error(db_session: Session):
    """
    Verify session rollback handles errors gracefully and prevents dirty reads.
    """
    # Valid record
    valid_metric = MetricSampleModel(
        service="rollback-service",
        timestamp=datetime.now(timezone.utc),
        latency_ms=25.0,
        error_rate=0.01,
        request_count=100,
        cpu_usage_pct=20.0,
        memory_usage_pct=30.0,
        is_synthetic=True,
    )
    db_session.add(valid_metric)
    db_session.commit()

    # Trigger integrity error with duplicate/null or deliberate error
    try:
        invalid_metric = MetricSampleModel(
            service=None,  # Not null violation
            timestamp=datetime.now(timezone.utc),
            latency_ms=25.0,
            error_rate=0.01,
            request_count=100,
            cpu_usage_pct=20.0,
            memory_usage_pct=30.0,
        )
        db_session.add(invalid_metric)
        db_session.commit()
    except Exception:
        db_session.rollback()

    # Verify session remains functional and valid metric survived intact
    count = db_session.query(MetricSampleModel).filter_by(service="rollback-service").count()
    assert count == 1


def test_incident_model_persistence(db_session: Session):
    """
    Verify IncidentModel can be persisted and queried with JSON evidence fields.
    """
    inc_id = f"inc-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    incident = IncidentModel(
        id=inc_id,
        service="payment-service",
        created_at=now,
        severity="critical",
        status="open",
        detector_name="threshold_baseline",
        detector_version="1.0.0",
        summary="High latency spike detected on payment-service",
        explanation="Observed round-trip latency exceeded 150.0 ms threshold.",
        observed_metric_evidence={
            "metric": "latency_ms",
            "observed_value": 312.4,
            "threshold": 150.0,
        },
        baseline_evidence={
            "baseline_mean": 42.1,
            "baseline_std": 5.2,
        },
        window_start=now - timedelta(minutes=5),
        window_end=now,
    )
    db_session.add(incident)
    db_session.commit()

    retrieved = db_session.query(IncidentModel).filter_by(id=inc_id).first()
    assert retrieved is not None
    assert retrieved.service == "payment-service"
    assert retrieved.severity == "critical"
    assert retrieved.observed_metric_evidence["observed_value"] == 312.4
    assert retrieved.baseline_evidence["baseline_mean"] == 42.1


def test_init_db_fresh_database():
    """Verify fresh database initialization creates all tables and required indexes."""
    from backend.app.db.session import init_db
    from sqlalchemy import inspect

    test_eng = create_engine("sqlite:///:memory:")
    init_db(target_engine=test_eng)

    inspector = inspect(test_eng)
    tables = inspector.get_table_names()
    assert "metric_samples" in tables
    assert "incidents" in tables

    incident_cols = {c["name"] for c in inspector.get_columns("incidents")}
    assert "metric_sample_id" in incident_cols
    assert "dedup_key" in incident_cols

    incident_indexes = {idx["name"] for idx in inspector.get_indexes("incidents")}
    assert "ix_incidents_dedup_key" in incident_indexes


def test_init_db_upgrade_from_earlier_schema():
    """
    Verify upgrade from earlier schema missing 'metric_sample_id' and 'dedup_key'.
    Ensures existing historical records remain intact and columns + unique index are added safely.
    """
    from backend.app.db.session import init_db
    from sqlalchemy import inspect, text

    test_eng = create_engine("sqlite:///:memory:")
    with test_eng.connect() as conn:
        # Create earlier legacy incidents table without metric_sample_id or dedup_key
        conn.execute(text("""
            CREATE TABLE incidents (
                id VARCHAR(36) PRIMARY KEY,
                service VARCHAR(100) NOT NULL,
                created_at TIMESTAMP NOT NULL,
                severity VARCHAR(20) NOT NULL,
                status VARCHAR(20) NOT NULL,
                detector_name VARCHAR(50) NOT NULL,
                detector_version VARCHAR(20) NOT NULL,
                summary VARCHAR(255) NOT NULL,
                explanation TEXT NOT NULL,
                observed_metric_evidence JSON NOT NULL,
                baseline_evidence JSON NOT NULL,
                window_start TIMESTAMP NOT NULL,
                window_end TIMESTAMP NOT NULL
            )
        """))
        conn.execute(text("""
            INSERT INTO incidents (
                id, service, created_at, severity, status, detector_name,
                detector_version, summary, explanation, observed_metric_evidence,
                baseline_evidence, window_start, window_end
            ) VALUES (
                'legacy-inc-1', 'auth-service', '2026-10-14 10:00:00', 'warning', 'open',
                'threshold_baseline', '1.0.0', 'Legacy incident', 'Details', '{}', '{}',
                '2026-10-14 10:00:00', '2026-10-14 10:00:00'
            )
        """))
        conn.commit()

    # Run init_db schema synchronization
    init_db(target_engine=test_eng)

    # Inspect schema
    inspector = inspect(test_eng)
    incident_cols = {c["name"] for c in inspector.get_columns("incidents")}
    assert "metric_sample_id" in incident_cols
    assert "dedup_key" in incident_cols

    incident_indexes = {idx["name"] for idx in inspector.get_indexes("incidents")}
    assert "ix_incidents_dedup_key" in incident_indexes

    # Verify historical data preserved intact
    with test_eng.connect() as conn:
        row = conn.execute(text("SELECT id, service, summary, metric_sample_id, dedup_key FROM incidents WHERE id = 'legacy-inc-1'")).fetchone()
        assert row is not None
        assert row[0] == "legacy-inc-1"
        assert row[1] == "auth-service"
        assert row[2] == "Legacy incident"
        assert row[3] is None  # metric_sample_id defaults to NULL safely
        assert row[4] is None  # dedup_key defaults to NULL safely


def test_init_db_repeated_initialization_is_idempotent():
    """Verify repeated calls to init_db do not fail or duplicate objects."""
    from backend.app.db.session import init_db

    test_eng = create_engine("sqlite:///:memory:")
    init_db(target_engine=test_eng)
    # Second call should complete safely without errors
    init_db(target_engine=test_eng)
    # Third call
    init_db(target_engine=test_eng)


def test_init_db_ensures_unique_index_when_columns_already_exist():
    """Verify that if columns exist but unique index is missing, init_db creates it."""
    from backend.app.db.session import init_db
    from sqlalchemy import inspect, text

    test_eng = create_engine("sqlite:///:memory:")
    with test_eng.connect() as conn:
        conn.execute(text("""
            CREATE TABLE incidents (
                id VARCHAR(36) PRIMARY KEY,
                service VARCHAR(100) NOT NULL,
                created_at TIMESTAMP NOT NULL,
                severity VARCHAR(20) NOT NULL,
                status VARCHAR(20) NOT NULL,
                detector_name VARCHAR(50) NOT NULL,
                detector_version VARCHAR(20) NOT NULL,
                summary VARCHAR(255) NOT NULL,
                explanation TEXT NOT NULL,
                observed_metric_evidence JSON NOT NULL,
                baseline_evidence JSON NOT NULL,
                window_start TIMESTAMP NOT NULL,
                window_end TIMESTAMP NOT NULL,
                metric_sample_id INTEGER,
                dedup_key VARCHAR(160)
            )
        """))
        conn.commit()

    # Pre-check: index does NOT exist
    inspector_before = inspect(test_eng)
    indexes_before = {idx["name"] for idx in inspector_before.get_indexes("incidents")}
    assert "ix_incidents_dedup_key" not in indexes_before

    # Run init_db
    init_db(target_engine=test_eng)

    inspector_after = inspect(test_eng)
    indexes_after = {idx["name"] for idx in inspector_after.get_indexes("incidents")}
    assert "ix_incidents_dedup_key" in indexes_after


def test_init_db_observable_failure_on_incompatible_schema():
    """Verify that init_db does not silently conceal schema failures (e.g. duplicate keys when creating unique index)."""
    from backend.app.db.session import init_db
    from sqlalchemy import text

    test_eng = create_engine("sqlite:///:memory:")
    with test_eng.connect() as conn:
        conn.execute(text("""
            CREATE TABLE incidents (
                id VARCHAR(36) PRIMARY KEY,
                service VARCHAR(100) NOT NULL,
                created_at TIMESTAMP NOT NULL,
                severity VARCHAR(20) NOT NULL,
                status VARCHAR(20) NOT NULL,
                detector_name VARCHAR(50) NOT NULL,
                detector_version VARCHAR(20) NOT NULL,
                summary VARCHAR(255) NOT NULL,
                explanation TEXT NOT NULL,
                observed_metric_evidence JSON NOT NULL,
                baseline_evidence JSON NOT NULL,
                window_start TIMESTAMP NOT NULL,
                window_end TIMESTAMP NOT NULL,
                metric_sample_id INTEGER,
                dedup_key VARCHAR(160)
            )
        """))
        # Insert duplicate dedup_key values which will violate unique index creation
        conn.execute(text("""
            INSERT INTO incidents VALUES 
            ('id-1', 's', '2026-10-14', 'c', 'o', 'd', '1', 'sum1', 'exp', '{}', '{}', '2026-10-14', '2026-10-14', 1, 'conflict-key'),
            ('id-2', 's', '2026-10-14', 'c', 'o', 'd', '1', 'sum2', 'exp', '{}', '{}', '2026-10-14', '2026-10-14', 2, 'conflict-key')
        """))
        conn.commit()

    # Running init_db must raise an exception rather than silently suppressing it
    with pytest.raises(Exception):
        init_db(target_engine=test_eng)

