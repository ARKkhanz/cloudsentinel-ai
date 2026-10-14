"""
CloudSentinel AI — Automated Docker Compose Integration & Persistence Verification

Tests the live running Docker Compose multi-container stack:
1. Verifies direct backend health on port 8000.
2. Verifies Nginx reverse proxy health on port 3000.
3. Verifies Nginx SPA root serving on port 3000.
4. Generates deterministic synthetic telemetry (100 samples, 5 injected anomalies).
5. Executes ThresholdDetector and verifies incident creation.
6. Executes IsolationForest detector and verifies multivariate incident creation.
7. Verifies incident deduplication (re-running detection creates 0 duplicate incidents).
8. Verifies SQLite persistence across container recreation (docker compose down -> up).
"""

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"


def http_request(url: str, method: str = "GET", data: dict = None) -> tuple[int, dict | str]:
    headers = {"Accept": "application/json"}
    body_bytes = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        body_bytes = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            content = resp.read().decode("utf-8")
            try:
                return status, json.loads(content)
            except Exception:
                return status, content
    except urllib.error.HTTPError as exc:
        err_content = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(err_content)
        except Exception:
            return exc.code, err_content
    except Exception as exc:
        return 0, str(exc)


def wait_for_backend(url: str = BACKEND_URL, timeout_seconds: int = 45) -> bool:
    print(f"Waiting for backend at {url}/health (up to {timeout_seconds}s)...")
    start = time.time()
    attempt = 0
    while time.time() - start < timeout_seconds:
        attempt += 1
        status, body = http_request(f"{url}/health")
        if status == 200 and isinstance(body, dict) and body.get("status") == "ok":
            print(f"  [OK] Backend healthy on attempt {attempt} ({time.time() - start:.1f}s)")
            return True
        time.sleep(2)
    return False


