# CloudSentinel AI — Engineering & Learning Architecture Guide

This document explains the technical architecture, data pipeline, design decisions, and reliability principles implemented in CloudSentinel AI across Day 1 and Day 2 (Milestones 1–5).

---

## 1. End-to-End Architecture: Detection-to-Incident Pipeline

CloudSentinel AI establishes an evidence-backed incident workflow:

```
[Synthetic / Ingested Telemetry]
              │
              ▼
   [SQLite Database Engine]
       (Table: metric_samples)
              │
              ▼
   [Incident Service Layer]  <── Queries persisted samples (newest first, reversed to chronological)
              │
              ├───► [Selected Detector: ThresholdDetector]
              │         Evaluates against statistical boundaries (>150ms latency, >5% error rate)
              │         Yields: ThresholdFinding
              │
              └───► [Selected Detector: IsolationForestDetector]
                        Fits on clean reference baseline (Seed 100, 100 samples, 0 anomalies)
                        Scores multivariate feature subspace (latency, error_rate, cpu, memory, requests)
                        Yields: MLDetectionFinding
              │
              ▼
    [Incident Conversion & Deduplication Engine]
        Computes deterministic key: f"{service}:{detector_name}:{obs_timestamp_utc_iso}"
        Filters previously recorded findings to prevent duplicate alert noise
              │
              ▼
   [SQLite Database Engine]
       (Table: incidents)  <── Stores immutable evidence snapshots & detector metadata
              │
              ▼
   [FastAPI Endpoints]
       POST /api/detection/run
       GET  /api/incidents
       GET  /api/incidents/{id}
              │
              ▼
   [React Dashboard UI]
       Action Controls -> Metrics Overview -> Incidents Table -> Evidence Modal
```

---

## 2. Core Concepts & Design Decisions

### 2.1 What an Incident Represents
An incident in CloudSentinel AI represents a **persisted, factual anomaly finding** produced by an active detector against recorded telemetry observations. It is an alert record indicating that observed system behavior deviated significantly from expected operational boundaries.

An incident is NOT:
* A speculative claim about software bugs or infrastructure failure.
* An unverified or fabricated alert.
* A temporary alert dismissed when browser is refreshed.

Every incident contains:
1. Unique incident UUID.
2. Target service identifier.
3. UTC creation timestamp.
4. Severity level (`critical` or `warning`).
5. Status (initially `open`).
6. Detector attribution (`detector_name` and `detector_version`).
7. Factual human-readable summary headline.
8. Non-speculative explanation.
9. Observed numerical measurements at time of observation.
10. Baseline/detector evidence snapshot (threshold rules or ML decision score and parameters).
11. Applicable observation timestamp window.
12. Deterministic deduplication key.

---

### 2.2 What Detector Evidence Means
Detector evidence is the **verifiable numerical data** that justified flagging an observation as anomalous:
* **For Threshold Breaches**: Exact measured values vs configured thresholds, numerical excess (e.g., `+271.57 ms`), units (`ms` or `%`), and the breached condition (`observed > threshold`).
* **For IsolationForest Outliers**: Raw Scikit-Learn `decision_function` score (e.g. `-0.0011`, where negative values indicate subspace isolation), binary prediction label (`-1`), expected contamination (`0.05`), tree count (`100`), reference baseline size (`100 normal samples`), and evaluated feature names.

Evidence must always be factual, grounded strictly in numbers, and distinct from any inferred interpretation.

---

### 2.3 How Threshold Incidents Differ from ML Incidents

| Dimension | Threshold Incidents (`ThresholdDetector`) | ML Incidents (`IsolationForestDetector`) |
| :--- | :--- | :--- |
| **Logic** | Univariate rule boundaries evaluated independently | Multivariate subspace partitioning across 5 combined metrics |
| **Boundaries** | Explicit fixed thresholds (`latency > 150ms`, `error_rate > 5%`) | Dynamic learned density cluster isolation |
| **Evidence** | Direct excess comparisons (`observed - threshold`) | Mathematical decision score (shorter tree path length) |
| **Severity Mapping** | Deterministic based on breached metric (latency -> warning, error rate / both -> critical) | Deterministic based on outlier extremity (score < -0.15 -> critical, else warning) |
| **Interpretability** | Immediate: obvious why breach occurred | Geometric: observation isolated in multi-metric space |

---

### 2.4 Why Deduplication Matters
In reliability engineering, duplicate alerts cause **alert fatigue**, burying critical outages under thousands of repeated notifications.

Running the same detector repeatedly on the same persisted metric records must never create duplicate incidents.

**CloudSentinel Deduplication Strategy**:
* Identity Key: `dedup_key = f"{service}:{detector_name}:{obs_timestamp_utc_iso}"`.
* **Cross-Detector Independence**: Because `detector_name` is embedded in the key, running `threshold_baseline` and `isolation_forest` on the exact same sample generates distinct deduplication keys (`demo-api:threshold_baseline:...` vs `demo-api:isolation_forest:...`). Neither detector suppresses the other!
* **Idempotency**: Repeatedly executing the same detector on the same samples increments `incidents_already_existing` and returns 0 new incidents, keeping the database clean.
* **Database Constraint**: A unique index on `incidents.dedup_key` guarantees database-level race protection.

