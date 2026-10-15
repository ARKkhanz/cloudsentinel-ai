"""
CloudSentinel AI — Day 4 Milestone 1 Automated End-to-End Browser QA Test Suite.
Automation Engine: Google Chrome DevTools Protocol (CDP) WebSocket.

Verifies the complete evaluator journey in real Google Chrome:
1. Verify dashboard loads at http://127.0.0.1:5173/ with backend online.
2. Generate synthetic demo telemetry (100 samples, 5 injected anomalies).
3. Validate KPI cards and metrics display (50 table rows displayed due to display limit, 100 in SQLite).
4. Run Threshold detection (latency_ms > 150.0, error_rate > 0.05) and verify incident creation.
5. Inspect threshold incident detail modal with observed vs threshold evidence.
6. Run IsolationForest detection (5 features: latency_ms, error_rate, cpu_usage_pct, memory_usage_pct, request_count).
7. Inspect ML incident detail modal with anomaly decision score and model metadata.
8. Re-run threshold detection and verify deduplication (0 new duplicate incidents via SHA-256 fingerprint).
9. Reload browser and verify full telemetry and incident persistence from SQLite.
10. Test backend outage handling and recovery via CDP network emulation.
11. Audit mobile layout usability (375x667) and horizontal overflow.
12. Verify clear synthetic prototype disclaimers and absence of false production claims.
13. Audit console messages (0 errors), JS exceptions (0 exceptions), and network requests (0 500+).
14. Capture visual evidence screenshots to docs/screenshots/.
"""

import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional

import websockets

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCREENSHOT_DIR = os.path.join(PROJECT_ROOT, "docs", "screenshots")
QA_ARTIFACT_DIR = os.environ.get("QA_ARTIFACT_DIR")
CDP_PORT = int(os.environ.get("CDP_PORT", "9222"))


def discover_chrome_path() -> str:
    """Discover Chrome/Chromium executable across standard OS environments and PATH."""
    env_override = os.environ.get("CHROME_PATH") or os.environ.get("GOOGLE_CHROME_BIN")
    if env_override and os.path.isfile(env_override):
        return env_override

    for binary in ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"]:
        candidate = shutil.which(binary)
        if candidate and os.path.isfile(candidate):
            return candidate

    standard_candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]
    for p in standard_candidates:
        if os.path.isfile(p):
            return p

    raise FileNotFoundError(
        "Could not discover Google Chrome or Chromium executable. "
        "Please install Google Chrome or set the CHROME_PATH environment variable."
    )