def main():
    print("==================================================================")
    print(" CloudSentinel AI — Docker Integration & Persistence Test Suite")
    print("==================================================================")

    # 1. Direct Backend Health
    print("\n[Phase 1] Testing direct backend health on port 8000...")
    status, body = http_request(f"{BACKEND_URL}/health")
    assert status == 200, f"Expected 200 on {BACKEND_URL}/health, got {status}: {body}"
    assert body.get("status") == "ok", f"Expected status='ok', got {body}"
    print(f"  [PASS] Direct backend health OK (service: {body.get('service')}, version: {body.get('version')})")

    # 2. Proxied Health through Nginx
    print("\n[Phase 2] Testing proxied health on port 3000...")
    status, body = http_request(f"{FRONTEND_URL}/health")
    assert status == 200, f"Expected 200 on {FRONTEND_URL}/health, got {status}: {body}"
    assert body.get("status") == "ok", f"Expected status='ok', got {body}"
    print("  [PASS] Nginx reverse proxy forwarded /health to backend successfully.")

    # 3. Proxied Frontend SPA HTML
    print("\n[Phase 3] Testing frontend SPA static file serving...")
    status, content = http_request(f"{FRONTEND_URL}/")
    assert status == 200, f"Expected 200 on {FRONTEND_URL}/, got {status}"
    assert "<!doctype html>" in content.lower() or "<html" in content.lower(), "Expected HTML response for SPA root"
    assert "backend:8000" not in content, "Leaked internal Docker DNS 'backend:8000' in frontend bundle!"
    print("  [PASS] Nginx served compiled React SPA root with zero internal DNS leaks.")

    # 4. Generate Telemetry via Proxied API
    print("\n[Phase 4] Generating synthetic telemetry via POST /api/demo/generate...")
    gen_payload = {
        "service": "demo-api",
        "total_samples": 100,
        "seed": 42,
        "latency_spike_count": 3,
        "error_spike_count": 2,
        "replace_existing": True,
    }
    status, gen_resp = http_request(f"{FRONTEND_URL}/api/demo/generate", method="POST", data=gen_payload)
    assert status == 200, f"Demo generation failed with HTTP {status}: {gen_resp}"
    assert gen_resp.get("samples_persisted") == 100, f"Expected 100 persisted samples, got {gen_resp}"
    assert gen_resp.get("anomalies_injected") == 5, f"Expected 5 injected anomalies, got {gen_resp}"
    print(f"  [PASS] Generated and persisted 100 samples with 5 anomalies (seed: {gen_resp.get('seed')})")

    # Verify telemetry retrieval
    status, metrics_resp = http_request(f"{FRONTEND_URL}/api/metrics?service=demo-api&limit=100")
    assert status == 200, f"Fetching metrics failed with HTTP {status}: {metrics_resp}"
    assert metrics_resp.get("total") == 100, f"Expected 100 total metrics in DB, got {metrics_resp.get('total')}"
    print(f"  [PASS] Verified 100 metrics retrieved through Nginx proxy /api/metrics.")

    # 5. Execute Threshold Baseline Detection
    print("\n[Phase 5] Running Threshold Baseline detection via POST /api/detection/run...")
    thresh_payload = {"service": "demo-api", "detector": "threshold_baseline", "limit": 100}
    status, thresh_resp = http_request(f"{FRONTEND_URL}/api/detection/run", method="POST", data=thresh_payload)
    assert status == 200, f"Threshold detection failed with HTTP {status}: {thresh_resp}"
    thresh_findings = thresh_resp.get("findings_generated", 0)
    thresh_incidents = thresh_resp.get("incidents_created", 0)
    assert thresh_findings > 0, f"Expected threshold findings, got {thresh_findings}"
    assert thresh_incidents > 0, f"Expected created incidents, got {thresh_incidents}"
    print(f"  [PASS] Threshold detector evaluated 100 samples -> {thresh_findings} findings, {thresh_incidents} incidents created.")

    # 6. Execute IsolationForest Detection
    print("\n[Phase 6] Running IsolationForest ML detection via POST /api/detection/run...")
    ml_payload = {"service": "demo-api", "detector": "isolation_forest", "limit": 100}
    status, ml_resp = http_request(f"{FRONTEND_URL}/api/detection/run", method="POST", data=ml_payload)
    assert status == 200, f"ML detection failed with HTTP {status}: {ml_resp}"
    ml_findings = ml_resp.get("findings_generated", 0)
    ml_incidents = ml_resp.get("incidents_created", 0)
    assert ml_findings > 0, f"Expected ML findings, got {ml_findings}"
    assert ml_incidents > 0, f"Expected ML incidents created, got {ml_incidents}"
    print(f"  [PASS] IsolationForest evaluated 100 samples -> {ml_findings} findings, {ml_incidents} incidents created.")

    # Check Total Incidents
    status, inc_list = http_request(f"{FRONTEND_URL}/api/incidents?service=demo-api&limit=50")
    assert status == 200, f"Fetching incidents failed with HTTP {status}: {inc_list}"
    total_incidents_before = inc_list.get("total", 0)
    assert total_incidents_before >= thresh_incidents + ml_incidents, f"Expected incidents >= {thresh_incidents + ml_incidents}, got {total_incidents_before}"
    sample_incident = inc_list["items"][0]
    sample_incident_id = sample_incident["id"]
    print(f"  [PASS] Persisted incident count: {total_incidents_before}. Sample Incident ID: {sample_incident_id}")

    # 7. Deduplication Verification
    print("\n[Phase 7] Verifying deduplication on repeated detection run...")
    status, dedup_resp = http_request(f"{FRONTEND_URL}/api/detection/run", method="POST", data=thresh_payload)
    assert status == 200, f"Repeated detection failed with HTTP {status}: {dedup_resp}"
    dedup_created = dedup_resp.get("incidents_created", 0)
    assert dedup_created == 0, f"Expected 0 new incidents created on repeat run, got {dedup_created}!"
    status, inc_list_after = http_request(f"{FRONTEND_URL}/api/incidents?service=demo-api&limit=50")
    total_incidents_after = inc_list_after.get("total", 0)
    assert total_incidents_after == total_incidents_before, f"Incident count increased from {total_incidents_before} to {total_incidents_after} on duplicate run!"
    print(f"  [PASS] Deduplication verified: exactly 0 duplicate incidents created on re-run (total remains {total_incidents_after}).")

    # 8. SQLite Named-Volume Persistence across Compose restart
    print("\n[Phase 8] Testing SQLite named volume persistence across container restart...")
    print("  Stopping and removing containers with 'docker compose down' (preserving named volume)...")
    res_down = subprocess.run(["docker", "compose", "down"], capture_output=True, text=True)
    assert res_down.returncode == 0, f"docker compose down failed: {res_down.stderr}"

    print("  Restarting containers with 'docker compose up -d'...")
    res_up = subprocess.run(["docker", "compose", "up", "-d"], capture_output=True, text=True)
    assert res_up.returncode == 0, f"docker compose up -d failed: {res_up.stderr}"

    # Wait for backend health
    assert wait_for_backend(BACKEND_URL, timeout_seconds=45), "Backend failed to become healthy after restart!"

    # Verify sample incident still exists
    status, reloaded_incident = http_request(f"{FRONTEND_URL}/api/incidents/{sample_incident_id}")
    assert status == 200, f"Failed to retrieve sample incident {sample_incident_id} after restart: {reloaded_incident}"
    assert reloaded_incident.get("id") == sample_incident_id, "Retrieved incident ID mismatch after restart!"
    assert reloaded_incident.get("observed_metric_evidence"), "Missing observed metric evidence after restart!"
    print(f"  [PASS] Verified sample incident {sample_incident_id} successfully persisted across container recreation.")

    # Verify telemetry count still 100
    status, reloaded_metrics = http_request(f"{FRONTEND_URL}/api/metrics?service=demo-api&limit=100")
    assert status == 200, f"Failed to retrieve metrics after restart: {reloaded_metrics}"
    assert reloaded_metrics.get("total") == 100, f"Expected 100 metrics after restart, got {reloaded_metrics.get('total')}"
    print(f"  [PASS] Verified 100 telemetry samples persisted across container recreation.")

    print("\n==================================================================")
    print(" ALL DOCKER INTEGRATION & PERSISTENCE CHECKS PASSED (100% GREEN)!")
    print("==================================================================")


if __name__ == "__main__":
    main()
