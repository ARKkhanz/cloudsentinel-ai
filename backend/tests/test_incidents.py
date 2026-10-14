from datetime import datetime, timezone, timedelta
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.detection.isolation_forest_detector import IsolationForestDetector
from backend.app.detection.threshold_detector import ThresholdDetector
from backend.app.models.incident import IncidentModel
from backend.app.models.metric import MetricSampleModel
from backend.app.schemas.metrics import MetricSample
from backend.app.services.anomaly_generator import generate_metrics_with_anomalies


def seed_anomalous_metrics(db_session: Session, service: str = "demo-api") -> None:
    """Helper to seed 50 synthetic metrics containing 2 latency spikes and 1 error spike."""
    gen = generate_metrics_with_anomalies(
        service=service,
        total_samples=50,
        seed=42,
        latency_spike_count=2,
        error_spike_count=1,
    )
    for sample in gen.samples:
        db_sample = MetricSampleModel(
            service=sample.service,
            timestamp=sample.timestamp,
            latency_ms=sample.latency_ms,
            error_rate=sample.error_rate,
            request_count=sample.request_count,
            cpu_usage_pct=sample.cpu_usage_pct,
            memory_usage_pct=sample.memory_usage_pct,
            is_synthetic=sample.is_synthetic,
        )
        db_session.add(db_sample)
    db_session.commit()


