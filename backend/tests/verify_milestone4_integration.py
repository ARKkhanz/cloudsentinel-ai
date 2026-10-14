"""
Backend HTTP Lifecycle & Network Integration Verification.

NOTE: This script tests the backend ASGI HTTP lifecycle, network socket connectivity,
CORS header negotiation, and response schemas over live HTTP requests.
It does NOT execute or verify the React browser DOM/UI layer.
"""
import json
import subprocess
import sys
import time
import urllib.request
import urllib.error


def verify_integration():
    print("=== Backend HTTP Process Lifecycle & Socket Verification ===")
    print("(Testing live FastAPI server, network responses & CORS - Not React DOM)")
    
    # 1. Start FastAPI backend on 127.0.0.1:8000
    print("\n1. Starting FastAPI backend...")
    backend_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    
    try:
        # Wait for backend readiness
        ready = False
        for _ in range(25):
            try:
                with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=1) as r:
                    if r.status == 200:
                        ready = True
                        break
            except Exception:
                time.sleep(0.2)
        assert ready, "Backend failed to start on port 8000"
        print("[PASS] FastAPI backend is running and healthy on http://127.0.0.1:8000")
        
        # 2. Verify Health Response
        with urllib.request.urlopen("http://127.0.0.1:8000/health") as r:
            health_payload = json.loads(r.read().decode())
            print(f"[PASS] /health response: {health_payload}")
            assert health_payload["status"] == "ok"
            assert health_payload["service"] == "cloudsentinel-backend"
            
        # 3. Verify Metrics Response (50 samples, synthetic)
        with urllib.request.urlopen("http://127.0.0.1:8000/api/metrics?service=demo-api&limit=50") as r:
            metrics_payload = json.loads(r.read().decode())
            samples = metrics_payload["data"]
            assert len(samples) == 50
            assert metrics_payload["is_synthetic"] is True
            print(f"[PASS] /api/metrics returned {len(samples)} synthetic samples in {metrics_payload['order']} order")
            
            # Compute same stats as React dashboard
            avg_lat = sum(s["latency_ms"] for s in samples) / len(samples)
            avg_err = (sum(s["error_rate"] for s in samples) / len(samples)) * 100
            tot_req = sum(s["request_count"] for s in samples)
            avg_cpu = sum(s["cpu_usage_pct"] for s in samples) / len(samples)
            avg_mem = sum(s["memory_usage_pct"] for s in samples) / len(samples)
            
            print(f"      Calculated UI KPIs -> Avg Latency: {avg_lat:.2f} ms | Avg Error: {avg_err:.2f}% | Total Req: {tot_req:,} | CPU: {avg_cpu:.1f}% | RAM: {avg_mem:.1f}%")
            
        # 4. Verify CORS Header against frontend origin
        req_cors = urllib.request.Request(
            "http://127.0.0.1:8000/api/metrics",
            headers={"Origin": "http://localhost:5173"}
        )
        with urllib.request.urlopen(req_cors) as r:
            allow_origin = r.headers.get("access-control-allow-origin")
            assert allow_origin == "http://localhost:5173"
            print(f"[PASS] CORS header verified: access-control-allow-origin = {allow_origin}")
            
    finally:
        print("\nStopping FastAPI backend to verify error state handling...")
        backend_proc.terminate()
        try:
            backend_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            backend_proc.kill()
            
    # 5. Verify Backend Offline Detection (Error State)
    offline_verified = False
    try:
        urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=1)
    except Exception as e:
        offline_verified = True
        print(f"[PASS] Confirmed backend offline error detection: {e}")
    assert offline_verified, "Backend should be offline"
    
    # 6. Verify Backend Restoration (Retry / Recovery)
    print("\nRestarting FastAPI backend to verify recovery...")
    backend_proc_2 = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        recovered = False
        for _ in range(25):
            try:
                with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=1) as r:
                    if r.status == 200:
                        recovered = True
                        break
            except Exception:
                time.sleep(0.2)
        assert recovered, "Backend failed to recover on port 8000"
        print("[PASS] Backend successfully recovered and returned HTTP 200")
    finally:
        backend_proc_2.terminate()
        try:
            backend_proc_2.wait(timeout=3)
        except subprocess.TimeoutExpired:
            backend_proc_2.kill()
        print("[PASS] Verification processes cleaned up cleanly")
        
    print("\n=== ALL MILESTONE 4 INTEGRATION CHECKS PASSED ===")


if __name__ == "__main__":
    verify_integration()
