import json
import subprocess
import sys
import time
import urllib.request
import urllib.error


def verify_live_server():
    print("=== Starting Uvicorn Server on 127.0.0.1:8000 ===")
    server_process = subprocess.Popen(
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
        # Wait for the server to bind and respond
        base_url = "http://127.0.0.1:8000"
        max_retries = 25
        ready = False
        
        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(f"{base_url}/health", timeout=1) as resp:
                    if resp.status == 200:
                        ready = True
                        break
            except Exception:
                time.sleep(0.2)
                
        if not ready:
            print("ERROR: Uvicorn server failed to start within 5 seconds.")
            sys.exit(1)
            
        print("[PASS] Uvicorn server is live and accepting connections on port 8000")
        
        # 1. Real HTTP GET /health with CORS header
        req = urllib.request.Request(
            f"{base_url}/health",
            headers={"Origin": "http://localhost:5173"},
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            status = resp.status
            cors_header = resp.headers.get("access-control-allow-origin")
            body = json.loads(resp.read().decode())
            print(f"\n[HTTP GET /health]: Status {status}")
            print(f"CORS Header 'access-control-allow-origin': {cors_header}")
            print(f"Payload: {body}")
            assert status == 200
            assert cors_header == "http://localhost:5173"
            assert body["status"] == "ok"
            assert body["service"] == "cloudsentinel-backend"
            print("[PASS] Live /health endpoint verified over network")
            
        # 2. Real HTTP GET /api/metrics?service=demo-api&limit=3
        req_metrics = urllib.request.Request(f"{base_url}/api/metrics?service=demo-api&limit=3")
        with urllib.request.urlopen(req_metrics, timeout=2) as resp:
            status = resp.status
            body = json.loads(resp.read().decode())
            print(f"\n[HTTP GET /api/metrics?service=demo-api&limit=3]: Status {status}")
            print(f"Total samples: {body['total_samples']}, is_synthetic: {body['is_synthetic']}")
            assert status == 200
            assert body["total_samples"] == 3
            assert body["is_synthetic"] is True
            assert len(body["data"]) == 3
            print(f"Sample 0: {body['data'][0]}")
            print("[PASS] Live /api/metrics endpoint verified over network")
            
        # 3. Real HTTP GET with invalid limit (limit=0) -> expect HTTP 422
        req_invalid = urllib.request.Request(f"{base_url}/api/metrics?limit=0")
        try:
            urllib.request.urlopen(req_invalid, timeout=2)
            print("ERROR: Expected HTTP 422 for limit=0 but request succeeded!")
            sys.exit(1)
        except urllib.error.HTTPError as e:
            print(f"\n[HTTP GET /api/metrics?limit=0]: Status {e.code}")
            assert e.code == 422
            print("[PASS] Live validation rejection (HTTP 422) verified over network")
            
        print("\n=== ALL LIVE HTTP SERVER CHECKS PASSED ===")
        
    finally:
        print("\nStopping Uvicorn server process...")
        server_process.terminate()
        try:
            server_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server_process.kill()
        print("Server stopped cleanly.")


if __name__ == "__main__":
    verify_live_server()