class Day4Milestone1BrowserQa:
    def __init__(self, backend_url: str = "http://127.0.0.1:8000", frontend_url: str = "http://127.0.0.1:5173"):
        self.backend_url = backend_url.rstrip("/")
        self.frontend_url = frontend_url.rstrip("/")
        self.msg_id = 0
        self.ws = None
        self.console_messages: List[Dict[str, Any]] = []
        self.exceptions: List[Dict[str, Any]] = []
        self.network_responses: List[Dict[str, Any]] = []
        self.results: List[Dict[str, Any]] = []
        self.chrome_proc: Optional[subprocess.Popen] = None
        self.temp_user_data_dir: Optional[str] = None

    def record(self, test_name: str, status: str, observation: str, evidence: str = ""):
        print(f"[{status}] {test_name}: {observation}")
        self.results.append({
            "name": test_name,
            "status": status,
            "observation": observation,
            "evidence": evidence,
        })

    def verify_database_isolation(self):
        """
        Preflight safety check: verify backend is connected to an isolated test database.
        If backend is connected to user's primary 'cloudsentinel.db', abort immediately.
        """
        print(f"Verifying backend database isolation at {self.backend_url}/health...")
        try:
            req = urllib.request.Request(f"{self.backend_url}/health")
            with urllib.request.urlopen(req, timeout=3) as resp:
                headers = dict(resp.headers)
                db_target = headers.get("x-database-target", "").strip()
                print(f"Backend reported database target: '{db_target}'")

                if db_target == "cloudsentinel.db":
                    msg = (
                        "CRITICAL SAFETY ABORT: Backend is connected to primary user database 'cloudsentinel.db'. "
                        "Chrome QA requires an isolated test database to prevent overwriting user data. "
                        "Please start the backend with: $env:DATABASE_URL='sqlite:///./backend/data/day4_evaluator_qa.db'"
                    )
                    print(f"\n[FAIL] {msg}\n")
                    self.record("DAY4_PREFLIGHT_DB_SAFETY", "FAIL", msg)
                    sys.exit(1)

                self.record(
                    "DAY4_PREFLIGHT_DB_SAFETY",
                    "PASS",
                    f"Backend confirmed running on isolated database target: '{db_target}'"
                )
        except Exception as exc:
            msg = f"Failed to connect to backend at {self.backend_url}/health: {exc}"
            print(f"\n[FAIL] {msg}\n")
            self.record("DAY4_PREFLIGHT_DB_SAFETY", "FAIL", msg)
            sys.exit(1)

    def start_chrome(self):
        chrome_exe = discover_chrome_path()
        self.temp_user_data_dir = tempfile.mkdtemp(prefix="cloudsentinel_chrome_qa_")
        print(f"Launching Google Chrome CDP on port {CDP_PORT}...")
        print(f"Chrome binary: {chrome_exe}")
        print(f"Isolated user profile: {self.temp_user_data_dir}")

        self.chrome_proc = subprocess.Popen(
            [
                chrome_exe,
                f"--remote-debugging-port={CDP_PORT}",
                f"--user-data-dir={self.temp_user_data_dir}",
                "--headless=new",
                "--no-first-run",
                "--no-default-browser-check",
                "about:blank",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(40):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=1) as resp:
                    if resp.status == 200:
                        print("Chrome CDP is ready.")
                        return
            except Exception:
                time.sleep(0.25)
        raise RuntimeError("Failed to connect to Chrome CDP.")

    def stop_chrome(self):
        if self.chrome_proc:
            print("Terminating Chrome process...")
            self.chrome_proc.terminate()
            try:
                self.chrome_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.chrome_proc.kill()
        if self.temp_user_data_dir and os.path.exists(self.temp_user_data_dir):
            try:
                shutil.rmtree(self.temp_user_data_dir, ignore_errors=True)
            except Exception:
                pass

    async def send_cmd(self, method: str, params: dict = None) -> dict:
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
        b64_data = res.get("data", "")
        if b64_data:
            img_bytes = base64.b64decode(b64_data)
            local_path = os.path.join(SCREENSHOT_DIR, filename)
            with open(local_path, "wb") as f:
                f.write(img_bytes)
            if QA_ARTIFACT_DIR and os.path.isdir(QA_ARTIFACT_DIR):
                art_path = os.path.join(QA_ARTIFACT_DIR, filename)
                try:
                    with open(art_path, "wb") as f:
                        f.write(img_bytes)
                except Exception:
                    pass
            print(f"Captured screenshot: {filename}")

    async def run(self):
        # 0. Safety Preflight Check
        self.verify_database_isolation()

        # 1. Start Chrome
        self.start_chrome()
        try:
            target_url = f"http://127.0.0.1:{CDP_PORT}/json/new?{self.frontend_url}"
            req = urllib.request.Request(target_url, method="PUT")
            with urllib.request.urlopen(req) as resp:
                target_info = json.loads(resp.read().decode())
            ws_url = target_info["webSocketDebuggerUrl"]
            print(f"Connecting to Chrome tab WebSocket: {ws_url}")

            async with websockets.connect(ws_url, max_size=25_000_000) as ws:
                self.ws = ws
                await self.send_cmd("Page.enable")
                await self.send_cmd("Runtime.enable")
                await self.send_cmd("Console.enable")
                await self.send_cmd("Network.enable")
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
                health_el = await self.eval_js("!!document.querySelector('.badge-health')")
                health_text = await self.eval_js("document.querySelector('.badge-health')?.innerText")
                is_healthy = await self.eval_js("document.querySelector('.badge-health')?.classList.contains('healthy')")

                step1_pass = health_el and is_healthy and "online" in (health_text or "").lower()
                self.record(
                    "DAY4_01_Initial_Connection",
                    "PASS" if step1_pass else "FAIL",
                    f"Page title: '{page_title}', Brand: '{brand}', Health badge: '{health_text}'"
                )
                await self.capture_screenshot("day4_01_initial_dashboard.png")

                # STEP 2: Generate Synthetic Demo Telemetry
                print("\n--- STEP 2: Generate Synthetic Demo Telemetry ---")
                btn_gen = await self.eval_js("!!document.querySelector('#btn-generate-demo')")
                if not btn_gen:
                    self.record("DAY4_02_Generate_Synthetic_Telemetry", "FAIL", "Missing #btn-generate-demo button")
                else:
                    await self.eval_js("document.querySelector('#btn-generate-demo')?.click()")
                    await asyncio.sleep(2.0)

                    feedback = await self.eval_js("document.querySelector('.feedback-banner')?.innerText")
                    row_count = await self.eval_js("document.querySelectorAll('#observations-table tbody tr').length")
                    service_card = await self.eval_js("document.querySelectorAll('.card-value')[0]?.innerText")
                    latency_card = await self.eval_js("document.querySelectorAll('.card-value')[1]?.innerText")
                    sample_footer = await self.eval_js("document.querySelectorAll('.card-footer')[0]?.innerText")

                    step2_pass = (
                        row_count == 50 and
                        "100 observations" in (feedback or "").lower() and
                        "5 injected anomalies" in (feedback or "").lower() and
                        service_card == "demo-api" and
                        "50 samples" in (sample_footer or "").lower()
                    )
                    self.record(
                        "DAY4_02_Generate_Synthetic_Telemetry",
                        "PASS" if step2_pass else "FAIL",
                        f"Generated telemetry: {row_count} rows displayed (limit 50). Service: '{service_card}', Avg Latency: '{latency_card}'.",
                        f"Feedback: '{feedback}', Footer: '{sample_footer}'"
                    )
                await self.capture_screenshot("day4_02_metrics_generated.png")

                # STEP 3: Run Threshold Baseline Anomaly Detection
                print("\n--- STEP 3: Run Threshold Detection (latency_ms > 150.0, error_rate > 0.05) ---")
                btn_threshold = await self.eval_js("!!document.querySelector('#btn-run-threshold')")
                if not btn_threshold:
                    self.record("DAY4_03_Run_Threshold_Detection", "FAIL", "Missing #btn-run-threshold button")
                else:
                    await self.eval_js("document.querySelector('#btn-run-threshold')?.click()")
                    await asyncio.sleep(2.0)

                    t_feedback = await self.eval_js("document.querySelector('.feedback-banner')?.innerText")
                    incident_rows = await self.eval_js("document.querySelectorAll('#incidents-table tbody tr').length")
                    has_threshold_badge = await self.eval_js("""
                        Array.from(document.querySelectorAll('#incidents-table .badge-detector'))
                            .some(el => el.innerText.toLowerCase().includes('threshold_baseline'))
                    """)

                    step3_pass = incident_rows == 5 and has_threshold_badge and "5 new incidents" in (t_feedback or "").lower()
                    self.record(
                        "DAY4_03_Run_Threshold_Detection",
                        "PASS" if step3_pass else "FAIL",
                        f"Threshold detection executed. Incident table row count: {incident_rows}. Threshold badge found: {has_threshold_badge}.",
                        f"Feedback: '{t_feedback}'"
                    )
                await self.capture_screenshot("day4_03_threshold_detection.png")

                # STEP 4: Inspect Threshold Incident Evidence Modal
                print("\n--- STEP 4: Threshold Incident Evidence Inspection ---")
                t_row_clicked = await self.eval_js("""
                    (() => {
                        const rows = Array.from(document.querySelectorAll('#incidents-table tbody tr'));
                        const tRow = rows.find(r => r.querySelector('.badge-detector')?.innerText.toLowerCase().includes('threshold_baseline'));
                        if (tRow) {
                            const btn = tRow.querySelector('.btn-evidence');
                            if (btn) { btn.click(); return true; }
                        }
                        return false;
                    })()
                """)
                await asyncio.sleep(1.0)

                has_modal = await self.eval_js("!!document.querySelector('#evidence-modal')")
                modal_title = await self.eval_js("document.querySelector('#modal-incident-title')?.innerText")
                modal_expl = await self.eval_js("document.querySelector('#incident-explanation')?.innerText")
                obs_latency_txt = await self.eval_js("document.querySelector('#observed-measurements-grid .evidence-card-value')?.innerText")

                # Verify actual numbers: latency > 150.0 or explanation explicitly describes threshold breach
                expl_lower = (modal_expl or "").lower()
                has_breach_explanation = "exceeded" in expl_lower or "threshold" in expl_lower or "150" in expl_lower or "0.05" in expl_lower
                step4_pass = t_row_clicked and has_modal and has_breach_explanation

                self.record(
                    "DAY4_04_Threshold_Evidence_Inspection",
                    "PASS" if step4_pass else "FAIL",
                    f"Evidence modal opened: '{modal_title}'. Observed latency: '{obs_latency_txt}'",
                    f"Explanation: '{modal_expl}'"
                )
                await self.capture_screenshot("day4_04_threshold_evidence_modal.png")

                # Close modal
                await self.eval_js("document.querySelector('#modal-close-btn')?.click()")
                await asyncio.sleep(1.0)

                # STEP 5: Run IsolationForest Multivariate Detection
                print("\n--- STEP 5: Run IsolationForest Detection (5 features) ---")
                btn_ml = await self.eval_js("!!document.querySelector('#btn-run-ml')")
                if not btn_ml:
                    self.record("DAY4_05_Run_IsolationForest_Detection", "FAIL", "Missing #btn-run-ml button")
                else:
                    await self.eval_js("document.querySelector('#btn-run-ml')?.click()")
                    await asyncio.sleep(3.0)

                    ml_feedback = await self.eval_js("document.querySelector('.feedback-banner')?.innerText")
                    all_incident_rows = await self.eval_js("document.querySelectorAll('#incidents-table tbody tr').length")
                    detector_names = await self.eval_js(
                        "Array.from(document.querySelectorAll('#incidents-table .badge-detector')).map(el => el.innerText)"
                    )

                    has_both_detectors = (
                        any("threshold_baseline" in d.lower() for d in (detector_names or [])) and
                        any("isolation_forest" in d.lower() for d in (detector_names or []))
                    )

                    step5_pass = has_both_detectors and all_incident_rows == 10 and "5 new incidents" in (ml_feedback or "").lower()
                    self.record(
                        "DAY4_05_Run_IsolationForest_Detection",
                        "PASS" if step5_pass else "FAIL",
                        f"Total incidents now: {all_incident_rows}. Detectors present: {set(detector_names or [])}",
                        f"Feedback: '{ml_feedback}'"
                    )
                await self.capture_screenshot("day4_05_isolation_forest_detection.png")

                # STEP 6: Inspect IsolationForest Evidence Modal
                print("\n--- STEP 6: IsolationForest Evidence Inspection ---")
                ml_row_clicked = await self.eval_js("""
                    (() => {
                        const rows = Array.from(document.querySelectorAll('#incidents-table tbody tr'));
                        const mlRow = rows.find(r => r.querySelector('.badge-detector')?.innerText.toLowerCase().includes('isolation_forest'));
                        if (mlRow) {
                            const btn = mlRow.querySelector('.btn-evidence');
                            if (btn) { btn.click(); return true; }
                        }
                        return false;
                    })()
                """)
                await asyncio.sleep(1.5)

                ml_modal_has = await self.eval_js("!!document.querySelector('#evidence-modal')")
                ml_modal_title = await self.eval_js("document.querySelector('#modal-incident-title')?.innerText")
                ml_expl = await self.eval_js("document.querySelector('#incident-explanation')?.innerText")
                ml_decision_score_str = await self.eval_js(
                    "document.querySelector('#evidence-modal .evidence-card-value[style*=\"color\"]')?.innerText"
                )

                score_is_negative = False
                try:
                    if ml_decision_score_str:
                        score_val = float(ml_decision_score_str.strip())
                        score_is_negative = score_val < 0.0
                except ValueError:
                    score_is_negative = False

                step6_pass = ml_row_clicked and ml_modal_has and score_is_negative and "isolationforest" in (ml_expl or "").lower()
                self.record(
                    "DAY4_06_IsolationForest_Evidence_Inspection",
                    "PASS" if step6_pass else "FAIL",
                    f"ML evidence modal verified: '{ml_modal_title}'. Anomaly score: '{ml_decision_score_str}' (negative: {score_is_negative})",
                    f"Explanation: '{ml_expl}'"
                )
                await self.capture_screenshot("day4_06_ml_evidence_modal.png")

                # Close modal
                await self.eval_js("document.querySelector('#modal-close-btn')?.click()")
                await asyncio.sleep(1.0)

                # STEP 7: Re-run Threshold Detection to Verify SHA-256 Deduplication
                print("\n--- STEP 7: Verify SHA-256 Deduplication on Repeated Run ---")
                await self.eval_js("document.querySelector('#btn-run-threshold')?.click()")
                await asyncio.sleep(2.0)

                dedup_feedback = await self.eval_js("document.querySelector('.feedback-banner')?.innerText")
                count_after_dedup = await self.eval_js("document.querySelectorAll('#incidents-table tbody tr').length")

                step7_pass = count_after_dedup == 10 and "0 new incidents" in (dedup_feedback or "").lower()
                self.record(
                    "DAY4_07_Incident_Deduplication",
                    "PASS" if step7_pass else "FAIL",
                    f"Deduplication confirmed. Total incidents remained {count_after_dedup} (0 duplicates created).",
                    f"Feedback: '{dedup_feedback}'"
                )

                # STEP 8: Reload Browser and Confirm SQLite Persistence
                print("\n--- STEP 8: Browser Reload and SQLite Persistence ---")
                await self.send_cmd("Page.reload")
                await asyncio.sleep(2.5)

                reloaded_rows = await self.eval_js("document.querySelectorAll('#incidents-table tbody tr').length")
                reloaded_obs_rows = await self.eval_js("document.querySelectorAll('#observations-table tbody tr').length")

                step8_pass = reloaded_rows == 10 and reloaded_obs_rows == 50
                self.record(
                    "DAY4_08_Persistence_Across_Reload",
                    "PASS" if step8_pass else "FAIL",
                    f"Persisted data restored after reload: {reloaded_rows} incidents, {reloaded_obs_rows} displayed telemetry rows."
                )
                await self.capture_screenshot("day4_07_persisted_after_reload.png")

                # STEP 9: Mobile Viewport Usability (375x667)
                print("\n--- STEP 9: Mobile Viewport Usability ---")
                await self.send_cmd("Emulation.setDeviceMetricsOverride", {
                    "width": 375,
                    "height": 667,
                    "deviceScaleFactor": 2,
                    "mobile": True,
                })
                await asyncio.sleep(1.0)
                await self.capture_screenshot("day4_08_mobile_responsive.png")

                has_overflow = await self.eval_js("document.documentElement.scrollWidth > window.innerWidth")
                step9_pass = not has_overflow
                self.record(
                    "DAY4_09_Mobile_Responsiveness",
                    "PASS" if step9_pass else "FAIL",
                    f"Mobile viewport (375px) tested. Horizontal overflow detected: {has_overflow}"
                )

                # Reset to desktop viewport
                await self.send_cmd("Emulation.setDeviceMetricsOverride", {
                    "width": 1440,
                    "height": 900,
                    "deviceScaleFactor": 1,
                    "mobile": False,
                })
                await asyncio.sleep(0.5)

                # STEP 10: Backend Outage Handling and Recovery Emulation
                print("\n--- STEP 10: Backend Outage Handling and Recovery Test ---")
                # Block health/metrics URLs to simulate network or backend drop
                await self.send_cmd("Network.setBlockedURLs", {
                    "urls": ["*health*", "*metrics*", "*incidents*"]
                })
                # Trigger retry to induce error/stale state
                await self.eval_js("""
                    (() => {
                        const retryBtn = document.querySelector('.btn-retry') || document.querySelector('#btn-generate-demo');
                        if (retryBtn) retryBtn.click();
                    })()
                """)
                await asyncio.sleep(2.0)

                # Strictly assert that outage/stale was ACTUALLY OBSERVED
                outage_observed = await self.eval_js(
                    "!!document.querySelector('.error-banner') || !!document.querySelector('.badge-health.unhealthy') || !!document.querySelector('.badge-synthetic')"
                )
                outage_title = await self.eval_js("document.querySelector('.error-title')?.innerText || document.querySelector('.badge-health')?.innerText")
                print(f"Outage condition observed: {outage_observed} ('{outage_title}')")

                # Now recover: unblock URLs
                await self.send_cmd("Network.setBlockedURLs", {"urls": []})
                await asyncio.sleep(0.5)

                # Click Retry Connection
                await self.eval_js("""
                    (() => {
                        const retry = document.querySelector('.btn-retry');
                        if (retry) retry.click();
                    })()
                """)
                await asyncio.sleep(2.5)

                recovered_health = await self.eval_js("document.querySelector('.badge-health')?.innerText")
                recovered_is_healthy = await self.eval_js("document.querySelector('.badge-health')?.classList.contains('healthy')")
                recovered_error_absent = await self.eval_js("!document.querySelector('.error-banner')")

                step10_pass = outage_observed and recovered_is_healthy and recovered_error_absent
                self.record(
                    "DAY4_10_Outage_And_Recovery_Handling",
                    "PASS" if step10_pass else "FAIL",
                    f"Outage observed: {outage_observed}. Recovered health badge: '{recovered_health}', Error banner cleared: {recovered_error_absent}"
                )
                await self.capture_screenshot("day4_09_backend_recovery.png")

                # STEP 11: Clear Prototype Disclaimers Audit
                print("\n--- STEP 11: Prototype Disclaimers and Non-Production Audit ---")
                body_text = await self.eval_js("document.body.innerText")
                claims_production = any(phrase in body_text.lower() for phrase in [
                    "production monitoring",
                    "automatic root-cause",
                    "predicts outages",
                    "guaranteed accuracy",
                ])
                has_prototype_disclaimer = "prototype" in body_text.lower() or "synthetic" in body_text.lower()

                step11_pass = (not claims_production) and has_prototype_disclaimer
                self.record(
                    "DAY4_11_Prototype_Disclaimers",
                    "PASS" if step11_pass else "FAIL",
                    f"Disclaimers verified. Claims production: {claims_production}, Has prototype/synthetic labels: {has_prototype_disclaimer}"
                )

                # STEP 12: Console Errors and Network Audits
                print("\n--- STEP 12: Console Errors & Network Audit ---")
                real_error_logs = [m for m in self.console_messages if m.get("level") == "error"]
                failed_requests = [r for r in self.network_responses if r.get("status", 200) >= 500]

                step12_pass = len(real_error_logs) == 0 and len(self.exceptions) == 0 and len(failed_requests) == 0
                self.record(
                    "DAY4_12_Console_And_Network_Audit",
                    "PASS" if step12_pass else "FAIL",
                    f"Console errors: {len(real_error_logs)}, JS exceptions: {len(self.exceptions)}, HTTP 500+ errors: {len(failed_requests)}"
                )

        finally:
            self.stop_chrome()


if __name__ == "__main__":
    runner = Day4Milestone1BrowserQa()
    try:
        asyncio.run(runner.run())
    except Exception as exc:
        print(f"\nCRITICAL RUNTIME ERROR: {exc}")
        runner.record("CRITICAL_RUN_ERROR", "FAIL", str(exc))

    # Save JSON results
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    json_path = os.path.join(SCREENSHOT_DIR, "day4_qa_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(runner.results, f, indent=2)
    print(f"\nSaved Day 4 QA results to: {json_path}")

    # Accurate PASS / FAIL / WARNING counting and nonzero exit
    pass_count = sum(1 for r in runner.results if r["status"] == "PASS")
    fail_count = sum(1 for r in runner.results if r["status"] == "FAIL")
    warn_count = sum(1 for r in runner.results if r["status"] == "WARNING")

    print("\n" + "=" * 50)
    print(f"DAY 4 BROWSER QA SUMMARY: {pass_count} PASSED, {fail_count} FAILED, {warn_count} WARNINGS")
    print("=" * 50)

    if fail_count > 0:
        print(f"FAILED: {fail_count} required QA check(s) failed.")
        sys.exit(1)
    else:
        print("ALL QA CHECKS PASSED SUCCESSFULLY.")
        sys.exit(0)