def test_1_post_detection_run_threshold_detector(client: TestClient, db_session: Session):
    """Verify POST /api/detection/run executes threshold detector and returns structured findings."""
    seed_anomalous_metrics(db_session, service="demo-api")

    payload = {
        "service": "demo-api",
        "detector": "threshold_baseline",
        "limit": 50,
    }
    response = client.post("/api/detection/run", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert data["service"] == "demo-api"
    assert data["detector_name"] == "threshold_baseline"
    assert data["detector_version"] == "1.0.0"
    assert data["samples_analyzed"] == 50
    assert data["findings_count"] == 3
    assert data["incidents_created"] == 3
    assert data["incidents_already_existing"] == 0
    assert len(data["created_incident_ids"]) == 3
    assert "latency_threshold_ms" in data["detector_metadata"]


def test_2_post_detection_run_isolation_forest(client: TestClient, db_session: Session):
    """Verify POST /api/detection/run executes IsolationForest detector fitted on reference baseline."""
    seed_anomalous_metrics(db_session, service="demo-api")

    payload = {
        "service": "demo-api",
        "detector": "isolation_forest",
        "limit": 50,
    }
    response = client.post("/api/detection/run", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert data["service"] == "demo-api"
    assert data["detector_name"] == "isolation_forest"
    assert data["samples_analyzed"] == 50
    assert data["findings_count"] > 0
    assert data["incidents_created"] > 0
    assert len(data["created_incident_ids"]) == data["incidents_created"]
    assert data["detector_metadata"]["n_estimators"] == 100
    assert data["detector_metadata"]["training_samples"] == 100


def test_3_detection_run_uses_actual_persisted_metrics(client: TestClient, db_session: Session):
    """Verify detection evaluates metrics specifically persisted for the requested service."""
    # Seed metrics for auth-service only
    seed_anomalous_metrics(db_session, service="auth-service")

    # Request detection on payment-service (which has no metrics)
    payload = {
        "service": "payment-service",
        "detector": "threshold_baseline",
        "limit": 50,
    }
    response = client.post("/api/detection/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["samples_analyzed"] == 0
    assert data["findings_count"] == 0
    assert data["incidents_created"] == 0


def test_4_no_incidents_when_no_findings(client: TestClient, db_session: Session):
    """Verify clean baseline metrics generate zero findings and zero incidents."""
    normal_gen = generate_metrics_with_anomalies(
        service="clean-service",
        total_samples=30,
        seed=100,
        latency_spike_count=0,
        error_spike_count=0,
    )
    for sample in normal_gen.samples:
        db_session.add(
            MetricSampleModel(
                service=sample.service,
                timestamp=sample.timestamp,
                latency_ms=sample.latency_ms,
                error_rate=sample.error_rate,
                request_count=sample.request_count,
                cpu_usage_pct=sample.cpu_usage_pct,
                memory_usage_pct=sample.memory_usage_pct,
                is_synthetic=True,
            )
        )
    db_session.commit()

    payload = {
        "service": "clean-service",
        "detector": "threshold_baseline",
        "limit": 50,
    }
    response = client.post("/api/detection/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["findings_count"] == 0
    assert data["incidents_created"] == 0
    assert len(data["created_incident_ids"]) == 0

    # Ensure no rows in DB
    db_incidents = db_session.query(IncidentModel).filter(IncidentModel.service == "clean-service").all()
    assert len(db_incidents) == 0


def test_5_empty_dataset_handling(client: TestClient):
    """Verify detection on completely empty database succeeds gracefully without crashing."""
    payload = {
        "service": "nonexistent-service",
        "detector": "threshold_baseline",
        "limit": 100,
    }
    response = client.post("/api/detection/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["samples_analyzed"] == 0
    assert data["findings_count"] == 0
    assert data["incidents_created"] == 0


def test_6_unsupported_detector_validation(client: TestClient):
    """Verify unsupported detector names are rejected with HTTP 422."""
    payload = {
        "service": "demo-api",
        "detector": "deep_neural_network",
        "limit": 50,
    }
    response = client.post("/api/detection/run", json=payload)
    assert response.status_code == 422


def test_7_correct_incidents_created_from_genuine_findings(client: TestClient, db_session: Session):
    """Verify persisted incident fields conform to specification."""
    seed_anomalous_metrics(db_session, service="demo-api")

    res = client.post("/api/detection/run", json={"service": "demo-api", "detector": "threshold_baseline"})
    created_id = res.json()["created_incident_ids"][0]

    incident = db_session.query(IncidentModel).filter(IncidentModel.id == created_id).first()
    assert incident is not None
    assert incident.service == "demo-api"
    assert incident.status == "open"
    assert incident.severity in ("warning", "critical")
    assert incident.detector_name == "threshold_baseline"
    assert incident.detector_version == "1.0.0"
    assert isinstance(incident.summary, str)
    assert isinstance(incident.explanation, str)
    assert incident.dedup_key is not None


def test_8_correct_observed_numerical_evidence(client: TestClient, db_session: Session):
    """Verify evidence snapshot contains exact numerical measurements and threshold boundaries."""
    seed_anomalous_metrics(db_session, service="demo-api")

    res = client.post("/api/detection/run", json={"service": "demo-api", "detector": "threshold_baseline"})
    created_id = res.json()["created_incident_ids"][0]

    incident = db_session.query(IncidentModel).filter(IncidentModel.id == created_id).first()
    obs = incident.observed_metric_evidence
    assert "latency_ms" in obs
    assert "error_rate" in obs
    assert "request_count" in obs
    assert "cpu_usage_pct" in obs
    assert "memory_usage_pct" in obs

    baseline = incident.baseline_evidence
    assert "comparisons" in baseline


def test_9_correct_detector_identity_and_version(client: TestClient, db_session: Session):
    """Verify detector identity is preserved in detection run response and incident model."""
    seed_anomalous_metrics(db_session, service="demo-api")

    res = client.post("/api/detection/run", json={"service": "demo-api", "detector": "threshold_baseline"})
    assert res.json()["detector_name"] == "threshold_baseline"
    assert res.json()["detector_version"] == "1.0.0"

    ml_res = client.post("/api/detection/run", json={"service": "demo-api", "detector": "isolation_forest"})
    assert ml_res.json()["detector_name"] == "isolation_forest"
    assert ml_res.json()["detector_version"] == "1.0.0"


def test_10_severity_mapping(client: TestClient, db_session: Session):
    """Verify explicit severity mapping for latency vs error rate breaches."""
    # Seed latency-only breach
    t1 = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)
    db_session.add(
        MetricSampleModel(
            service="severity-test",
            timestamp=t1,
            latency_ms=350.0,
            error_rate=0.005,
            request_count=100,
            cpu_usage_pct=30.0,
            memory_usage_pct=40.0,
            is_synthetic=True,
        )
    )
    # Seed error-rate breach
    t2 = datetime(2026, 10, 14, 12, 1, 0, tzinfo=timezone.utc)
    db_session.add(
        MetricSampleModel(
            service="severity-test",
            timestamp=t2,
            latency_ms=45.0,
            error_rate=0.25,
            request_count=100,
            cpu_usage_pct=30.0,
            memory_usage_pct=40.0,
            is_synthetic=True,
        )
    )
    db_session.commit()

    client.post("/api/detection/run", json={"service": "severity-test", "detector": "threshold_baseline"})
    incidents = db_session.query(IncidentModel).filter(IncidentModel.service == "severity-test").all()
    assert len(incidents) == 2

    severity_map = {inc.observed_metric_evidence["error_rate"]: inc.severity for inc in incidents}
    assert severity_map[0.005] == "warning"  # Latency breach -> warning
    assert severity_map[0.25] == "critical"  # Error rate breach -> critical


def test_11_database_persistence(client: TestClient, db_session: Session):
    """Verify incidents created via detection pipeline are queryable via standard SQLAlchemy queries."""
    seed_anomalous_metrics(db_session, service="demo-api")
    client.post("/api/detection/run", json={"service": "demo-api", "detector": "threshold_baseline"})

    count = db_session.query(IncidentModel).count()
    assert count == 3


def test_12_duplicate_prevention_on_repeated_runs(client: TestClient, db_session: Session):
    """Verify repeated detection runs on the same samples do not create duplicate incidents."""
    seed_anomalous_metrics(db_session, service="demo-api")

    # First run
    run1 = client.post("/api/detection/run", json={"service": "demo-api", "detector": "threshold_baseline"})
    assert run1.status_code == 200
    d1 = run1.json()
    assert d1["incidents_created"] == 3
    assert d1["incidents_already_existing"] == 0

    # Second run (exact same persisted data)
    run2 = client.post("/api/detection/run", json={"service": "demo-api", "detector": "threshold_baseline"})
    assert run2.status_code == 200
    d2 = run2.json()
    assert d2["incidents_created"] == 0
    assert d2["incidents_already_existing"] == 3
    assert d2["findings_count"] == 3

    # Confirm DB count did not change
    assert db_session.query(IncidentModel).filter(IncidentModel.service == "demo-api").count() == 3


def test_13_independent_incidents_for_different_detectors(client: TestClient, db_session: Session):
    """Verify threshold and ML detectors create independent incidents without suppressing each other."""
    seed_anomalous_metrics(db_session, service="demo-api")

    # Run threshold detector
    t_res = client.post("/api/detection/run", json={"service": "demo-api", "detector": "threshold_baseline"})
    assert t_res.json()["incidents_created"] == 3

    # Run IsolationForest detector on the same samples
    ml_res = client.post("/api/detection/run", json={"service": "demo-api", "detector": "isolation_forest"})
    assert ml_res.json()["incidents_created"] > 0

    t_count = db_session.query(IncidentModel).filter(IncidentModel.detector_name == "threshold_baseline").count()
    ml_count = db_session.query(IncidentModel).filter(IncidentModel.detector_name == "isolation_forest").count()

    assert t_count == 3
    assert ml_count > 0


def test_14_incident_list_ordering(client: TestClient, db_session: Session):
    """Verify GET /api/incidents returns incidents ordered descending (newest first)."""
    now = datetime.now(timezone.utc)
    inc1 = IncidentModel(
        id=str(uuid.uuid4()),
        service="demo-api",
        created_at=now - timedelta(minutes=10),
        severity="warning",
        status="open",
        detector_name="threshold_baseline",
        detector_version="1.0.0",
        summary="Incident 1",
        explanation="Explanation 1",
        observed_metric_evidence={},
        baseline_evidence={},
        window_start=now - timedelta(minutes=10),
        window_end=now - timedelta(minutes=10),
        dedup_key="key-1",
    )
    inc2 = IncidentModel(
        id=str(uuid.uuid4()),
        service="demo-api",
        created_at=now,
        severity="critical",
        status="open",
        detector_name="threshold_baseline",
        detector_version="1.0.0",
        summary="Incident 2",
        explanation="Explanation 2",
        observed_metric_evidence={},
        baseline_evidence={},
        window_start=now,
        window_end=now,
        dedup_key="key-2",
    )
    db_session.add_all([inc1, inc2])
    db_session.commit()

    res = client.get("/api/incidents?service=demo-api")
    assert res.status_code == 200
    items = res.json()["data"]
    assert len(items) == 2
    assert items[0]["id"] == inc2.id  # Newest first
    assert items[1]["id"] == inc1.id


def test_15_incident_filtering_by_service_status_and_detector(client: TestClient, db_session: Session):
    """Verify filtering by service, status, and detector_name parameters."""
    now = datetime.now(timezone.utc)
    inc1 = IncidentModel(
        id=str(uuid.uuid4()),
        service="service-a",
        created_at=now,
        severity="warning",
        status="open",
        detector_name="threshold_baseline",
        detector_version="1.0.0",
        summary="Incident A",
        explanation="Expl A",
        observed_metric_evidence={},
        baseline_evidence={},
        window_start=now,
        window_end=now,
        dedup_key="k1",
    )
    inc2 = IncidentModel(
        id=str(uuid.uuid4()),
        service="service-b",
        created_at=now,
        severity="critical",
        status="resolved",
        detector_name="isolation_forest",
        detector_version="1.0.0",
        summary="Incident B",
        explanation="Expl B",
        observed_metric_evidence={},
        baseline_evidence={},
        window_start=now,
        window_end=now,
        dedup_key="k2",
    )
    db_session.add_all([inc1, inc2])
    db_session.commit()

    # Filter by service
    res_a = client.get("/api/incidents?service=service-a")
    assert len(res_a.json()["data"]) == 1
    assert res_a.json()["data"][0]["service"] == "service-a"

    # Filter by status
    res_open = client.get("/api/incidents?status=open")
    assert len(res_open.json()["data"]) == 1
    assert res_open.json()["data"][0]["status"] == "open"

    # Filter by detector
    res_ml = client.get("/api/incidents?detector_name=isolation_forest")
    assert len(res_ml.json()["data"]) == 1
    assert res_ml.json()["data"][0]["detector_name"] == "isolation_forest"


def test_16_incident_detail_lookup_success_and_404(client: TestClient, db_session: Session):
    """Verify GET /api/incidents/{id} returns full detail on existing ID and 404 on unknown ID."""
    now = datetime.now(timezone.utc)
    inc_id = str(uuid.uuid4())
    inc = IncidentModel(
        id=inc_id,
        service="demo-api",
        created_at=now,
        severity="critical",
        status="open",
        detector_name="threshold_baseline",
        detector_version="1.0.0",
        summary="Detailed Incident",
        explanation="Full explanation",
        observed_metric_evidence={"latency_ms": 320.0},
        baseline_evidence={"comparisons": {}},
        window_start=now,
        window_end=now,
        dedup_key="k-detail",
    )
    db_session.add(inc)
    db_session.commit()

    # Valid ID lookup
    res = client.get(f"/api/incidents/{inc_id}")
    assert res.status_code == 200
    assert res.json()["id"] == inc_id
    assert res.json()["observed_metric_evidence"]["latency_ms"] == 320.0

    # Unknown ID lookup
    unknown_id = str(uuid.uuid4())
    res_404 = client.get(f"/api/incidents/{unknown_id}")
    assert res_404.status_code == 404
    assert f"'{unknown_id}' not found" in res_404.json()["detail"]


def test_17_invalid_request_handling(client: TestClient):
    """Verify validation boundaries: negative limit or excessive limit return HTTP 422."""
    res_neg = client.post("/api/detection/run", json={"service": "demo-api", "detector": "threshold_baseline", "limit": -1})
    assert res_neg.status_code == 422

    res_huge = client.post("/api/detection/run", json={"service": "demo-api", "detector": "threshold_baseline", "limit": 99999})
    assert res_huge.status_code == 422


def test_18_stable_evidence_after_demo_regeneration(client: TestClient, db_session: Session):
    """Verify incident evidence remains intact after synthetic demo metrics are wiped and regenerated."""
    # 1. Generate demo metrics
    client.post("/api/demo/generate", json={"service": "demo-api", "total_samples": 40, "seed": 42, "latency_spike_count": 2})

    # 2. Run detection to create incidents
    det_res = client.post("/api/detection/run", json={"service": "demo-api", "detector": "threshold_baseline"})
    incident_id = det_res.json()["created_incident_ids"][0]

    # 3. Retrieve incident before regeneration
    detail_before = client.get(f"/api/incidents/{incident_id}").json()
    evidence_before = detail_before["observed_metric_evidence"]

    # 4. Regenerate synthetic metrics with replace_existing=True (deleting all metric samples)
    client.post("/api/demo/generate", json={"service": "demo-api", "total_samples": 40, "seed": 99, "replace_existing": True})

    # 5. Verify the incident and its evidence still exist and match exactly
    detail_after = client.get(f"/api/incidents/{incident_id}").json()
    assert detail_after["id"] == incident_id
    assert detail_after["observed_metric_evidence"] == evidence_before


def test_19_utc_timestamp_correctness_and_missing_timestamp_rejection():
    """Verify detector rejects samples with missing timestamps instead of falling back to datetime.now()."""
    sample_no_ts = {
        "service": "demo-api",
        "latency_ms": 400.0,
        "error_rate": 0.20,
        "cpu_usage_pct": 50.0,
        "memory_usage_pct": 50.0,
        "request_count": 100,
        "timestamp": None,
    }

    # Threshold detector
    t_det = ThresholdDetector()
    with pytest.raises(ValueError, match="Missing required observation timestamp"):
        t_det.detect_sample(sample_no_ts)

    # ML detector
    train_data = generate_metrics_with_anomalies(total_samples=30, seed=100).samples
    ml_det = IsolationForestDetector(random_state=42).fit(train_data)
    with pytest.raises(ValueError, match="Missing required observation timestamp"):
        ml_det.predict_sample(sample_no_ts)


def test_20_no_ground_truth_label_leakage_in_incidents(client: TestClient, db_session: Session):
    """Verify incidents contain no ground-truth anomaly attributes in evidence snapshots."""
    seed_anomalous_metrics(db_session, service="demo-api")
    client.post("/api/detection/run", json={"service": "demo-api", "detector": "threshold_baseline"})

    incidents = db_session.query(IncidentModel).all()
    for inc in incidents:
        assert "is_anomaly" not in inc.observed_metric_evidence
        assert "anomaly_type" not in inc.observed_metric_evidence
        assert "ground_truth" not in inc.observed_metric_evidence


def test_21_no_fabricated_root_cause_explanations(client: TestClient, db_session: Session):
    """Verify explanations report numerical evidence factually without diagnosing production root causes."""
    seed_anomalous_metrics(db_session, service="demo-api")

    # Threshold detection explanation check
    client.post("/api/detection/run", json={"service": "demo-api", "detector": "threshold_baseline"})
    t_inc = db_session.query(IncidentModel).filter(IncidentModel.detector_name == "threshold_baseline").first()
    assert "exceeded" in t_inc.explanation
    for speculation in ("database lock", "memory leak", "network partition", "bug in code", "root cause"):
        assert speculation not in t_inc.explanation.lower()

    # IsolationForest explanation check
    client.post("/api/detection/run", json={"service": "demo-api", "detector": "isolation_forest"})
    ml_inc = db_session.query(IncidentModel).filter(IncidentModel.detector_name == "isolation_forest").first()
    assert "isolationforest" in ml_inc.explanation.lower()
    assert "outlier" in ml_inc.explanation.lower()
    for speculation in ("database lock", "memory leak", "network partition", "bug in code", "root cause"):
        assert speculation not in ml_inc.explanation.lower()
