from datetime import datetime
import pytest
from fastapi.testclient import TestClient

from backend.app.schemas.metrics import MetricSample


def test_metrics_empty_database_returns_200_and_zero_samples(client: TestClient):
    """
    Day 2 Milestone 1 requirement:
    Verify that when the database is empty, GET /api/metrics returns HTTP 200
    with an empty data list and total_samples=0, without erroring.
    """
    response = client.get("/api/metrics")
    assert response.status_code == 200
    
    payload = response.json()
    assert payload["service"] == "demo-api"
    assert payload["total_samples"] == 0
    assert payload["order"] == "descending"
    assert payload["data"] == []


def test_metrics_default_returns_200_and_50_samples(seeded_client: TestClient):
    """
    Verify GET /api/metrics returns 50 persisted samples for demo-api.
    Note: Updated for Day 2 persistence; reads from pre-seeded SQLite database.
    """
    response = seeded_client.get("/api/metrics")
    assert response.status_code == 200
    
    payload = response.json()
    assert payload["service"] == "demo-api"
    assert payload["total_samples"] == 50
    assert payload["order"] == "descending"
    assert payload["is_synthetic"] is True
    assert len(payload["data"]) == 50


def test_metrics_custom_parameters_work(seeded_client: TestClient):
    """Verify GET /api/metrics with custom service name and bounded limit against persisted data."""
    response = seeded_client.get("/api/metrics?service=auth-service&limit=15")
    assert response.status_code == 200
    
    payload = response.json()
    assert payload["service"] == "auth-service"
    assert payload["total_samples"] == 15
    assert len(payload["data"]) == 15
    assert all(item["service"] == "auth-service" for item in payload["data"])


@pytest.mark.parametrize("invalid_limit", [0, 201, "abc", -1])
def test_metrics_invalid_limit_rejected_with_422(client: TestClient, invalid_limit):
    """Verify that limits outside [1, 200] or non-integers trigger HTTP 422."""
    response = client.get(f"/api/metrics?limit={invalid_limit}")
    assert response.status_code == 422


@pytest.mark.parametrize("invalid_service", ["", "a" * 101])
def test_metrics_invalid_service_rejected_with_422(client: TestClient, invalid_service):
    """Verify that empty or excessively long service names trigger HTTP 422."""
    response = client.get(f"/api/metrics?service={invalid_service}")
    assert response.status_code == 422


def test_metrics_conform_to_pydantic_schema(seeded_client: TestClient):
    """Verify that every persisted sample retrieved strictly conforms to the MetricSample model."""
    response = seeded_client.get("/api/metrics?limit=25")
    assert response.status_code == 200
    
    for raw_sample in response.json()["data"]:
        validated = MetricSample(**raw_sample)
        assert validated.service == "demo-api"
        assert validated.is_synthetic is True


def test_metrics_synthetic_label_on_all_samples(seeded_client: TestClient):
    """Verify that both the response envelope and each sample are explicitly labeled synthetic."""
    response = seeded_client.get("/api/metrics?limit=30")
    assert response.status_code == 200
    
    payload = response.json()
    assert payload["is_synthetic"] is True
    assert all(item["is_synthetic"] is True for item in payload["data"])


def test_metrics_timestamps_ordered_newest_first(seeded_client: TestClient):
    """Verify timestamps are parseable UTC dates and ordered descending (newest first)."""
    response = seeded_client.get("/api/metrics?limit=20")
    assert response.status_code == 200
    
    timestamps = [
        datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00"))
        for item in response.json()["data"]
    ]
    
    # Assert descending order: each timestamp must be earlier than or equal to the previous
    for i in range(len(timestamps) - 1):
        assert timestamps[i] >= timestamps[i + 1], f"Order mismatch at index {i}"


def test_metrics_reproducibility_deterministic_data(seeded_client: TestClient):
    """Verify that two successive calls with identical parameters return identical persisted data."""
    res_1 = seeded_client.get("/api/metrics?service=demo-api&limit=10")
    res_2 = seeded_client.get("/api/metrics?service=demo-api&limit=10")
    
    assert res_1.status_code == 200
    assert res_2.status_code == 200
    assert res_1.json() == res_2.json()


def test_metrics_numeric_values_within_valid_ranges(seeded_client: TestClient):
    """Verify all numerical fields conform to domain-appropriate telemetry boundaries."""
    response = seeded_client.get("/api/metrics?limit=50")
    assert response.status_code == 200
    
    for item in response.json()["data"]:
        assert item["latency_ms"] >= 0.0, "Latency cannot be negative"
        assert 0.0 <= item["error_rate"] <= 1.0, "Error rate must be a proportion [0, 1]"
        assert item["request_count"] >= 0, "Request count cannot be negative"
        assert 0.0 <= item["cpu_usage_pct"] <= 100.0, "CPU usage must be between 0 and 100%"
        assert 0.0 <= item["memory_usage_pct"] <= 100.0, "Memory usage must be between 0 and 100%"


def test_metrics_cors_headers_allow_frontend_origin(client: TestClient):
    """Verify CORS headers on the metrics route for local development."""
    response = client.get("/api/metrics", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
