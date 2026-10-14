from datetime import datetime
from fastapi.testclient import TestClient


def test_health_endpoint_returns_200(client: TestClient):
    """Verify that GET /health returns HTTP 200 and expected payload structure."""
    response = client.get("/health")
    assert response.status_code == 200
    
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "cloudsentinel-backend"
    assert "version" in payload
    assert "timestamp" in payload


def test_health_timestamp_is_valid_iso_datetime(client: TestClient):
    """Verify that the health check timestamp is parseable as a valid datetime."""
    response = client.get("/health")
    assert response.status_code == 200
    
    raw_ts = response.json()["timestamp"]
    parsed_dt = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
    assert parsed_dt.year >= 2026


def test_health_cors_headers_allow_frontend_origin(client: TestClient):
    """Verify CORS headers when request originates from local React dev server."""
    response = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
