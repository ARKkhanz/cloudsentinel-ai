# CloudSentinel AI — Day 2 Milestone 6 Automated Browser QA Report

**Date:** 2026-10-14 19:03:30
**Automation Engine:** Google Chrome DevTools Protocol (CDP) WebSocket
**Target URL:** `http://127.0.0.1:5173/` (FastAPI backend at `http://127.0.0.1:8000/`)

## Executive Summary
Executed 11 automated verification checks in real Google Chrome. All core flows passed cleanly.

## Summary of Test Results

| Test Step | Status | Observation | Evidence |
| :--- | :---: | :--- | :--- |
| **M6_01_Initial_Connection** | PASS | Page title: 'CloudSentinel AI — Reliability Dashboard', Health badge: 'BACKEND: ONLINE (CLOUDSENTINEL-BACKEND V0.1.0)' |  |
| **M6_02_Generate_Synthetic_Telemetry** | PASS | Generated telemetry: 50 table rows displayed (display limit: 50). Total samples: demo-api. | Feedback: 'Successfully generated and persisted 100 observations with 5 injected anomalies for 'demo-api'.
✕' |
| **M6_03_Run_Threshold_Detection** | PASS | Threshold detection active. Incident table row count: 10. Threshold badge found: True | Feedback: 'Threshold Detection completed on 100 samples: 5 findings, 0 new incidents created (5 deduplicated).
✕' |
| **M6_04_Threshold_Evidence_Inspection** | PASS | Evidence modal opened: 'Elevated Latency on demo-api (421.6 ms)' | Explanation: 'Observed latency of 421.57 ms exceeded the configured threshold of 150.0 ms (+271.57 ms excess).'. Measurements: ['421.57 ms', '0.49%', '133', '71.5%', '43.4%'] |
| **M6_05_Run_IsolationForest_Detection** | PASS | Total incidents now: 10. Detectors present: {'ISOLATION_FOREST', 'THRESHOLD_BASELINE'} | Feedback: 'IsolationForest Detection completed on 100 samples: 5 findings, 0 new incidents created (5 deduplicated).
✕' |
| **M6_06_IsolationForest_Evidence_Inspection** | PASS | ML evidence modal verified: 'Multivariate Anomaly Detected by IsolationForest on demo-api (score: -0.0011)'. Anomaly score: '-0.0011' | Explanation: 'IsolationForest classified this observation as an outlier based on its combined numerical telemetry features (latency_ms, error_rate, cpu_usage_pct, memory_usage_pct, request_count). The recorded decision score was -0.0011 (negative decision score indicates isolation in anomalous subspace).' |
| **M6_07_Incident_Deduplication** | PASS | Deduplication confirmed. Total incidents remained 10 (0 duplicates). | Feedback: 'Threshold Detection completed on 100 samples: 5 findings, 0 new incidents created (5 deduplicated).
✕' |
| **M6_08_Persistence_Across_Reload** | PASS | Persisted data restored after reload: 10 incidents, 50 telemetry rows. |  |
| **M6_09_Mobile_Responsiveness** | PASS | Mobile viewport (375px) tested. Horizontal overflow: False |  |
| **M6_10_Prototype_Disclaimers** | PASS | Disclaimers verified. Claims production: False, Has prototype labels: True |  |
| **M6_11_Console_And_Network_Audit** | PASS | Console errors: 0, JS exceptions: 0, Failed HTTP requests: 0 |  |

## Visual Evidence Artifacts
- `docs/screenshots/milestone6_01_initial_dashboard.png` — Initial dashboard state with backend online badge.
- `docs/screenshots/milestone6_02_metrics_generated.png` — Synthetic telemetry generation with 100 samples.
- `docs/screenshots/milestone6_03_threshold_detection.png` — Threshold baseline detection incidents table.
- `docs/screenshots/milestone6_04_threshold_evidence_modal.png` — Modal with observed numerical metric evidence.
- `docs/screenshots/milestone6_05_isolation_forest_detection.png` — IsolationForest multivariate detection findings.
- `docs/screenshots/milestone6_06_ml_evidence_modal.png` — IsolationForest modal with anomaly score evidence.
- `docs/screenshots/milestone6_07_persisted_after_reload.png` — Browser reload confirming SQLite persistence.
- `docs/screenshots/milestone6_08_mobile_responsive.png` — Mobile viewport (375x667) responsive layout.