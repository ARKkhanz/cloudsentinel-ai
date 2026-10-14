"""
CloudSentinel AI — Milestone 5 Automated Browser QA Test Suite via Chrome DevTools Protocol (CDP).

Executes the complete user journey in real Google Chrome (v141):
1. Connect to live dashboard at http://127.0.0.1:5173/
2. Confirm healthy FastAPI connection.
3. Click 'Generate Synthetic Data' (100 samples with 3 latency spikes and 2 error spikes).
4. Verify metrics display in KPI cards and observations table.
5. Click 'Run Threshold Detection' and verify threshold incidents appear.
6. Open threshold evidence modal and inspect numerical evidence.
7. Click 'Run IsolationForest Detection' and verify multivariate ML incidents appear.
8. Open ML evidence modal and inspect anomaly decision score.
9. Re-run threshold detection and verify deduplication.
10. Reload browser and verify persistence from SQLite.
11. Audit console messages, network responses, and responsive viewports.
12. Capture screenshots for visual QA proof.
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

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9222
TEMP_USER_DATA = os.path.join(os.environ.get("TEMP", r"C:\Temp"), "cloudsentinel_m5_cdp")
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCREENSHOT_DIR = os.path.join(PROJECT_ROOT, "docs", "screenshots")
ARTIFACT_DIR = r"C:\Users\USER\.gemini\antigravity-ide\brain\6d7dfa2b-f416-4292-81b1-442323a893ba"


class Milestone5BrowserQa:
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
            "evidence": evidence,
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
        return result.get("result", {}).get("value")

    async def capture_screenshot(self, filename: str):
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        res = await self.send_cmd("Page.captureScreenshot", {"format": "png"})
        img_bytes = base64.b64decode(res["data"])

        # Save to docs/screenshots
        filepath = os.path.join(SCREENSHOT_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(img_bytes)

        # Also copy to artifacts directory for direct UI rendering
        if os.path.exists(ARTIFACT_DIR):
            artifact_file = os.path.join(ARTIFACT_DIR, filename)
            with open(artifact_file, "wb") as f:
                f.write(img_bytes)

        rel_path = os.path.relpath(filepath, PROJECT_ROOT).replace("\\", "/")
        print(f"Captured screenshot: {rel_path} ({len(img_bytes):,} bytes)")
        return rel_path

    async def run(self):
        self.start_chrome()

        target_url = f"http://127.0.0.1:{CDP_PORT}/json/new?http://127.0.0.1:5173"
        req = urllib.request.Request(target_url, method="PUT")
        with urllib.request.urlopen(req) as resp:
            target_info = json.loads(resp.read().decode())
        ws_url = target_info["webSocketDebuggerUrl"]
        print(f"Connecting to Chrome tab WebSocket: {ws_url}")

        async with websockets.connect(ws_url) as ws:
            self.ws = ws

            await self.send_cmd("Page.enable")
            await self.send_cmd("Runtime.enable")
            await self.send_cmd("Console.enable")
            await self.send_cmd("Network.enable")

            # Set 1440x900 desktop viewport
            await self.send_cmd("Emulation.setDeviceMetricsOverride", {
                "width": 1440,
                "height": 900,
                "deviceScaleFactor": 1,
                "mobile": False,
            })

            # STEP 1: Verify Initial Render & Connection
            print("\n--- STEP 1: Initial Render & Connection ---")
            await asyncio.sleep(2.0)
            page_title = await self.eval_js("document.title")
            brand = await self.eval_js("document.querySelector('.brand-title')?.innerText")
            health_text = await self.eval_js("document.querySelector('.badge-health')?.innerText")
            is_healthy = await self.eval_js("document.querySelector('.badge-health')?.classList.contains('healthy')")

            self.record(
                "M5_01_Initial_Connection",
                "PASS" if is_healthy and "online" in (health_text or "").lower() else "FAIL",
                f"Page title: '{page_title}', Health badge: '{health_text}'"
            )
            await self.capture_screenshot("milestone5_01_initial_state.png")

            # STEP 2: Generate Synthetic Telemetry with Anomalies
            print("\n--- STEP 2: Generate Synthetic Demo Telemetry ---")
            await self.eval_js("document.querySelector('#btn-generate-demo')?.click()")
            await asyncio.sleep(2.0)

            feedback = await self.eval_js("document.querySelector('.feedback-banner')?.innerText")
            row_count = await self.eval_js("document.querySelectorAll('#observations-table tbody tr').length")
            total_reqs = await self.eval_js("document.querySelectorAll('.card-value')[3]?.innerText")

            self.record(
                "M5_02_Generate_Synthetic_Telemetry",
                "PASS" if row_count > 0 and "successfully generated" in (feedback or "").lower() else "FAIL",
                f"Generated telemetry: {row_count} table rows displayed. Feedback: '{feedback}'",
                f"Total requests: {total_reqs}"
            )
            await self.capture_screenshot("milestone5_02_metrics_generated.png")

            # STEP 3: Run Threshold Anomaly Detection
            print("\n--- STEP 3: Run Threshold Detection ---")
            await self.eval_js("document.querySelector('#btn-run-threshold')?.click()")
            await asyncio.sleep(2.0)

            t_feedback = await self.eval_js("document.querySelector('.feedback-banner')?.innerText")
            incident_rows = await self.eval_js("document.querySelectorAll('#incidents-table tbody tr').length")
            t_detector_badge = await self.eval_js("document.querySelector('#incidents-table .badge-detector')?.innerText")

            self.record(
                "M5_03_Run_Threshold_Detection",
                "PASS" if incident_rows >= 3 and "threshold" in (t_detector_badge or "").lower() else "FAIL",
                f"Created {incident_rows} threshold incidents. Feedback: '{t_feedback}'",
                f"Detector badge: '{t_detector_badge}'"
            )
            await self.capture_screenshot("milestone5_03_threshold_incidents.png")

            # STEP 4: Inspect Threshold Incident Evidence Modal
            print("\n--- STEP 4: Threshold Incident Evidence Inspection ---")
            await self.eval_js("document.querySelector('#incidents-table .btn-evidence')?.click()")
            await asyncio.sleep(1.0)

            has_modal = await self.eval_js("!!document.querySelector('#evidence-modal')")
            modal_title = await self.eval_js("document.querySelector('#modal-incident-title')?.innerText")
            modal_expl = await self.eval_js("document.querySelector('#incident-explanation')?.innerText")
            obs_measurements = await self.eval_js(
                "Array.from(document.querySelectorAll('#observed-measurements-grid .evidence-card-value')).map(el => el.innerText)"
            )

            self.record(
                "M5_04_Threshold_Evidence_Inspection",
                "PASS" if has_modal and "exceeded" in (modal_expl or "").lower() else "FAIL",
                f"Evidence modal opened: '{modal_title}'",
                f"Explanation: '{modal_expl}'. Measurements: {obs_measurements}"
            )
            await self.capture_screenshot("milestone5_04_threshold_evidence_modal.png")

            # Close modal
            await self.eval_js("document.querySelector('#modal-close-btn')?.click()")
            await asyncio.sleep(0.5)

            # STEP 5: Run IsolationForest Detection
            print("\n--- STEP 5: Run IsolationForest Detection ---")
            await self.eval_js("document.querySelector('#btn-run-ml')?.click()")
            await asyncio.sleep(2.5)

            ml_feedback = await self.eval_js("document.querySelector('.feedback-banner')?.innerText")
            all_incident_rows = await self.eval_js("document.querySelectorAll('#incidents-table tbody tr').length")
            detector_names = await self.eval_js(
                "Array.from(document.querySelectorAll('#incidents-table .badge-detector')).map(el => el.innerText)"
            )

            has_both_detectors = (
                any("threshold_baseline" in d.lower() for d in (detector_names or [])) and
                any("isolation_forest" in d.lower() for d in (detector_names or []))
            )

            self.record(
                "M5_05_Run_IsolationForest_Detection",
                "PASS" if has_both_detectors else "FAIL",
                f"Total incidents now: {all_incident_rows}. Detectors present: {set(detector_names or [])}",
                f"Feedback: '{ml_feedback}'"
            )

            # STEP 6: Inspect IsolationForest Evidence Modal
            print("\n--- STEP 6: IsolationForest Evidence Inspection ---")
            # Click evidence button on the first isolation_forest incident
            await self.eval_js("""
                const rows = Array.from(document.querySelectorAll('#incidents-table tbody tr'));
                const mlRow = rows.find(r => r.querySelector('.badge-detector')?.innerText.toLowerCase().includes('isolation_forest'));
                if (mlRow) mlRow.querySelector('.btn-evidence')?.click();
            """)
            await asyncio.sleep(1.0)

            ml_modal_title = await self.eval_js("document.querySelector('#modal-incident-title')?.innerText")
            ml_modal_expl = await self.eval_js("document.querySelector('#incident-explanation')?.innerText")
            ml_score = await self.eval_js("document.querySelector('#evidence-modal .evidence-card-value[style*=\"color\"]')?.innerText")

            self.record(
                "M5_06_ML_Evidence_Inspection",
                "PASS" if ml_score and "-" in ml_score else "FAIL",
                f"ML evidence modal opened: '{ml_modal_title}'",
                f"IsolationForest Decision Score: '{ml_score}'. Explanation: '{ml_modal_expl}'"
            )
            await self.capture_screenshot("milestone5_05_ml_evidence_modal.png")

            # Close modal
            await self.eval_js("document.querySelector('#modal-close-btn')?.click()")
            await asyncio.sleep(0.5)

            # STEP 7: Test Duplicate Prevention (Deduplication)
            print("\n--- STEP 7: Deduplication Verification ---")
            await self.eval_js("document.querySelector('#btn-run-threshold')?.click()")
            await asyncio.sleep(1.5)

            dedup_feedback = await self.eval_js("document.querySelector('.feedback-banner')?.innerText")
            after_dedup_rows = await self.eval_js("document.querySelectorAll('#incidents-table tbody tr').length")

            self.record(
                "M5_07_Deduplication_Prevention",
                "PASS" if "0 new incidents created" in (dedup_feedback or "") and after_dedup_rows == all_incident_rows else "FAIL",
                f"Deduplication confirmed. Total rows remained: {after_dedup_rows}",
                f"Feedback: '{dedup_feedback}'"
            )

            # STEP 8: Browser Page Reload Persistence Verification
            print("\n--- STEP 8: Browser Reload State Persistence ---")
            await self.send_cmd("Page.reload")
            await asyncio.sleep(2.5)

            reloaded_incidents = await self.eval_js("document.querySelectorAll('#incidents-table tbody tr').length")
            reloaded_samples = await self.eval_js("document.querySelectorAll('#observations-table tbody tr').length")

            self.record(
                "M5_08_Reload_State_Persistence",
                "PASS" if reloaded_incidents == after_dedup_rows and reloaded_samples > 0 else "FAIL",
                f"State persisted after browser reload: {reloaded_incidents} incidents, {reloaded_samples} metric samples."
            )

            # STEP 9: Mobile Viewport & Responsiveness
            print("\n--- STEP 9: Mobile Viewport Responsiveness ---")
            await self.send_cmd("Emulation.setDeviceMetricsOverride", {
                "width": 390,
                "height": 844,
                "deviceScaleFactor": 2,
                "mobile": True,
            })
            await asyncio.sleep(1.0)

            is_overflowing = await self.eval_js("document.body.scrollWidth > window.innerWidth")
            self.record(
                "M5_09_Mobile_Viewport_390x844",
                "PASS" if not is_overflowing else "FAIL",
                "Mobile layout inspected without horizontal overflow.",
                f"scrollWidth <= innerWidth: {not is_overflowing}"
            )
            await self.capture_screenshot("milestone5_06_mobile_responsive.png")

            # Restore desktop viewport
            await self.send_cmd("Emulation.setDeviceMetricsOverride", {
                "width": 1440,
                "height": 900,
                "deviceScaleFactor": 1,
                "mobile": False,
            })
            await asyncio.sleep(0.5)
            await self.capture_screenshot("milestone5_07_full_dashboard.png")

            # STEP 10: Console Errors & Network Audit
            print("\n--- STEP 10: Console Errors & Network Audit ---")
            error_logs = [m for m in self.console_messages if m.get("level") == "error"]
            failed_requests = [r for r in self.network_responses if r.get("status", 200) >= 400]

            self.record(
                "M5_10_Console_Zero_Errors",
                "PASS" if len(error_logs) == 0 else "FAIL",
                f"Audited browser console: {len(error_logs)} error logs found."
            )
            self.record(
                "M5_11_Network_Healthy_Responses",
                "PASS" if len(failed_requests) == 0 else "FAIL",
                f"Network audit: {len(failed_requests)} failed requests out of {len(self.network_responses)} total."
            )

        self.stop_chrome()
        self.generate_report()

    def generate_report(self):
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")

        print("\n" + "=" * 60)
        print(f"MILESTONE 5 BROWSER QA SUMMARY: {passed}/{total} PASSED ({failed} FAILED)")
        print("=" * 60)

        report_md = f"""# CloudSentinel AI — Milestone 5 Automated Browser QA Verification Report

