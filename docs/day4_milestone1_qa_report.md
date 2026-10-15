# CloudSentinel AI — Day 4 Milestone 1 Automated End-to-End QA Report

**Verification Date:** 2026-10-15 17:39:50 UTC  
**Target Milestone:** Day 4 Milestone 1 — Final End-to-End Evaluator Verification Journey  
**Execution Mode:** Google Chrome DevTools Protocol (CDP) WebSocket Automation  
**Target Service URL:** `http://127.0.0.1:5173/` (Vite dev server)  
**Backend API URL:** `http://127.0.0.1:8000/` (FastAPI ASGI Uvicorn service)  
**Disposable Database Target:** `./backend/data/day4_evaluator_qa.db` (Cleanly isolated and removed post-test)

---

## 1. System Environment & Tool Versions

| Tool / Runtime | Version | Scope / Notes |
| :--- | :--- | :--- |
| **Operating System** | Windows 11 Pro (win32) | Workstation host environment |
| **Python** | 3.11.9 (in `backend/.venv`) | Backend FastAPI, Scikit-Learn, Pytest |
| **Node.js** | v24.19.0 | Frontend build toolchain & ESLint |
| **npm** | 11.17.0 | Frontend dependency manager |
| **Google Chrome** | 141+ (detected via `discover_chrome_path()`) | Headless browser for automated CDP QA |
| **Docker** | Uninstalled locally | Docker containerization verified via GitHub Actions cloud runner |

---

## 2. User Data Protection & Database Isolation Policy

In strict accordance with Phase 3 requirements, existing user data in `backend/data/cloudsentinel.db` was protected:
1. **Preflight Safety Enforcement (`DAY4_PREFLIGHT_DB_SAFETY`)**: The QA script checks `GET /health`'s `x-database-target` response header before running state-changing operations. If the backend is running against `cloudsentinel.db`, the script aborts immediately with code 1 and prints an explicit error.
2. **Isolated Database URI**: The QA backend was started with an isolated disposable database:
   `$env:DATABASE_URL="sqlite:///./backend/data/day4_evaluator_qa.db"`
3. **Untouched Primary Database**: `cloudsentinel.db` retained its original modification timestamp (`2026-10-14 19:03:10`) and size (`102,400 bytes`). Zero production/user data was overwritten or modified.
4. **Safe Teardown**: `./backend/data/day4_evaluator_qa.db` and its journal files were safely deleted after the QA execution completed.

---

## 3. Automated Chrome CDP Test Results (13/13 PASSED)

| Step # | Test Identifier | Status | Observation | Evidence / Response Details |
| :---: | :--- | :---: | :--- | :--- |
| **Pre** | `DAY4_PREFLIGHT_DB_SAFETY` | **PASS** | Preflight safety verified; backend confirmed running on isolated database. | `x-database-target: day4_evaluator_qa.db`<br>Primary database protected. |
| **1** | `DAY4_01_Initial_Connection` | **PASS** | Dashboard rendered cleanly; backend online badge verified. | Page Title: `CloudSentinel AI — Reliability Dashboard`<br>Badge: `BACKEND: ONLINE (CLOUDSENTINEL-BACKEND V0.1.0)` |
| **2** | `DAY4_02_Generate_Synthetic_Telemetry` | **PASS** | Clicked `#btn-generate-demo`; generated 100 samples with 5 anomalies. | Feedback: `"Successfully generated and persisted 100 observations with 5 injected anomalies for 'demo-api'."`<br>Table: 50 rows displayed (display limit). Footer: `50 samples (descending)`. |
| **3** | `DAY4_03_Run_Threshold_Detection` | **PASS** | Clicked `#btn-run-threshold`; created 5 threshold incident records. | Incident Table: 5 rows.<br>Badge: `THRESHOLD_BASELINE` (v1.0.0).<br>Rules: `latency_ms > 150.0`, `error_rate > 0.05`. |
| **4** | `DAY4_04_Threshold_Evidence_Inspection` | **PASS** | Opened modal for threshold incident; verified observed vs rule comparison. | Modal Title: `"High Error Rate on demo-api (16.2%)"` / `"Elevated Latency on demo-api"`<br>Condition: Observed metric values compared against threshold rules. |
| **5** | `DAY4_05_Run_IsolationForest_Detection` | **PASS** | Clicked `#btn-run-ml`; executed Scikit-Learn detector; incidents reached 10. | Incident Table: 10 total rows.<br>Detectors present: `THRESHOLD_BASELINE` and `ISOLATION_FOREST`. |
| **6** | `DAY4_06_IsolationForest_Evidence_Inspection` | **PASS** | Opened modal for ML incident; verified decision score and model parameters. | Modal Title: `"Multivariate Anomaly Detected by IsolationForest on demo-api (score: -0.0011)"`<br>Decision Score: `-0.0011` (negative float verified).<br>Parameters: `contamination=0.05`, `n_estimators=100`, 5 features evaluated. |
| **7** | `DAY4_07_Incident_Deduplication` | **PASS** | Re-ran threshold detection; confirmed zero duplicate incidents created. | Feedback: `"Threshold detection complete for 'demo-api': 0 new incidents created (5 duplicates suppressed)."`<br>Total incidents remained exactly 10. |
| **8** | `DAY4_08_Persistence_Across_Reload` | **PASS** | Executed `Page.reload`; confirmed full state restore from SQLite. | Reloaded state: 10 incidents intact, 50 telemetry rows displayed, KPI summary cards accurate. |
| **9** | `DAY4_09_Mobile_Responsiveness` | **PASS** | Emulated mobile viewport (375x667, 2x scale); verified responsive layout. | Horizontal overflow check: `document.documentElement.scrollWidth <= window.innerWidth` returned `True` (zero horizontal overflow). |
| **10** | `DAY4_10_Outage_And_Recovery_Handling` | **PASS** | Blocked network requests via CDP; verified stale/error banner; unblocked and recovered. | Outage condition strictly observed (`has_error_or_stale=True`). Upon unblocking and clicking retry, health badge returned to `online` and error banner cleared. |
| **11** | `DAY4_11_Prototype_Disclaimers` | **PASS** | Audited DOM text for production claims vs prototype disclaimers. | Zero false claims of "production monitoring", "automatic root-cause", or "predicts outages". Clear prototype and synthetic notices present. |
| **12** | `DAY4_12_Console_And_Network_Audit` | **PASS** | Audited browser console and network responses. | Real Console Errors: `0`<br>Uncaught JS Exceptions: `0`<br>Unexpected HTTP 500+ Failures: `0`. |

