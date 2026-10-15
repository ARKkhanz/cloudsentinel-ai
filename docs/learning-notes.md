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
        Computes deterministic key: f"{service}:{detector_name}:{sha256[:32]}"
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
* **Deterministic Canonical Fingerprinting**: The current implementation computes a deterministic SHA-256 fingerprint: `dedup_key = f"{service}:{detector_name}:{sha256[:32]}"`. The hash payload combines service name, detector version, detector configuration summary, UTC observation timestamp, and sorted, fixed-precision numerical metric readings. *(Historical note: Milestone 5 initially used a simpler timestamp-based key `f"{service}:{detector_name}:{obs_timestamp_utc_iso}"`, which was upgraded in Milestone 6 to SHA-256 fingerprinting so that distinct metric values at reused timestamps are never falsely suppressed).*
* **Value-Sensitive Discrimination**: If telemetry values change at a reused timestamp (e.g., during dataset regeneration), the canonical metric string produces a distinct SHA-256 hash, ensuring legitimate shifts are never suppressed.
* **Cross-Detector Independence**: Because `detector_name` is embedded in the key, running `threshold_baseline` and `isolation_forest` on the exact same sample generates distinct deduplication keys (`demo-api:threshold_baseline:...` vs `demo-api:isolation_forest:...`). Neither detector suppresses the other!
* **Idempotency**: Repeatedly executing the same detector on identical samples increments `incidents_already_existing` and returns 0 new incidents, keeping the database clean.
* **Database Constraint**: A unique index on `incidents.dedup_key` guarantees database-level race protection and enforces absolute idempotency.

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

### 2.11 Database Schema Migration & Observable Error Propagation
In earlier iterations, database schema initialization wrapped table alterations in broad exception suppression (`except Exception: pass`). This presented a critical reliability defect where failed schema migrations could pass silently.

In Milestone 6, `init_db()` was refactored:
1. **Observable Failure**: Silent suppression was removed. Operational failures (e.g. database locks, read-only media, disk full, or unique index integrity conflicts) are logged with full stack traces via Python `logging` and re-raised (`raise`).
2. **Idempotent Synchronization**: Using SQLAlchemy's `inspect()`, existing columns and indexes are examined before applying schema changes. Missing columns (`metric_sample_id`, `dedup_key`) are added safely via `ALTER TABLE ... ADD COLUMN ...`.
3. **Index Verification**: Even if columns existed from previous migrations, the unique index `ix_incidents_dedup_key` is verified and created idempotently using `CREATE UNIQUE INDEX IF NOT EXISTS`.
4. **Data Preservation**: Existing incident records and telemetry are preserved intact during migrations without table recreation or truncation.

---

### 2.12 Hardened Deduplication via SHA-256 Metric Fingerprinting
The previous deduplication key format was:
`service:detector_name:observation_timestamp`

While effective for identical telemetry runs, this key suppressed genuinely new findings if synthetic demo batches were regenerated with different numerical telemetry at the same timestamps.

To resolve this edge case, Milestone 6 implemented canonical SHA-256 fingerprinting:
1. **Identity Vector**:
   $$\text{Payload} = \text{service} \parallel \text{detector:version} \parallel \text{config} \parallel \text{UTC timestamp} \parallel \text{sorted canonical metrics}$$
2. **Fixed Numerical Formatting**: Float values are formatted to stable precision (`latency_ms` to 4 decimal places, `request_count` as an integer) to avoid representation jitter across serialization boundaries.
3. **Compact Key**: The key is formatted as `f"{service}:{detector_name}:{sha256[:32]}"`, remaining compact (< 60 chars) and optimal for SQLite indexes.
4. **Backward Compatibility**: Pre-existing historical incidents created with legacy keys (`service:detector:iso_timestamp`) are cross-referenced with stored metric evidence so historical incidents are preserved without unnecessary duplication.
5. **Safe Concurrency Conflict Handling**: If concurrent processes attempt duplicate insertion, SQLite's unique constraint raises `IntegrityError`. The transaction is rolled back safely, non-conflicting incidents are committed individually, and `incidents_already_existing` is reported without exposing unhandled HTTP 500 errors.