**Execution Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}  
**Target URL:** [http://127.0.0.1:5173/](http://127.0.0.1:5173/)  
**Backend API:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)  
**Browser Engine:** Google Chrome v141 Headless via native Chrome DevTools Protocol (CDP over WebSockets)  
**Total Tests:** {total}  
**Passed:** **{passed}** ({passed/total*100:.1f}%)  
**Failed:** **{failed}**  

---

## Verification Matrix

| Test ID | Status | Observation | Evidence |
| :--- | :---: | :--- | :--- |
"""
        for r in self.results:
            report_md += f"| **{r['name']}** | **{r['status']}** | {r['observation']} | {r['evidence']} |\n"

        report_md += """
---

## Visual Verification Artifacts

1. `milestone5_01_initial_state.png` — Initial clean dashboard state connected to FastAPI.
2. `milestone5_02_metrics_generated.png` — Dashboard populated with 100 observations after synthetic data generation.
3. `milestone5_03_threshold_incidents.png` — Detected Incidents table displaying threshold baseline findings.
4. `milestone5_04_threshold_evidence_modal.png` — Threshold incident evidence modal showing factual measurements vs rules.
5. `milestone5_05_ml_evidence_modal.png` — IsolationForest evidence modal showing decision score, classification label, and baseline model metadata.
6. `milestone5_06_mobile_responsive.png` — Mobile viewport (390×844) responsive rendering.
7. `milestone5_07_full_dashboard.png` — Final persistent state showing both detector findings surviving reloads.
"""
        report_path = os.path.join(PROJECT_ROOT, "docs", "milestone5_browser_qa_report.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_md)
        print(f"Saved QA report to {report_path}")

        # Also save to brain artifact directory
        artifact_report = os.path.join(ARTIFACT_DIR, "milestone5_browser_qa_report.md")
        with open(artifact_report, "w", encoding="utf-8") as f:
            f.write(report_md)


if __name__ == "__main__":
    runner = Milestone5BrowserQa()
    asyncio.run(runner.run())