---

## 4. Negative Test & Exit Code Verification

To ensure that the QA suite fails correctly and cannot report false passes:
1. **Targeted Negative Test (Backend Refused)**: Executing `backend/tests/day4_milestone1_browser_qa.py` while the backend is offline caused immediate abort during preflight, recording `[FAIL] DAY4_PREFLIGHT_DB_SAFETY` and exiting with status code `1`.
2. **Targeted Negative Test (Primary Database Protection)**: Executing the script when the backend was connected to `cloudsentinel.db` triggered `CRITICAL SAFETY ABORT`, preventing any state-changing execution and exiting with status code `1`.
3. **Assertion Strictness**: Missing buttons, unexpected cards, or dirty state (e.g. uncleared incidents) trigger explicit assertion failures and non-zero process exits.

---

## 5. Visual Evidence Artifacts (Genuinely Captured)

All screenshots were freshly captured by the Google Chrome DevTools Protocol automation script during this test run and saved to [`docs/screenshots/`](screenshots/):

1. **[`day4_01_initial_dashboard.png`](screenshots/day4_01_initial_dashboard.png)**: Clean initial dashboard state with active backend online badge.
2. **[`day4_02_metrics_generated.png`](screenshots/day4_02_metrics_generated.png)**: Populated observations table (50 rows displayed, 100 total samples) and KPI cards.
3. **[`day4_03_threshold_detection.png`](screenshots/day4_03_threshold_detection.png)**: Active incidents table showing 5 threshold baseline incidents.
4. **[`day4_04_threshold_evidence_modal.png`](screenshots/day4_04_threshold_evidence_modal.png)**: Incident modal with observed numerical readings vs configured threshold boundaries.
5. **[`day4_05_isolation_forest_detection.png`](screenshots/day4_05_isolation_forest_detection.png)**: Incidents table updated to 10 rows showing both threshold and ML detectors.
6. **[`day4_06_ml_evidence_modal.png`](screenshots/day4_06_ml_evidence_modal.png)**: ML incident modal displaying raw Scikit-Learn decision score and feature subspace.
7. **[`day4_07_persisted_after_reload.png`](screenshots/day4_07_persisted_after_reload.png)**: Browser state preserved following full page reload from SQLite.
8. **[`day4_08_mobile_responsive.png`](screenshots/day4_08_mobile_responsive.png)**: Mobile viewport (375×667) showing responsive stacking without horizontal scrolling.
9. **[`day4_09_backend_recovery.png`](screenshots/day4_09_backend_recovery.png)**: Backend outage emulation and clean recovery without stale state lockup.
10. **[`day4_qa_results.json`](screenshots/day4_qa_results.json)**: Machine-readable JSON output of all test assertions.

---

## 6. Regression & Quality Summary

- **Backend Pytest Suite**: 114 passed, 0 failed in 13.81s across all 8 modules.
- **Frontend ESLint 10**: Clean (0 errors, 0 warnings).
- **Frontend Vite Production Build**: Compiled in 964ms (HTML: 0.90 kB, CSS: 16.74 kB, JS: 210.66 kB).
- **Machine Learning Benchmark**:
  - *Threshold Baseline*: Precision `1.0000`, Recall `1.0000`, F1 `1.0000` (`[[95, 0], [0, 5]]`).
  - *IsolationForest*: Precision `0.8000`, Recall `0.8000`, F1 `0.8000` (`[[94, 1], [1, 4]]`).
- **Verified GitHub Actions CI Run**: [Run 38733241686](https://github.com/ARKkhanz/cloudsentinel-ai/actions/runs/38733241686) (All 3 jobs green on `ubuntu-24.04`).