---

### 2.13 Reproducible ML Evaluation & Metric Formulation
Evaluating anomaly detectors against synthetic benchmarks requires strict mathematical formulation and zero leakage:
1. **Training/Evaluation Isolation**:
   - Clean Training: Seed `100`, 100 samples, 0 anomalies injected.
   - Evaluation Set: Seed `42`, 100 samples, 5 injected anomalies (3 latency spikes, 2 error rate surges).
2. **Zero Leakage**: Feature vectors strictly exclude ground-truth anomaly labels, synthetic flags, timestamps, and database IDs.
3. **Formulas**:
   - $\text{Precision} = \frac{\text{TP}}{\text{TP} + \text{FP}}$ (handles division by zero safely by returning 0.0)
   - $\text{Recall} = \frac{\text{TP}}{\text{TP} + \text{FN}}$
   - $\text{F1} = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$
   - $\text{FPR} = \frac{\text{FP}}{\text{FP} + \text{TN}}$
   - Confusion Sum Check: $\text{TP} + \text{FP} + \text{TN} + \text{FN} = \text{Total Samples} (100)$

---

### 2.14 Comparative Insights: Threshold vs. IsolationForest
Empirical evaluation demonstrated key operational trade-offs:
1. **Threshold Baseline ($F_1 = 1.0$)**:
   - Outperformed ML on this benchmark because the synthetic generator injects massive single-metric spikes ($>20$ standard deviations above baseline).
   - When operational rules are tuned to target known, severe univariate shocks, threshold rules achieve perfect precision and recall with zero training cost.
2. **IsolationForest ($F_1 = 0.80$)**:
   - Successfully isolated 4 of 5 ground-truth anomalies in 5-dimensional subspace without access to labels or business rules.
   - **False Positive (Index 28)**: Flagged an observation with unusually low latency (31.88ms) and high request count (152). While operationally healthy, this rare coordinate combination fell into a sparse subspace, receiving a decision score of `-0.0054` (below the training-derived `offset_`).
   - **Contamination is an Assumption, Not Ground Truth**: Setting `contamination=0.05` sets the decision threshold (`offset_`) based on the 5th percentile of anomaly scores on the training data. It does not enforce an arbitrary budget or quota of 5 samples on unseen evaluation data, nor does it reflect empirical anomaly prevalence in production.
   - **No Per-Feature Causal Attribution**: IsolationForest isolates samples via randomized orthogonal cuts across all 5 features. It outputs a scalar outlier score for the feature vector as a whole, but provides no per-feature causal explanation or root cause diagnosis.
   - **Anomaly Score is NOT Outage Probability**: A negative decision score (e.g. $-0.0373$) indicates geometric isolation path length, not a probability of service failure.

---

## 3. Automated Verification Summary

| Suite | Scope | Result | Execution Time |
| :--- | :--- | :---: | :---: |
| **Pytest Backend Suite** | 8 test modules (Health, Metrics, Persistence, Demo Gen, Threshold, ML, Incidents, Evaluation) | **114 passed, 0 failed** | ~13.1s |
| **Frontend Production Build** | TypeScript compiler check (`tsc -b`) & Vite bundler | **Pass** (0 errors) | ~1.0s |
| **Reproducible ML Benchmark** | Standalone benchmark runner (`backend/scripts/evaluate_detectors.py`) | **Reproduced** (100 samples) | ~0.6s |
| **Chrome Browser QA (Day 4 Final)** | 13 automated CDP steps (including database safety preflight and negative test proofs; documented in [`docs/day4_milestone1_qa_report.md`](day4_milestone1_qa_report.md)) | **13 passed, 0 failed** | ~28s |
| *Historical Chrome QA (Day 2 Milestone 6)* | *11 automated CDP steps (preliminary verification of core UI flows)* | *11 passed, 0 failed* | *~24s* |
| **GitHub Actions CI (All 3 Jobs)** | Backend pytest (114), Frontend ESLint/Vite, Docker Compose multi-container integration & persistence | **100% Green** | ~1m 40s |

