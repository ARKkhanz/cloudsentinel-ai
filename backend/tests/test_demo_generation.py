from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.metric import MetricSampleModel
from backend.app.schemas.demo import DemoGenerateRequest, GroundTruthAnomaly
from backend.app.services.anomaly_generator import (
    DEFAULT_REFERENCE_TIME,
    generate_metrics_with_anomalies,
    get_ground_truth_labels,
)


def test_deterministic_generation_same_seed():
    """Verify identical seed and parameters yield bit-for-bit identical telemetry and ground truth."""
    res1 = generate_metrics_with_anomalies(service="checkout-service", total_samples=100, seed=42)
    res2 = generate_metrics_with_anomalies(service="checkout-service", total_samples=100, seed=42)

    assert len(res1.samples) == len(res2.samples) == 100
    assert len(res1.ground_truth) == len(res2.ground_truth) == 5

    for s1, s2 in zip(res1.samples, res2.samples):
        assert s1.timestamp == s2.timestamp
        assert s1.latency_ms == s2.latency_ms
        assert s1.error_rate == s2.error_rate
        assert s1.cpu_usage_pct == s2.cpu_usage_pct
        assert s1.memory_usage_pct == s2.memory_usage_pct
        assert s1.request_count == s2.request_count

    for gt1, gt2 in zip(res1.ground_truth, res2.ground_truth):
        assert gt1.sample_index == gt2.sample_index
        assert gt1.timestamp == gt2.timestamp
        assert gt1.anomaly_type == gt2.anomaly_type
        assert gt1.injected_value == gt2.injected_value


def test_different_seeds_produce_different_data():
    """Verify different seeds produce distinct metric values and injection placements."""
    res_a = generate_metrics_with_anomalies(seed=42)
    res_b = generate_metrics_with_anomalies(seed=99)

    # Values must differ
    diff_latencies = [s_a.latency_ms != s_b.latency_ms for s_a, s_b in zip(res_a.samples, res_b.samples)]
    assert any(diff_latencies), "Different seeds should produce differing sample values"


def test_normal_baseline_samples():
    """Verify baseline samples stay near normal Gaussian expectations."""
    res = generate_metrics_with_anomalies(total_samples=100, seed=42, latency_spike_count=3, error_spike_count=2)
    anom_indices = {gt.sample_index for gt in res.ground_truth}

    normal_samples = [s for idx, s in enumerate(res.samples) if idx not in anom_indices]
    assert len(normal_samples) == 95

    # Check normal distributions
    avg_latency = sum(s.latency_ms for s in normal_samples) / len(normal_samples)
    avg_error = sum(s.error_rate for s in normal_samples) / len(normal_samples)
    assert 38.0 <= avg_latency <= 46.0, f"Expected normal baseline latency near 42ms, got {avg_latency}"
    assert 0.0 <= avg_error <= 0.015, f"Expected low baseline error rate, got {avg_error}"


def test_latency_spike_injection():
    """Verify latency spikes produce significant excursions and are labeled properly."""
    res = generate_metrics_with_anomalies(total_samples=100, seed=42, latency_spike_count=3, error_spike_count=0)
    assert len(res.ground_truth) == 3

    for gt in res.ground_truth:
        assert gt.anomaly_type == "latency_spike"
        assert gt.injected_value >= 250.0  # Far above 42ms baseline
        sample = res.samples[gt.sample_index]
        assert sample.latency_ms == gt.injected_value
        assert sample.timestamp == gt.timestamp


def test_error_rate_spike_injection():
    """Verify error rate spikes produce significant surges and are labeled properly."""
    res = generate_metrics_with_anomalies(total_samples=100, seed=42, latency_spike_count=0, error_spike_count=3)
    assert len(res.ground_truth) == 3

    for gt in res.ground_truth:
        assert gt.anomaly_type == "error_rate_spike"
        assert gt.injected_value >= 0.10  # >= 10% vs 0.5% baseline
        sample = res.samples[gt.sample_index]
        assert sample.error_rate == gt.injected_value
        assert sample.timestamp == gt.timestamp


