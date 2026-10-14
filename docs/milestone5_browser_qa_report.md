# CloudSentinel AI — Milestone 5 Automated Browser QA Verification Report

**Execution Date:** 2026-10-14 18:28:15 UTC  
**Target URL:** [http://127.0.0.1:5173/](http://127.0.0.1:5173/)  
**Backend API:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)  
**Browser Engine:** Google Chrome v141 Headless via native Chrome DevTools Protocol (CDP over WebSockets)  
**Total Tests:** 11  
**Passed:** **11** (100.0%)  
**Failed:** **0**  

---

## Verification Matrix

| Test ID | Status | Observation | Evidence |
| :--- | :---: | :--- | :--- |
| **M5_01_Initial_Connection** | **PASS** | Page title: 'CloudSentinel AI — Reliability Dashboard', Health badge: 'BACKEND: ONLINE (CLOUDSENTINEL-BACKEND V0.1.0)' |  |
| **M5_02_Generate_Synthetic_Telemetry** | **PASS** | Generated telemetry: 50 table rows displayed. Feedback: 'Successfully generated and persisted 100 observations with 5 injected anomalies for 'demo-api'.
✕' | Total requests: 6,536 |
| **M5_03_Run_Threshold_Detection** | **PASS** | Created 5 threshold incidents. Feedback: 'Threshold Detection completed on 100 samples: 5 findings, 5 new incidents created (0 deduplicated).
✕' | Detector badge: 'THRESHOLD_BASELINE' |
| **M5_04_Threshold_Evidence_Inspection** | **PASS** | Evidence modal opened: 'Elevated Latency on demo-api (421.6 ms)' | Explanation: 'Observed latency of 421.57 ms exceeded the configured threshold of 150.0 ms (+271.57 ms excess).'. Measurements: ['421.57 ms', '0.49%', '133', '71.5%', '43.4%'] |
| **M5_05_Run_IsolationForest_Detection** | **PASS** | Total incidents now: 10. Detectors present: {'THRESHOLD_BASELINE', 'ISOLATION_FOREST'} | Feedback: 'IsolationForest Detection completed on 100 samples: 5 findings, 5 new incidents created (0 deduplicated).
✕' |
| **M5_06_ML_Evidence_Inspection** | **PASS** | ML evidence modal opened: 'Multivariate Anomaly Detected by IsolationForest on demo-api (score: -0.0011)' | IsolationForest Decision Score: '-0.0011'. Explanation: 'IsolationForest classified this observation as an outlier based on its combined numerical telemetry features (latency_ms, error_rate, cpu_usage_pct, memory_usage_pct, request_count). The recorded decision score was -0.0011 (negative decision score indicates isolation in anomalous subspace).' |
| **M5_07_Deduplication_Prevention** | **PASS** | Deduplication confirmed. Total rows remained: 10 | Feedback: 'Threshold Detection completed on 100 samples: 5 findings, 0 new incidents created (5 deduplicated).
✕' |
| **M5_08_Reload_State_Persistence** | **PASS** | State persisted after browser reload: 10 incidents, 50 metric samples. |  |
| **M5_09_Mobile_Viewport_390x844** | **PASS** | Mobile layout inspected without horizontal overflow. | scrollWidth <= innerWidth: True |
| **M5_10_Console_Zero_Errors** | **PASS** | Audited browser console: 0 error logs found. |  |
| **M5_11_Network_Healthy_Responses** | **PASS** | Network audit: 0 failed requests out of 53 total. |  |

---

## Visual Verification Artifacts

1. `milestone5_01_initial_state.png` — Initial clean dashboard state connected to FastAPI.
2. `milestone5_02_metrics_generated.png` — Dashboard populated with 100 observations after synthetic data generation.
3. `milestone5_03_threshold_incidents.png` — Detected Incidents table displaying threshold baseline findings.
4. `milestone5_04_threshold_evidence_modal.png` — Threshold incident evidence modal showing factual measurements vs rules.
5. `milestone5_05_ml_evidence_modal.png` — IsolationForest evidence modal showing decision score, classification label, and baseline model metadata.
6. `milestone5_06_mobile_responsive.png` — Mobile viewport (390×844) responsive rendering.
7. `milestone5_07_full_dashboard.png` — Final persistent state showing both detector findings surviving reloads.