---

## 4. Day 3: Containerization, Orchestration & Continuous Integration

### 4.1 Continuous Integration (CI) Principles
Continuous Integration is the automated engineering practice of validating every code change against an isolated, reproducible environment upon push. In CloudSentinel AI, CI ensures that code quality, unit tests, machine learning evaluation baselines, and multi-container Docker orchestration are automatically proven on disposable Ubuntu cloud runners before deployment.

### 4.2 GitHub Actions Architecture: Workflows, Jobs, and Steps
- **Workflow** (`.github/workflows/ci.yml`): The top-level automated process defined in YAML, triggered by events (`push`, `pull_request`, `workflow_dispatch`).
- **Jobs** (`backend-tests`, `frontend-checks`, `docker-integration`): Parallel execution units running on independent, fresh `ubuntu-24.04` virtual machines.
- **Steps**: Sequential tasks inside a job executing individual commands (checkout, setup-python, npm ci, docker compose up).

### 4.3 Why Hosted Cloud Runners Solve Local Toolchain Constraints
The local development Windows workstation did not have Docker Desktop installed. Rather than attempting risky, unverified local container operations, we designed and committed declarative Docker and Compose definitions, and leveraged GitHub-hosted Ubuntu runners (which include real, running Docker Engines and Compose plugins) to achieve authentic, verifiable runtime execution.

### 4.4 Image Compilation vs. Runtime System Validation
A Docker image building without syntax errors only proves that dependencies installed and files copied. It does **NOT** prove:
- That the process binds correctly to `0.0.0.0` instead of `127.0.0.1`.
- That Nginx can resolve `backend` over the Docker bridge network.
- That the non-root user has write permissions to create SQLite write-ahead logs (`.db-wal`).
- That database records survive container destruction and restart.
Only live container orchestration tests (Phase 5–10) provide authentic engineering proof.

### 4.5 Health Checks and Startup Ordering
FastAPI's `@router.get("/health")` endpoint is polled via Python standard library `urllib.request`. In Compose, `frontend` specifies `depends_on.backend.condition: service_healthy` with a 15-second `start_period`, ensuring Nginx does not proxy traffic until Scikit-Learn models and SQLAlchemy schemas have initialized.

### 4.6 Reverse Proxying & Internal DNS Concealment
In production, the browser only speaks to `http://localhost:3000`. It makes relative requests (`/health`, `/api/metrics`). Nginx resolves `http://backend:8000` via Docker's internal DNS (`127.0.0.11`). The internal container hostname `backend:8000` never leaks into browser JavaScript bundles, eliminating CORS preflight overhead and concealing container network topology.

### 4.7 SQLite Volume Persistence Across Container Lifecycle
- **`docker compose down`**: Stops and removes container namespaces and networks, but **preserves** the named volume `cloudsentinel-data`.
- **`docker compose up -d`**: Re-attaches the existing volume. Our automated CI integration script proved that telemetry observations (100 samples) and incident records persisted across a full container down/up recreation cycle.
- **`docker compose down -v`**: Destructively deletes named volumes. It is reserved strictly for test teardown and clean slate resets.

### 4.8 Non-Root Permissions on Mounted Volumes
In `backend/Dockerfile`, `/app/backend/data` is created and assigned to `cloudsentinel:appgroup`. When Docker initializes a named volume for a container, it copies the image directory's initial metadata and file permissions into the volume. This guarantees that SQLite transactions succeed without encountering read-only filesystem errors under `USER cloudsentinel`.

### 4.9 CI Environment Hardening: Ubuntu 24.04 LTS Pinning & Node 24 Action Runtimes
In Day 3 Milestone 5, the CI pipeline underwent engineering hardening to guarantee long-term reproducibility and eliminate runtime deprecation warnings:
1. **Explicit Runner Pinning (`ubuntu-24.04`)**:
   - Rather than relying on the moving target `ubuntu-latest` (which issued migration notices preparing for Ubuntu 26), all three workflow jobs explicitly pin `runs-on: ubuntu-24.04`.
   - This fixes OS kernel, system C libraries, Docker engine, and toolchain versions to a stable Long-Term Support release, eliminating surprise pipeline breakage.