def test_anomaly_counts_and_ground_truth_labels():
    """Verify exact count of latency and error anomalies match requested counts."""
    res = generate_metrics_with_anomalies(
        total_samples=120,
        seed=101,
        latency_spike_count=5,
        error_spike_count=4,
    )
    assert len(res.ground_truth) == 9
    latency_gts = [gt for gt in res.ground_truth if gt.anomaly_type == "latency_spike"]
    error_gts = [gt for gt in res.ground_truth if gt.anomaly_type == "error_rate_spike"]

    assert len(latency_gts) == 5
    assert len(error_gts) == 4

    # Verify helper get_ground_truth_labels returns identical labels
    labels = get_ground_truth_labels(
        total_samples=120,
        seed=101,
        latency_spike_count=5,
        error_spike_count=4,
    )
    assert len(labels) == 9
    assert labels[0].sample_index == res.ground_truth[0].sample_index


def test_ground_truth_separation_from_features():
    """
    CRITICAL: Verify MetricSample objects do NOT contain ground-truth anomaly labels.
    Prevents ML detector feature leakage.
    """
    res = generate_metrics_with_anomalies(total_samples=50, seed=42)
    sample = res.samples[0]

    # Verify attributes of MetricSample
    fields = sample.model_dump().keys()
    assert "is_anomaly" not in fields
    assert "anomaly_type" not in fields
    assert "ground_truth" not in fields

    # Detector features must be strictly operational measurements
    detector_features = ["latency_ms", "error_rate", "request_count", "cpu_usage_pct", "memory_usage_pct"]
    for feat in detector_features:
        assert feat in fields


def test_valid_metric_ranges():
    """Verify all generated metrics conform strictly to physical/bounded limits."""
    res = generate_metrics_with_anomalies(total_samples=100, seed=42)
    for s in res.samples:
        assert s.latency_ms >= 0.0
        assert 0.0 <= s.error_rate <= 1.0
        assert 0.0 <= s.cpu_usage_pct <= 100.0
        assert 0.0 <= s.memory_usage_pct <= 100.0
        assert s.request_count >= 0
        assert s.is_synthetic is True


def test_utc_timestamp_formatting_and_ordering():
    """Verify timestamps are timezone-aware UTC and ordered descending (newest first)."""
    res = generate_metrics_with_anomalies(total_samples=30, seed=42)

    assert res.samples[0].timestamp.tzinfo is not None
    assert res.samples[0].timestamp.utcoffset().total_seconds() == 0

    # Descending check: sample 0 is newest, sample 29 is oldest
    for i in range(len(res.samples) - 1):
        assert res.samples[i].timestamp > res.samples[i + 1].timestamp