---

### 2.5 Why Evidence Snapshots Must Survive Telemetry Regeneration
In prototype and testing environments, synthetic telemetry datasets are frequently regenerated or wiped (e.g. `replace_existing=True` in `/api/demo/generate`).

If an incident only contained foreign keys or pointers to raw metric rows, regenerating the dataset would leave orphaned incidents or corrupt investigation records.

CloudSentinel AI solves this by embedding an **immutable evidence snapshot** directly within the `IncidentModel` record in SQLite (`observed_metric_evidence` and `baseline_evidence`). Even if the originating telemetry samples are deleted or replaced, the incident's investigation evidence remains 100% complete, legible, and verifiable.

---

### 2.6 How FastAPI Exposes Incident Records
FastAPI exposes incidents through clean REST endpoints decoupled from database internals:
* `POST /api/detection/run`: Accepts `{ service, detector, limit }`. Executes the pipeline via `incident_service.py` and returns structured summary counts.
* `GET /api/incidents`: Supports filtering by `service`, `status`, `detector_name`, and bounded `limit`. Orders records newest-first (`created_at.desc()`).
* `GET /api/incidents/{id}`: Looks up a specific incident by UUID. Returns HTTP 404 with standard JSON detail if not found.

Pydantic schemas (`DetectionRunRequest`, `DetectionRunResponse`, `IncidentResponse`, `IncidentListResponse`) enforce request validation and response serialization.

---

### 2.7 How React Fetches and Displays Incidents
The React dashboard (`App.tsx`) uses a centralized API client (`client.ts`) without external state libraries:
* **Concurrent Loading**: Dispatches `fetchHealth()`, `fetchMetrics()`, and `fetchIncidents()` in parallel via `Promise.all`.
* **Action Controls Toolbar**:
  * `⚡ Generate Synthetic Data`: Generates 100 samples with 5 injected anomalies.
  * `📊 Run Threshold Detection`: Triggers rule-based detection and updates the incident list.
  * `🌲 Run IsolationForest Detection`: Triggers ML detection and populates multivariate findings.
* **Incident Table**: Renders incident UUID, observation time, severity badge, detector tag, status, summary, and a "View Evidence" button.
* **Evidence Modal**: Displays complete evidence breakdown including observed measurements, comparison rules, IsolationForest decision score, and anti-speculation disclaimers.

---

### 2.8 Why Anomaly Detection Cannot Establish Root Cause
Unsupervised anomaly detection algorithms (like IsolationForest) and threshold detectors detect **statistical abnormality**, not **causality**:
* A detector knows *that* latency surged to 420ms or *that* a metric combination is isolated in feature space.
* A detector does NOT know *why* it happened (e.g., whether caused by an unindexed SQL query, a memory leak, a third-party API outage, or GC pauses).

Claiming that anomaly detection "diagnosed the root cause" is scientifically inaccurate. CloudSentinel AI enforces this principle in all summaries, explanations, and UI disclaimers.

---

### 2.9 How Data Survives a Server Restart
CloudSentinel AI uses **SQLite** backed by a persistent file (`backend/data/cloudsentinel.db`) via SQLAlchemy ORM:
* SQLite writes transactions to persistent disk storage using ACID write-ahead logging.
* When the FastAPI backend (Uvicorn) is stopped, the database file remains intact on disk.
* Upon server restart, SQLAlchemy reconnects to the database file, and `init_db()` synchronizes table schemas without dropping existing records.
* This was verified in automated testing: all 10 persisted incidents remained available immediately following backend restart.

---

### 2.10 Timestamp Integrity & Separation
Every incident maintains three distinct, unambiguous UTC timestamps:
1. **Observation Timestamp (`window_start` / `window_end`)**: When the anomaly physically occurred in the monitored service.
2. **Detection Run Timestamp (`run_timestamp`)**: When the detection algorithm executed.
3. **Creation Timestamp (`created_at`)**: When the incident record was committed to SQLite.

Detectors strictly reject missing timestamps (`timestamp=None`) and normalize all values to UTC timezone-aware datetimes, completely preventing silent fallbacks to `datetime.now()`.

---

## 3. Automated Verification Summary

| Suite | Scope | Result | Execution Time |
| :--- | :--- | :---: | :---: |
| **Pytest Backend Suite** | 7 test files (Health, Metrics, Persistence, Demo Gen, Threshold, ML, Incidents) | **96 passed, 0 failed** | ~8.3s |
| **Frontend Production Build** | TypeScript compiler check (`tsc -b`) & Vite bundler | **Pass** (0 errors) | ~1.1s |
| **Real Chrome Browser QA** | 11 automated CDP steps (Connection, Generation, Threshold, ML, Evidence, Dedup, Persistence, Mobile) | **11 passed, 0 failed** | ~23s |