2. **Official Node 24 Actions Upgrade (`v7`)**:
   - Upgraded core actions to `actions/checkout@v7`, `actions/setup-python@v7`, and `actions/setup-node@v7`.
   - These official major releases natively declare `using: 'node24'`, resolving the Node.js 20 deprecation notice.
3. **Least-Privilege Security**:
   - Preserved global `permissions: contents: read` to prevent workflow token privilege escalation.

### 4.10 Safe Teardown Protocol: Ephemeral CI Cleanup vs. Local Volume Preservation
A critical principle of containerized data safety is distinguishing disposable continuous integration environments from long-lived developer workstations:
1. **Local Developer Workflow (`docker compose down`)**:
   - Preserves named volume `cloudsentinel-data`.
   - When developers stop their containers at the end of the day, all historical metric samples, generated demo scenarios, and recorded incident evidence remain safe on disk.
2. **Automated CI Workflow (`docker compose down -v`)**:
   - Runs in the `always()` post-job hook on ephemeral cloud runners.
   - The volume was created seconds prior solely for the automated integration test script.
   - Deleting the test volume with `-v` frees runner disk space and prevents runner state pollution.
   - **Crucial Rule**: Never run `docker compose down -v` locally unless an intentional full factory reset is required.

---

## 5. Technical Glossary

A concise engineering reference defining foundational concepts utilized throughout CloudSentinel AI:

