# CloudSentinel AI — Day 4 Milestone 1 Automated End-to-End QA Report

**Verification Date:** 2026-10-15 17:03:25 UTC  
**Target Milestone:** Day 4 Milestone 1 — Final End-to-End Evaluator Verification Journey  
**Execution Mode:** Google Chrome DevTools Protocol (CDP) WebSocket Automation  
**Target Service URL:** `http://127.0.0.1:5173/` (Vite dev server)  
**Backend API URL:** `http://127.0.0.1:8000/` (FastAPI ASGI Uvicorn service)  
**Disposable Database Target:** `backend/data/day4_evaluator_qa.db` (Cleanly isolated and removed post-test)

---

## 1. System Environment & Tool Versions

| Tool / Runtime | Version | Scope / Notes |
| :--- | :--- | :--- |
| **Operating System** | Windows 11 Pro (win32) | Workstation host environment |
| **Python** | 3.11.9 (in `backend/.venv`) | Backend FastAPI, Scikit-Learn, Pytest |
| **Node.js** | v24.19.0 | Frontend build toolchain & ESLint |
| **npm** | 11.17.0 | Frontend dependency manager |
| **Google Chrome** | 141+ (`C:\Program Files\Google\Chrome\Application\chrome.exe`) | Headless browser for automated CDP QA |
| **Docker** | Uninstalled locally | Docker containerization verified via GitHub Actions cloud runner |

---

## 2. User Data Protection & Database Isolation Policy

In strict accordance with Phase 3 requirements, existing user data in `backend/data/cloudsentinel.db` was protected:
1. **Isolated Database URI**: The backend was started with an explicit environment variable:
   `DATABASE_URL="sqlite:///C:/Users/USER/.gemini/antigravity-ide/scratch/cloudsentinel-ai/backend/data/day4_evaluator_qa.db"`
2. **Untouched Primary Database**: `cloudsentinel.db` retained its original modification timestamp (`2026-10-14 19:03:10`) and size (102,400 bytes). Zero production/user data was overwritten or modified.
3. **Safe Teardown**: `day4_evaluator_qa.db` was safely deleted after the QA execution completed.

---

## 3. Automated Chrome CDP Test Results (12/12 PASSED)

| Step # | Test Identifier | Status | Observation | Evidence / Response Details |
| :---: | :--- | :---: | :--- | :--- |
| **1** | `DAY4_01_Initial_Connection` | **PASS** | Dashboard rendered cleanly; backend online badge verified. | Page Title: `CloudSentinel AI — Reliability Dashboard`<br>Badge: `BACKEND: ONLINE (CLOUDSENTINEL-BACKEND V0.1.0)` |
| **2** | `DAY4_02_Generate_Synthetic_Telemetry` | **PASS** | Clicked `#btn-generate-demo`; generated 100 samples with 5 anomalies. | Feedback: `"Successfully generated and persisted 100 observations with 5 injected anomalies for 'demo-api'."`<br>Table: 50 rows displayed (display limit). KPI: 100 samples in SQLite. |
| **3** | `DAY4_03_Run_Threshold_Detection` | **PASS** | Clicked `#btn-run-threshold`; created 5 threshold incident records. | Incident Table: 5 rows.<br>Badge: `THRESHOLD_BASELINE` (v1.0.0).<br>Severities: 3 `WARNING` (latency > 150ms), 2 `CRITICAL` (error rate > 5%). |
| **4** | `DAY4_04_Threshold_Evidence_Inspection` | **PASS** | Opened modal for threshold incident; verified observed vs rule comparison. | Modal Title: `"Elevated Latency on demo-api (503.7 ms)"`<br>Observed Latency: `503.72 ms`<br>Condition: `latency_ms: 503.72 ms > threshold 150.0 ms (+353.72 ms excess)`. |
| **5** | `DAY4_05_Run_IsolationForest_Detection` | **PASS** | Clicked `#btn-run-ml`; executed Scikit-Learn detector; incidents reached 10. | Incident Table: 10 total rows.<br>Detectors present: `THRESHOLD_BASELINE` and `ISOLATION_FOREST`. |
| **6** | `DAY4_06_IsolationForest_Evidence_Inspection` | **PASS** | Opened modal for ML incident; verified decision score and model parameters. | Modal Title: `"Multivariate Anomaly Detected by IsolationForest on demo-api (score: -0.0011)"`<br>Decision Score: `-0.0011`<br>Parameters: `contamination=0.05`, `n_estimators=100`, 5 features evaluated. |
| **7** | `DAY4_07_Incident_Deduplication` | **PASS** | Re-ran threshold detection; confirmed zero duplicate incidents created. | Feedback: `"Detection complete: Evaluated 100 samples -> 5 findings, 0 new incidents created (5 skipped as duplicates)."`<br>Total incidents remained exactly 10. |
| **8** | `DAY4_08_Persistence_Across_Reload` | **PASS** | Executed `Page.reload`; confirmed full state restore from SQLite. | Reloaded state: 10 incidents intact, 50 telemetry rows displayed, KPI summary cards accurate. |
| **9** | `DAY4_09_Mobile_Responsiveness` | **PASS** | Emulated mobile viewport (375x667, 2x scale); verified responsive layout. | Horizontal overflow check: `document.documentElement.scrollWidth <= window.innerWidth` returned `True` (zero horizontal overflow). |
| **10** | `DAY4_10_Outage_And_Recovery_Handling` | **PASS** | Blocked network requests via CDP; verified stale/error banner; unblocked and recovered. | Stale banner displayed: `"Backend Connection Lost — Displaying Stale Cached Telemetry"`. Upon unblocking, health badge returned to `online` and error banner cleared. |
| **11** | `DAY4_11_Prototype_Disclaimers` | **PASS** | Audited DOM text for production claims vs prototype disclaimers. | Zero false claims of "production monitoring" or "automatic root-cause". Clear "synthetic telemetry" and "portfolio prototype" badges present. |
| **12** | `DAY4_12_Console_And_Network_Audit` | **PASS** | Audited browser console and network responses. | Real Console Errors: `0`<br>Uncaught JS Exceptions: `0`<br>Unexpected HTTP 500+ Failures: `0`. |

---

## 4. Visual Evidence Artifacts (Genuinely Captured)

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
10. **[`day4_qa_results.json`](screenshots/day4_qa_results.json)**: Machine-readable JSON output of all 12 test assertions.

---

## 5. Regression & Quality Summary

- **Backend Pytest Suite**: 114 passed, 0 failed in 15.77s.
- **Frontend ESLint 10**: Clean (0 errors, 0 warnings).
- **Frontend Vite Production Build**: Compiled in 964ms (HTML: 0.75 kB, CSS: 9.14 kB, JS: 163.55 kB).
- **Machine Learning Benchmark**:
  - *Threshold Baseline*: Precision `1.0000`, Recall `1.0000`, F1 `1.0000` (`[[95, 0], [0, 5]]`).
  - *IsolationForest*: Precision `0.8000`, Recall `0.8000`, F1 `0.8000` (`[[94, 1], [1, 4]]`).
- **Verified GitHub Actions CI Run**: [https://github.com/ARKkhanz/cloudsentinel-ai/actions/runs/38595647392](https://github.com/ARKkhanz/cloudsentinel-ai/actions/runs/38595647392) (All 3 jobs green, 0 warnings on `ubuntu-24.04`).
