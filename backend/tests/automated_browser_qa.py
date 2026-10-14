"""
CloudSentinel AI — Automated Browser QA Test Suite via Chrome DevTools Protocol (CDP).

Connects directly to Google Chrome via native Chrome DevTools Protocol over WebSockets,
executing real browser DOM inspection, JavaScript console auditing, network monitoring,
click interactions, viewport resizing, screenshot capture, and backend outage/recovery tests.
"""
import asyncio
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime

import websockets

CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9222
TEMP_USER_DATA = os.path.join(os.environ.get("TEMP", r"C:\Temp"), "cloudsentinel_cdp_profile")
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCREENSHOT_DIR = os.path.join(PROJECT_ROOT, "docs", "screenshots")


class BrowserQaRunner:
    def __init__(self):
        self.msg_id = 0
        self.ws = None
        self.console_messages = []
        self.exceptions = []
        self.network_responses = []
        self.results = []
        self.chrome_proc = None

    def record(self, test_name: str, status: str, observation: str, evidence: str = ""):
        print(f"[{status}] {test_name}: {observation}")
        self.results.append({
            "name": test_name,
            "status": status,
            "observation": observation,
            "evidence": evidence
        })

    def start_chrome(self):
        print(f"Launching Google Chrome CDP on port {CDP_PORT}...")
        os.makedirs(TEMP_USER_DATA, exist_ok=True)
        self.chrome_proc = subprocess.Popen(
            [
                CHROME_EXE,
                f"--remote-debugging-port={CDP_PORT}",
                f"--user-data-dir={TEMP_USER_DATA}",
                "--headless=new",
                "--no-first-run",
                "--no-default-browser-check",
                "about:blank",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # Wait for CDP endpoint to be ready
        for _ in range(30):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=1) as resp:
                    if resp.status == 200:
                        print("Google Chrome CDP endpoint is ready.")
                        return
            except Exception:
                time.sleep(0.2)
        raise RuntimeError("Failed to connect to Google Chrome CDP port 9222")

    def stop_chrome(self):
        if self.chrome_proc:
            print("Terminating Google Chrome...")
            self.chrome_proc.terminate()
            try:
                self.chrome_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.chrome_proc.kill()

    async def send_cmd(self, method: str, params: dict = None):
        self.msg_id += 1
        req = {"id": self.msg_id, "method": method}
        if params:
            req["params"] = params
        await self.ws.send(json.dumps(req))
        
        while True:
            resp_raw = await self.ws.recv()
            resp = json.loads(resp_raw)
            # Collect background events
            if "method" in resp:
                if resp["method"] == "Console.messageAdded":
                    self.console_messages.append(resp["params"]["message"])
                elif resp["method"] == "Runtime.exceptionThrown":
                    self.exceptions.append(resp["params"])
                elif resp["method"] == "Network.responseReceived":
                    self.network_responses.append(resp["params"]["response"])
                continue
            
            if resp.get("id") == self.msg_id:
                if "error" in resp:
                    raise RuntimeError(f"CDP Error in {method}: {resp['error']}")
                return resp.get("result", {})

    async def eval_js(self, expression: str):
        result = await self.send_cmd("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        })
        val = result.get("result", {}).get("value")
        return val

    async def capture_screenshot(self, filename: str):
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        res = await self.send_cmd("Page.captureScreenshot", {"format": "png"})
        img_bytes = base64.b64decode(res["data"])
        filepath = os.path.join(SCREENSHOT_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(img_bytes)
        rel_path = os.path.relpath(filepath, PROJECT_ROOT).replace("\\", "/")
        print(f"Captured screenshot: {rel_path} ({len(img_bytes):,} bytes)")
        return rel_path

    async def run(self):
        self.start_chrome()
        
        # Open tab targeting localhost:5173
        target_url = f"http://127.0.0.1:{CDP_PORT}/json/new?http://127.0.0.1:5173"
        req = urllib.request.Request(target_url, method="PUT")
        with urllib.request.urlopen(req) as resp:
            target_info = json.loads(resp.read().decode())
        ws_url = target_info["webSocketDebuggerUrl"]
        print(f"Connecting to Chrome tab WebSocket: {ws_url}")
        
        async with websockets.connect(ws_url) as ws:
            self.ws = ws
            
            # Enable domains
            await self.send_cmd("Page.enable")
            await self.send_cmd("Runtime.enable")
            await self.send_cmd("Console.enable")
            await self.send_cmd("Network.enable")
            
            # PHASE 1: Verify Initial Render
            print("\n--- PHASE 1: Browser Environment & Render Verification ---")
            await asyncio.sleep(2.0)  # Allow Vite to load and React to mount
            
            page_title = await self.eval_js("document.title")
            has_root = await self.eval_js("!!document.querySelector('#root .dashboard-container')")
            
            if page_title == "CloudSentinel AI — Reliability Dashboard" and has_root:
                self.record(
                    "P1_Dashboard_Render",
                    "PASS",
                    "React app rendered inside Google Chrome",
                    f"Title: '{page_title}', Root container present."
                )
            else:
                self.record("P1_Dashboard_Render", "FAIL", f"Unexpected title '{page_title}' or missing root container")

            # PHASE 2: Dashboard Rendering Tests
            print("\n--- PHASE 2: Dashboard Content & KPI Accuracy Tests ---")
            brand_title = await self.eval_js("document.querySelector('.brand-title')?.innerText")
            synthetic_badge = await self.eval_js("document.querySelector('.badge-synthetic')?.innerText")
            health_badge = await self.eval_js("document.querySelector('.badge-health')?.innerText")
            is_healthy = await self.eval_js("document.querySelector('.badge-health')?.classList.contains('healthy')")
            
            self.record(
                "P2_Brand_Title",
                "PASS" if brand_title == "CloudSentinel AI" else "FAIL",
                f"Brand title rendered: '{brand_title}'"
            )
            self.record(
                "P2_Synthetic_Badge",
                "PASS" if "synthetic demo telemetry" in (synthetic_badge or "").lower() else "FAIL",
                f"Synthetic badge visible: '{synthetic_badge}'"
            )
            self.record(
                "P2_Health_Badge_Online",
                "PASS" if is_healthy and "online" in (health_badge or "").lower() else "FAIL",
                f"Health badge state: '{health_badge}' (healthy class: {is_healthy})"
            )
            
            # Fetch actual backend API data to compare mathematically with rendered DOM KPIs
            with urllib.request.urlopen("http://127.0.0.1:8000/api/metrics?service=demo-api&limit=50") as r:
                api_data = json.loads(r.read().decode())
            samples = api_data["data"]
            calc_avg_lat = sum(s["latency_ms"] for s in samples) / len(samples)
            calc_avg_err = (sum(s["error_rate"] for s in samples) / len(samples)) * 100
            calc_tot_req = sum(s["request_count"] for s in samples)
            calc_avg_cpu = sum(s["cpu_usage_pct"] for s in samples) / len(samples)
            calc_avg_mem = sum(s["memory_usage_pct"] for s in samples) / len(samples)

            cards_values = await self.eval_js("""
                Array.from(document.querySelectorAll('.metric-card')).map(c => ({
                    title: c.querySelector('.card-title')?.innerText,
                    value: c.querySelector('.card-value')?.innerText,
                    footer: c.querySelector('.card-footer')?.innerText
                }))
            """)
            
            self.record("P2_Cards_Count", "PASS" if len(cards_values) == 5 else "FAIL", f"Rendered {len(cards_values)} KPI cards")
            
            # Card 1: Monitored Service
            self.record(
                "P2_Card_Service",
                "PASS" if cards_values[0]["value"] == "demo-api" else "FAIL",
                f"Service card value: '{cards_values[0]['value']}'"
            )
            # Card 2: Avg Latency
            dom_lat_str = cards_values[1]["value"].replace(" ms", "").strip()
            dom_lat = float(dom_lat_str) if dom_lat_str != "--" else 0.0
            lat_diff = abs(dom_lat - calc_avg_lat)
            self.record(
                "P2_Card_Avg_Latency",
                "PASS" if lat_diff < 0.05 else "FAIL",
                f"DOM value {dom_lat} ms vs Calculated {calc_avg_lat:.2f} ms (diff: {lat_diff:.3f})"
            )
            # Card 3: Avg Error Rate
            dom_err_str = cards_values[2]["value"].replace("%", "").strip()
            dom_err = float(dom_err_str) if dom_err_str != "--" else 0.0
            err_diff = abs(dom_err - calc_avg_err)
            self.record(
                "P2_Card_Avg_ErrorRate",
                "PASS" if err_diff < 0.05 else "FAIL",
                f"DOM value {dom_err}% vs Calculated {calc_avg_err:.2f}% (diff: {err_diff:.3f})"
            )
            # Card 4: Total Requests
            dom_req_str = cards_values[3]["value"].replace(",", "").strip()
            dom_req = int(dom_req_str) if dom_req_str != "--" else 0
            self.record(
                "P2_Card_Total_Requests",
                "PASS" if dom_req == calc_tot_req else "FAIL",
                f"DOM value {dom_req:,} vs Calculated {calc_tot_req:,}"
            )
            # Card 5: CPU / RAM
            dom_res_str = cards_values[4]["value"]
            self.record(
                "P2_Card_Resources",
                "PASS" if f"{calc_avg_cpu:.1f}%" in dom_res_str and f"{calc_avg_mem:.1f}%" in dom_res_str else "FAIL",
                f"DOM value: '{dom_res_str}' vs Calculated: '{calc_avg_cpu:.1f}% / {calc_avg_mem:.1f}%'"
            )

            # Table verification
            table_rows_count = await self.eval_js("document.querySelectorAll('table.data-table tbody tr').length")
            synthetic_tags_count = await self.eval_js("document.querySelectorAll('table.data-table .tag-synthetic').length")
            first_timestamp = await self.eval_js("document.querySelector('table.data-table tbody tr:first-child td:first-child')?.innerText")
            last_timestamp = await self.eval_js("document.querySelector('table.data-table tbody tr:last-child td:first-child')?.innerText")
            
            self.record("P2_Table_Rows_Count", "PASS" if table_rows_count == 50 else "FAIL", f"Rendered {table_rows_count} table rows (expected 50)")
            self.record("P2_Table_Synthetic_Tags", "PASS" if synthetic_tags_count == 50 else "FAIL", f"Found {synthetic_tags_count} SYNTHETIC tags in table")
            
            # Verify chronological descending order (first row >= last row)
            is_descending = first_timestamp >= last_timestamp
            self.record(
                "P2_Table_Timestamp_Order",
                "PASS" if is_descending else "FAIL",
                f"First row: '{first_timestamp}' >= Last row: '{last_timestamp}' (Order: Descending)"
            )

            # PHASE 3: Browser Console and Network Testing
            print("\n--- PHASE 3: Browser Console & Network Testing ---")
            error_logs = [m for m in self.console_messages if m.get("level") == "error"]
            health_reqs = [r for r in self.network_responses if "/health" in r.get("url", "")]
            metrics_reqs = [r for r in self.network_responses if "/api/metrics" in r.get("url", "")]
            
            self.record(
                "P3_Console_Zero_Errors",
                "PASS" if len(error_logs) == 0 and len(self.exceptions) == 0 else "FAIL",
                f"{len(error_logs)} console errors, {len(self.exceptions)} uncaught exceptions"
            )
            self.record(
                "P3_Network_Health_200",
                "PASS" if any(r.get("status") == 200 for r in health_reqs) else "FAIL",
                f"Observed {len(health_reqs)} /health responses (Status 200 confirmed)"
            )
            self.record(
                "P3_Network_Metrics_200",
                "PASS" if any(r.get("status") == 200 for r in metrics_reqs) else "FAIL",
                f"Observed {len(metrics_reqs)} /api/metrics responses (Status 200 confirmed)"
            )

            # PHASE 4: Refresh Button Testing
            print("\n--- PHASE 4: Refresh Button Testing ---")
            responses_before = len(self.network_responses)
            url_before = await self.eval_js("window.location.href")
            
            # Click the Refresh button in React DOM
            await self.eval_js("document.querySelector('button.btn-primary').click()")
            await asyncio.sleep(1.0)
            
            url_after = await self.eval_js("window.location.href")
            responses_after = len(self.network_responses)
            new_network_calls = responses_after - responses_before
            rows_after_refresh = await self.eval_js("document.querySelectorAll('table.data-table tbody tr').length")
            
            self.record(
                "P4_Refresh_In_Place",
                "PASS" if url_before == url_after else "FAIL",
                f"Page URL unchanged ({url_after}) - No full page reload"
            )
            self.record(
                "P4_Refresh_Network_Dispatched",
                "PASS" if new_network_calls >= 2 else "FAIL",
                f"Dispatched {new_network_calls} new network responses upon click"
            )
            self.record(
                "P4_Refresh_Data_Intact",
                "PASS" if rows_after_refresh == 50 else "FAIL",
                f"Table retains {rows_after_refresh} rows after refresh"
            )

            # PHASE 5: Backend Failure and Stale Data Testing
            print("\n--- PHASE 5: Backend Failure & Stale Data Handling ---")
            print("Stopping FastAPI backend process on port 8000...")
            # Kill process listening on port 8000 (excluding PID 0 / Idle)
            subprocess.run(
                ["powershell", "-Command", "Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -gt 0 } | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"],
                check=False
            )
            # Wait until port 8000 is fully closed
            for _ in range(25):
                try:
                    with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=0.5):
                        time.sleep(0.2)
                except Exception:
                    break
            
            # Click Refresh while backend is offline
            await self.eval_js("document.querySelector('button.btn-primary').click()")
            await asyncio.sleep(2.0)
            
            offline_badge = await self.eval_js("document.querySelector('.badge-health.offline')?.innerText")
            has_error_banner = await self.eval_js("!!document.querySelector('.error-banner')")
            error_title = await self.eval_js("document.querySelector('.error-title')?.innerText")
            has_stale_badge = await self.eval_js("!!document.querySelector('.section-panel .badge-synthetic')")
            stale_badge_text = await self.eval_js("document.querySelector('.section-panel .badge-synthetic')?.innerText")
            
            self.record(
                "P5_Offline_Badge_Displayed",
                "PASS" if offline_badge and "offline" in offline_badge.lower() else "FAIL",
                f"Offline badge: '{offline_badge}'"
            )
            self.record(
                "P5_Error_Banner_Displayed",
                "PASS" if has_error_banner else "FAIL",
                f"Error banner title: '{error_title}'"
            )
            self.record(
                "P5_Stale_Data_Explicit_Labeling",
                "PASS" if has_stale_badge and "stale cached data" in (stale_badge_text or "").lower() else "FAIL",
                f"Stale badge rendered: '{stale_badge_text}'"
            )

            # Capture screenshot of offline/stale state
            await self.capture_screenshot("offline_stale_state.png")

            # PHASE 6: Backend Recovery Testing
            print("\n--- PHASE 6: Backend Recovery Testing ---")
            print("Restarting FastAPI backend from project root...")
            subprocess.Popen(
                [
                    os.path.join(PROJECT_ROOT, "backend", ".venv", "Scripts", "python.exe"),
                    "-m",
                    "uvicorn",
                    "backend.app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                ],
                cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            
            # Wait for backend readiness
            backend_recovered = False
            for _ in range(30):
                try:
                    with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=1) as resp:
                        if resp.status == 200:
                            backend_recovered = True
                            break
                except Exception:
                    time.sleep(0.3)
            
            self.record(
                "P6_Backend_Restart",
                "PASS" if backend_recovered else "FAIL",
                "FastAPI recovered and responds with HTTP 200 on /health"
            )
            
            # Click "Retry Connection" button in React
            await self.eval_js("document.querySelector('button.btn-retry')?.click() || document.querySelector('button.btn-primary')?.click()")
            await asyncio.sleep(2.0)
            
            recovered_badge = await self.eval_js("document.querySelector('.badge-health.healthy')?.innerText")
            error_banner_gone = await self.eval_js("!document.querySelector('.error-banner')")
            recovered_rows = await self.eval_js("document.querySelectorAll('table.data-table tbody tr').length")
            
            self.record(
                "P6_Recovery_Online_Badge",
                "PASS" if recovered_badge and "online" in recovered_badge.lower() else "FAIL",
                f"Recovered health badge: '{recovered_badge}'"
            )
            self.record(
                "P6_Recovery_Error_Banner_Dismissed",
                "PASS" if error_banner_gone else "FAIL",
                "Error banner smoothly dismissed upon successful reconnection"
            )
            self.record(
                "P6_Recovery_Rows_Restored",
                "PASS" if recovered_rows == 50 else "FAIL",
                f"Restored telemetry table with {recovered_rows} rows"
            )

            # PHASE 7: Responsive Design Testing & Viewport Screenshots
            print("\n--- PHASE 7: Responsive Viewport Testing ---")
            viewports = [
                ("Desktop", 1440, 900, "desktop_1440x900.png"),
                ("Tablet", 768, 1024, "tablet_768x1024.png"),
                ("Mobile", 390, 844, "mobile_390x844.png"),
            ]
            
            for name, w, h, shot_name in viewports:
                await self.send_cmd("Emulation.setDeviceMetricsOverride", {
                    "width": w,
                    "height": h,
                    "deviceScaleFactor": 1,
                    "mobile": name == "Mobile",
                })
                await self.send_cmd("Emulation.setVisibleSize", {"width": w, "height": h})
                await asyncio.sleep(0.5)
                
                # Check horizontal overflow
                overflow = await self.eval_js("document.documentElement.scrollWidth > window.innerWidth")
                cards_visible = await self.eval_js("document.querySelectorAll('.metric-card').length == 5")
                table_visible = await self.eval_js("!!document.querySelector('.table-responsive')")
                
                shot_path = await self.capture_screenshot(shot_name)
                
                self.record(
                    f"P7_Viewport_{name}_{w}x{h}",
                    "PASS" if not overflow and cards_visible and table_visible else "FAIL",
                    f"No horizontal overflow: {not overflow}, 5 cards visible: {cards_visible}, Table responsive: {table_visible}",
                    f"Screenshot: {shot_path}"
                )
                
            # Reset viewport
            await self.send_cmd("Emulation.clearDeviceMetricsOverride")


async def main():
    runner = BrowserQaRunner()
    try:
        await runner.run()
    finally:
        runner.stop_chrome()
        
    print("\n=== QA AUTOMATION SUMMARY ===")
    total = len(runner.results)
    passed = sum(1 for r in runner.results if r["status"] == "PASS")
    failed = sum(1 for r in runner.results if r["status"] == "FAIL")
    print(f"Total: {total} | Passed: {passed} | Failed: {failed}")
    
    # Save results json
    out_json = os.path.join(SCREENSHOT_DIR, "qa_results.json")
    with open(out_json, "w") as f:
        json.dump(runner.results, f, indent=2)
    print(f"QA report JSON saved to: {out_json}")


if __name__ == "__main__":
    asyncio.run(main())