| Term | Technical Definition & CloudSentinel AI Context | Practical Example / Formula |
| :--- | :--- | :--- |
| **API** *(Application Programming Interface)* | A formal software interface defining how client components request and receive data from services. | In CloudSentinel AI, FastAPI defines the RESTful contract between the React SPA and backend services. |
| **REST** *(Representational State Transfer)* | A stateless architectural style for web services using standard HTTP methods (`GET`, `POST`) and explicit status codes. | `POST /api/detection/run` triggers detection; `GET /api/incidents` retrieves persisted incident records. |
| **JSON** *(JavaScript Object Notation)* | A lightweight, human-readable data serialization format using key-value pairs and arrays. | Used across all FastAPI endpoints and for persisting immutable evidence snapshots in SQLite (`observed_metric_evidence`). |
| **Database** | An organized collection of structured data stored electronically and accessed via a management engine. | Stores telemetry observations and operational incidents on disk. |
| **Relational Database** | A database organizing data into structured tables with schema constraints, typed columns, primary keys, and ACID guarantees. | CloudSentinel AI defines relational tables (`metric_samples`, `incidents`) with foreign key references and indexes. |
| **SQLite** | A self-contained, serverless, zero-configuration transactional SQL database engine running in-process. | Persists operational data directly to `backend/data/cloudsentinel.db` with Write-Ahead Logging (`WAL`) mode enabled. |
| **SQLAlchemy** | An enterprise Python SQL toolkit and Object Relational Mapper (ORM) translating Python classes to relational tables. | Declarative models `MetricSampleModel` and `IncidentModel` define schema fields, indexes, and session lifecycles. |
| **Telemetry** | Automated digital transmission and collection of operational performance metrics from services. | Time-series observations comprising `latency_ms`, `error_rate`, `cpu_usage_pct`, `memory_usage_pct`, and `request_count`. |
| **Anomaly** | An observation, pattern, or data point that deviates significantly from established baseline behavior. | An unexpected surge in error rate from normal $<0.01$ up to $0.35$ during a synthetic traffic spike. |
| **Baseline** | The statistical profile representing normal, steady-state system behavior. | CloudSentinel's synthetic baseline models healthy service traffic with mean latency ~42 ms and error rate $<0.01$. |
| **Threshold** | A static numerical limit configured by engineering teams beyond which observations are flagged as anomalous. | `latency_ms > 150.0` or `error_rate > 0.05`. Any sample exceeding either boundary triggers a finding. |
| **Precision** | The proportion of predicted anomaly alerts that are true ground-truth anomalies. Measures alert accuracy. | $\text{Precision} = \frac{\text{TP}}{\text{TP} + \text{FP}}$ (High precision prevents false alarms). |
| **Recall** | The proportion of actual ground-truth anomalies that were successfully flagged by the detector. Measures coverage. | $\text{Recall} = \frac{\text{TP}}{\text{TP} + \text{FN}}$ (High recall prevents unmonitored outages). |
| **F1 Score** | The harmonic mean of Precision and Recall, providing a balanced evaluation of detection quality. | $\text{F1} = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$. Both precision and recall depend directly on $\text{TP}$, $\text{FP}$, and $\text{FN}$ counts. On benchmark: Threshold $F_1 = 1.00$, IsolationForest $F_1 = 0.80$. |
| **False Positive (FP)** | An alert generated for an observation that is actually healthy/normal (Type I error). | IsolationForest flagged sample index 28 (healthy 31.88 ms latency with 152 requests) due to sparse subspace coordinates. |
| **False Negative (FN)** | An actual anomaly that the detector failed to identify (Type II error / missed detection). | IsolationForest missed 1 subtle injected anomaly whose coordinates clustered close to the normal training distribution. |
| **IsolationForest** | An unsupervised ensemble learning algorithm that isolates anomalies by building randomized decision trees. | Anomalies require significantly shorter tree path lengths to isolate than clustered normal points; scored via Scikit-Learn. |
| **Contamination** | An IsolationForest hyperparameter specifying the expected proportion of outliers in the training dataset. | Configured as `contamination=0.05` ($5\%$), defining the decision score offset boundary separating normal from anomalous samples. |
| **Docker** | A containerization engine packaging applications and runtime dependencies into lightweight, immutable containers. | Packages the Python 3.11 FastAPI backend and React/Nginx frontend into isolated container environments. |
| **Docker Compose** | A declarative tool for defining and orchestrating multi-container Docker applications via YAML configurations. | Orchestrates `frontend` and `backend` services on an internal bridge network (`cloudsentinel-network`) via `compose.yaml`. |
| **Named Volume** | A persistent Docker storage mechanism decoupled from container lifecycles. | Named volume `cloudsentinel-data` mounts to `/app/backend/data`, preserving SQLite database files across container restarts. |
| **Reverse Proxy** | An intermediate server receiving client traffic and routing requests to appropriate backend services. | Nginx Alpine listens on port 3000, serves SPA static assets, and forwards `/api/` and `/health` requests to FastAPI on port 8000. |
| **CORS** *(Cross-Origin Resource Sharing)* | A browser security protocol controlling whether scripts on one origin can request resources from a different origin. | Handled via FastAPI's `CORSMiddleware` in local dev; eliminated in Docker production mode via Nginx reverse proxying. |
| **CI/CD** *(Continuous Integration & Delivery)* | Automated software engineering pipeline building, linting, testing, and verifying code changes on every commit. | Automated multi-job pipeline ensuring regressions are caught before code is merged or released. |
| **GitHub Actions** | A cloud-native CI/CD automation runner built into GitHub executing declarative workflow jobs on Ubuntu runners. | Executes 3 parallel jobs: `Frontend Lint & Build`, `Backend Tests & ML Evaluation`, and `Docker Compose Integration & Persistence`. |
| **Idempotence** | An operational property ensuring that executing an action multiple times produces the exact same end state. | Running detection repeatedly against the same telemetry creates 0 duplicate incidents, incrementing `already_existing` counts. |
| **SHA-256 Fingerprint** | A deterministic cryptographic hash generating a unique 32-byte (64 hex character) digest from an input vector. | CloudSentinel AI hashes `service`, `detector:version`, `config`, `timestamp`, and `sorted_metrics`, storing `service:detector:sha256[:32]` in `dedup_key`. |