def test_post_demo_generate_endpoint_success(client: TestClient):
    """Verify POST /api/demo/generate generates, persists, and returns structured summary."""
    payload = {
        "service": "checkout-service",
        "total_samples": 60,
        "seed": 42,
        "latency_spike_count": 2,
        "error_spike_count": 1,
        "replace_existing": True,
    }
    response = client.post("/api/demo/generate", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "success"
    assert body["service"] == "checkout-service"
    assert body["total_samples"] == 60
    assert body["seed"] == 42
    assert body["is_synthetic"] is True
    assert body["anomalies_injected"] == 3
    assert set(body["anomaly_types"]) == {"latency_spike", "error_rate_spike"}
    assert len(body["injected_anomalies"]) == 3
    assert body["generation_policy"] == "replace_existing_synthetic"
    assert "time_range_start" in body
    assert "time_range_end" in body
    assert "created_at" in body


def test_demo_generate_persists_to_database(client: TestClient):
    """Verify records persisted by POST /api/demo/generate are readable via GET /api/metrics."""
    payload = {
        "service": "orders-service",
        "total_samples": 80,
        "seed": 42,
        "latency_spike_count": 3,
        "error_spike_count": 2,
        "replace_existing": True,
    }
    gen_resp = client.post("/api/demo/generate", json=payload)
    assert gen_resp.status_code == 200

    # Query GET /api/metrics
    get_resp = client.get("/api/metrics?service=orders-service&limit=100")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["service"] == "orders-service"
    assert data["total_samples"] == 80
    assert len(data["data"]) == 80
    assert data["is_synthetic"] is True

    # Newest-first ordering check in API output
    first_ts = data["data"][0]["timestamp"]
    last_ts = data["data"][-1]["timestamp"]
    assert first_ts > last_ts


def test_demo_generate_invalid_parameters_rejected(client: TestClient):
    """Verify validation boundaries: negative samples, invalid counts, excessive density."""
    # 1. Total samples below minimum (minimum is 20)
    resp = client.post("/api/demo/generate", json={"service": "api", "total_samples": 10})
    assert resp.status_code == 422

    # 2. Total samples above maximum (maximum is 500)
    resp = client.post("/api/demo/generate", json={"service": "api", "total_samples": 600})
    assert resp.status_code == 422

    # 3. Negative seed
    resp = client.post("/api/demo/generate", json={"service": "api", "seed": -5})
    assert resp.status_code == 422

    # 4. Excessive anomaly density (> 50% of samples)
    resp = client.post(
        "/api/demo/generate",
        json={
            "service": "api",
            "total_samples": 50,
            "latency_spike_count": 20,
            "error_spike_count": 10,  # 30 anomalies > 25 (50% of 50)
        },
    )
    assert resp.status_code == 422


def test_duplicate_prevention_replace_existing(client: TestClient):
    """
    Verify repeated calls with replace_existing=True overwrite existing synthetic samples,
    preventing unlimited growth.
    """
    payload = {
        "service": "inventory-service",
        "total_samples": 50,
        "seed": 42,
        "latency_spike_count": 2,
        "error_spike_count": 1,
        "replace_existing": True,
    }

    # Call 1
    resp1 = client.post("/api/demo/generate", json=payload)
    assert resp1.status_code == 200

    metrics_resp1 = client.get("/api/metrics?service=inventory-service&limit=200")
    assert metrics_resp1.json()["total_samples"] == 50

    # Call 2 with same service & replace_existing=True
    resp2 = client.post("/api/demo/generate", json=payload)
    assert resp2.status_code == 200

    metrics_resp2 = client.get("/api/metrics?service=inventory-service&limit=200")
    # Count must remain 50, NOT 100
    assert metrics_resp2.json()["total_samples"] == 50


def test_duplicate_prevention_does_not_delete_user_data(client: TestClient, db_session: Session):
    """
    Verify demo generation replacement policy does NOT delete:
    1. Real user-ingested metrics (is_synthetic=False).
    2. Metrics for other services.
    """
    # Insert a real user-ingested metric
    user_metric = MetricSampleModel(
        service="checkout-service",
        timestamp=datetime.now(timezone.utc),
        latency_ms=35.0,
        error_rate=0.001,
        request_count=200,
        cpu_usage_pct=25.0,
        memory_usage_pct=40.0,
        is_synthetic=False,  # Real observation
    )
    db_session.add(user_metric)

    # Insert a metric for a different service
    other_metric = MetricSampleModel(
        service="payment-service",
        timestamp=datetime.now(timezone.utc),
        latency_ms=50.0,
        error_rate=0.002,
        request_count=100,
        cpu_usage_pct=30.0,
        memory_usage_pct=45.0,
        is_synthetic=True,
    )
    db_session.add(other_metric)
    db_session.commit()

    # Now run demo generate for checkout-service
    gen_payload = {
        "service": "checkout-service",
        "total_samples": 40,
        "seed": 42,
        "replace_existing": True,
    }
    resp = client.post("/api/demo/generate", json=gen_payload)
    assert resp.status_code == 200

    # Verify user-ingested metric for checkout-service still exists
    persisted_user = db_session.query(MetricSampleModel).filter(
        MetricSampleModel.service == "checkout-service",
        MetricSampleModel.is_synthetic.is_(False),
    ).first()
    assert persisted_user is not None
    assert persisted_user.latency_ms == 35.0

    # Verify other service metrics still exist
    persisted_other = db_session.query(MetricSampleModel).filter(
        MetricSampleModel.service == "payment-service",
    ).first()
    assert persisted_other is not None


def test_existing_metrics_api_compatibility(seeded_client: TestClient):
    """Confirm GET /health, GET /api/metrics, and POST /api/metrics remain fully functional."""
    # 1. Health endpoint
    health_resp = seeded_client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "ok"
    assert health_resp.json()["database"] == "connected"

    # 2. Metrics query
    metrics_resp = seeded_client.get("/api/metrics?service=demo-api&limit=25")
    assert metrics_resp.status_code == 200
    assert metrics_resp.json()["total_samples"] == 25

    # 3. Ingestion POST /api/metrics
    ingest_payload = {
        "service": "custom-service",
        "timestamp": "2026-10-14T12:00:00Z",
        "latency_ms": 48.5,
        "error_rate": 0.002,
        "request_count": 150,
        "cpu_usage_pct": 32.0,
        "memory_usage_pct": 45.0,
        "is_synthetic": True,
    }
    ingest_resp = seeded_client.post("/api/metrics", json=ingest_payload)
    assert ingest_resp.status_code == 201
    assert ingest_resp.json()["service"] == "custom-service"
