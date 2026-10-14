# CloudSentinel AI

[![CloudSentinel AI CI](https://github.com/ARKkhanz/cloudsentinel-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/ARKkhanz/cloudsentinel-ai/actions/workflows/ci.yml)

> **An AI-assisted cloud reliability prototype that detects unusual service metrics, creates evidence-backed incidents, and helps a developer investigate them.**

Developed as a four-day engineering project following the *CloudSentinel AI Implementation & Learning Blueprint*.

---

## Project Status

- **Day 1: Skeleton + Real API + Connected Dashboard**
  - [x] **Milestone 0**: Repository & GitHub setup (`main` branch, `.gitignore`, `.env.example`, initial structure)
  - [x] **Milestone 1**: Minimal FastAPI backend + deterministic synthetic metric generator
  - [x] **Milestone 2**: Automated backend test suite with `pytest` (17 tests, 100% pass)
  - [x] **Milestone 3**: React + TypeScript + Vite frontend skeleton and centralized API client
  - [x] **Milestone 4**: Connected React dashboard displaying real FastAPI data, error banners, and stale state handling
  - [x] **Milestone 5**: Full test suite verification, build checks, and comprehensive documentation
- **Day 2: Persistence, Anomaly Detection & Incident Workflow**
  - [x] **Milestone 1**: SQLite database persistence with SQLAlchemy 2.x ORM models (`MetricSampleModel`, `IncidentModel`)
  - [x] **Milestone 2**: Reproducible synthetic anomaly generator with controlled latency spikes and error surges
  - [x] **Milestone 3**: Transparent threshold baseline anomaly detector (`ThresholdDetector`)
  - [x] **Milestone 4**: Multivariate `IsolationForest` anomaly detector with Scikit-Learn
  - [x] **Milestone 5**: Incident generation, evidence preservation, deduplication, FastAPI APIs, and React dashboard integration
  - [x] **Milestone 6**: Reproducible ML evaluation, reliability hardening (schema migration logging & SHA-256 fingerprint deduplication), comprehensive documentation, and final Day 2 verification
- **Day 3: Quality, Docker & GitHub Actions CI**
  - [x] **Milestone 1**: Engineering quality, dependency hygiene, ESLint 10, and security review
  - [x] **Milestone 2**: Secure backend and frontend Dockerfiles + production Nginx configuration
  - [x] **Milestone 3**: Docker Compose multi-container orchestration, networking, and SQLite volume persistence
  - [x] **Milestone 4**: GitHub Actions CI workflow + real Docker multi-container integration and SQLite persistence verification
  - [x] **Milestone 5**: Final Day 3 quality gate, CI hardening (`ubuntu-24.04` & Node 24 runtime), volume safety, and engineering audit
- **Day 4: Final Verification, Presentation & Portfolio Delivery** *(Planned)*

---

## Notice on Telemetry & Prototype Scope
All metric observations ingested and displayed by CloudSentinel AI are **strictly synthetic** and generated deterministically with isolated random seeds and explicit UTC reference timestamps.

CloudSentinel AI is a portfolio-grade reliability engineering prototype. It provides factual mathematical evidence (threshold boundaries and IsolationForest decision scores) and does **NOT** claim automated root-cause diagnosis, production monitoring, or outage forecasting.

---

## Technology Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Frontend UI** | React 18 + TypeScript + Vite | Reactive dashboard, action controls toolbar, KPI cards, observations table, and incident evidence modal |
| **Backend API** | Python 3.11 + FastAPI + Uvicorn | ASGI web service, route handlers, CORS middleware, detection pipeline |
| **Persistence** | SQLite + SQLAlchemy 2.x | ACID persistence for metric samples and deduplicated incident evidence snapshots |
| **Machine Learning** | Scikit-Learn (IsolationForest) + NumPy | Unsupervised multivariate anomaly detection with reproducible random seeds |
| **Validation** | Pydantic v2 | Strict request validation, response serialization, and timestamp normalization |
| **Evaluation** | Standalone Benchmark Script | Confusion matrices, Precision, Recall, F1-Score, and False-Positive Rate calculations |
| **Testing** | pytest + TestClient + Google Chrome CDP | 114-test automated backend suite + 11-test real Google Chrome browser QA journey |
| **Version Control** | Git + GitHub CLI | Checked-in milestones, verified commits on GitHub `main` branch |

---

## Repository Structure

```text
cloudsentinel-ai/
├── frontend/                     # React + TypeScript + Vite Dashboard
│   ├── src/
│   │   ├── api/
│   │   │   └── client.ts         # Centralized HTTP client (metrics, demo generate, detection, incidents)
│   │   ├── types/
│   │   │   ├── metrics.ts        # TypeScript interfaces for health & metrics
│   │   │   └── incidents.ts      # TypeScript interfaces for detection runs & incidents
│   │   ├── App.tsx               # Reactive dashboard container, action controls, and evidence modal
│   │   ├── main.tsx              # React DOM mounting entry point
│   │   ├── index.css             # Polished dark-mode styling, action buttons, and modal dialogs
│   │   └── vite-env.d.ts         # Vite client type definitions
│   ├── package.json              # Frontend dependencies and build scripts
│   ├── tsconfig.json             # Root TypeScript configuration
│   └── vite.config.ts            # Vite dev server configuration (127.0.0.1:5173)
├── backend/                      # FastAPI Python Web Service
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes_health.py    # GET /health
│   │   │   ├── routes_metrics.py   # GET /api/metrics & POST /api/metrics
│   │   │   ├── routes_demo.py      # POST /api/demo/generate
│   │   │   ├── routes_detection.py # POST /api/detection/run
│   │   │   └── routes_incidents.py # GET /api/incidents & GET /api/incidents/{id}
│   │   ├── detection/
│   │   │   ├── threshold_detector.py        # Statistical threshold baseline detector
│   │   │   └── isolation_forest_detector.py # Multivariate IsolationForest detector
│   │   ├── models/
│   │   │   ├── metric.py         # SQLAlchemy MetricSampleModel
│   │   │   └── incident.py       # SQLAlchemy IncidentModel with dedup_key
│   │   ├── schemas/
│   │   │   ├── metrics.py        # Pydantic telemetry models
│   │   │   ├── demo.py           # Pydantic synthetic generation models
│   │   │   └── incidents.py      # Pydantic detection and incident models
│   │   ├── services/
│   │   │   ├── metric_generator.py  # Seeded telemetry generator
│   │   │   ├── anomaly_generator.py # Controlled anomaly injector with ground truth
│   │   │   └── incident_service.py  # Service layer: detection, SHA-256 fingerprint dedup, persistence
│   │   ├── db/
│   │   │   ├── base.py           # DeclarativeBase
│   │   │   └── session.py        # SQLite engine, SessionLocal, and hardened init_db() sync
│   │   ├── config.py             # Settings, CORS origins, and SQLite database path
│   │   └── main.py               # FastAPI application factory and router registration
│   ├── scripts/
│   │   └── evaluate_detectors.py # Reproducible detector benchmark evaluation script
│   ├── tests/
│   │   ├── conftest.py           # In-memory SQLite fixtures and test clients
│   │   ├── test_health.py        # Health route tests (3 tests)
│   │   ├── test_metrics.py       # Telemetry route tests (15 tests)
│   │   ├── test_persistence.py   # Database lifecycle and schema migration tests (11 tests)
│   │   ├── test_demo_generation.py # Anomaly injection tests (15 tests)
│   │   ├── test_threshold_detector.py # Threshold detector tests (18 tests)
│   │   ├── test_ml_detector.py   # IsolationForest detector tests (18 tests)
│   │   ├── test_incidents.py     # Incident generation & fingerprint deduplication tests (25 tests)
│   │   ├── test_evaluation.py    # Metric mathematics & benchmark reproducibility tests (9 tests)
│   │   ├── automated_browser_qa.py   # Day 1 Chrome CDP browser runner (29 tests)
│   │   ├── milestone5_browser_qa.py  # Day 2 Milestone 5 Chrome CDP runner (11 tests)
│   │   └── milestone6_browser_qa.py  # Day 2 Milestone 6 Chrome CDP runner (11 tests)
│   └── requirements.txt          # Python dependencies
├── docs/
│   ├── learning-notes.md         # Comprehensive Day 1 & Day 2 engineering and learning notes
│   ├── experiment-results.md     # Full empirical evaluation report with confusion matrices and analysis
│   ├── day1_automated_browser_qa_report.md     # Day 1 browser QA report
│   ├── milestone5_browser_qa_report.md # Milestone 5 browser QA report
│   ├── milestone6_browser_qa_report.md # Milestone 6 browser QA report
│   └── screenshots/              # Real browser visual proof captures
├── .env.example                  # Root environment template
├── .gitignore                    # Python, Node, OS, and secret exclusion rules
└── README.md                     # Project documentation
```

---

## Local Setup & Startup Guide (Windows / PowerShell)

### Prerequisites
* **Python 3.10+** (tested on Python 3.11.9)
* **Node.js 18+ & npm** (tested on Node v24.19.0 / npm 11.17.0)
* **Google Chrome** (tested on Chrome v141)

### 1. Backend Setup & Startup
Open a terminal in the repository root:

```bash
# Clone and enter directory
cd cloudsentinel-ai

# Activate virtual environment (Windows PowerShell)
.\backend\.venv\Scripts\Activate.ps1
# Or on Linux/macOS:
# source backend/.venv/bin/activate

# Run FastAPI backend service from repository root
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
FastAPI runs at `http://127.0.0.1:8000`. Swagger documentation is available at `http://127.0.0.1:8000/docs`.

### 2. Frontend Setup & Startup
Open a second terminal in the repository root:

```bash
cd frontend

# Start the Vite development server
npm run dev -- --host 127.0.0.1 --port 5173
```
Dashboard is served at `http://127.0.0.1:5173`.

---

## Reproducible Machine Learning Evaluation

To run the reproducible benchmark comparing `ThresholdDetector` and `IsolationForestDetector` against held-out telemetry:

```bash
# From repository root with virtual environment active:
python backend/scripts/evaluate_detectors.py
```

### Benchmark Summary (Seed 100 Train, Seed 42 Held-out Eval)

| Metric | Threshold Baseline | IsolationForest |
| :--- | :---: | :---: |
| **Evaluated Samples** | 100 | 100 |
| **Ground-Truth Anomalies** | 5 | 5 |
| **Predicted Anomalies** | 5 | 5 |
| **True Positives (TP)** | 5 | 4 |
| **False Positives (FP)** | 0 | 1 |
| **True Negatives (TN)** | 95 | 94 |
| **False Negatives (FN)** | 0 | 1 |
| **Precision** | **1.0000 (100.0%)** | **0.8000 (80.0%)** |
| **Recall** | **1.0000 (100.0%)** | **0.8000 (80.0%)** |
| **F1 Score** | **1.0000** | **0.8000** |
| **False-Positive Rate** | **0.0000 (0.00%)** | **0.0105 (1.05%)** |

Detailed scientific analysis, confusion matrices, and qualitative false-positive/negative breakdown are available in [`docs/experiment-results.md`](docs/experiment-results.md).

---

## API Endpoints Specification

### 1. `GET /health`
Readiness probe returning backend health and database connectivity.

### 2. `GET /api/metrics`
Retrieve persisted metrics ordered descending by timestamp.
* Query parameters: `service` (default `demo-api`), `limit` (default 50, max 200).
* *Note on Display Limit*: When generating 100 demo observations, the dashboard fetches and displays the most recent 50 observations in the table by default to maintain responsive UI rendering, while all 100 samples are stored in SQLite and evaluated by detectors.

### 3. `POST /api/demo/generate`
Generate and persist reproducible synthetic telemetry with controlled anomaly injections.
* **Payload**:
  ```json
  {
    "service": "demo-api",
    "total_samples": 100,
    "seed": 42,
    "latency_spike_count": 3,
    "error_spike_count": 2,
    "replace_existing": true
  }
  ```

### 4. `POST /api/detection/run`
Execute anomaly detection pipeline against persisted metrics in SQLite with SHA-256 fingerprint deduplication.
* **Supported Detectors**:
  * `"threshold_baseline"`: Evaluates against latency (>150ms) and error rate (>5%) boundaries.
  * `"isolation_forest"`: Evaluates multivariate metrics with IsolationForest fitted on clean reference baseline (Seed 100, 100 samples).
* **Payload**:
  ```json
  {
    "service": "demo-api",
    "detector": "threshold_baseline",
    "limit": 100
  }
  ```
* **Response**: Reports `samples_analyzed`, `findings_count`, `incidents_created`, and `incidents_already_existing`.

### 5. `GET /api/incidents`
Retrieve persisted incidents with optional filtering by `service`, `status`, `detector_name`, and `limit` (ordered newest first).

### 6. `GET /api/incidents/{id}`
Retrieve complete persisted incident information including observed measurements and baseline evidence snapshot.

---

## Verification & Testing Suite

### 1. Backend pytest Suite (114 Tests, 100% Pass)
```bash
# From repository root:
pytest -v
```
*Result*: **114 passed, 0 failed** in ~13.1s across all 8 test modules.

### 2. Frontend Production Build
```bash
cd frontend
npm run build
```
*Result*: TypeScript compilation check (`tsc -b`) and Vite production bundle passed in 1.02s.

### 3. Real Google Chrome Automated Browser QA
```bash
# From repository root with backend and frontend running:
python backend/tests/milestone6_browser_qa.py
```
*Result*: **11/11 PASSED (100%)** in Google Chrome via Chrome DevTools Protocol (CDP):
* Initial health connection verification.
* Synthetic telemetry generation with 5 injected anomalies.
* KPI cards and observations table updates (50 rows displayed, 100 in SQLite).
* Threshold detection execution and incident table populating.
* Threshold incident evidence modal inspection (measurements vs rules).
* IsolationForest detection execution and multivariate incident populating.
* IsolationForest evidence modal inspection (decision score & model parameters).
* Duplicate prevention on repeated detection run (0 new incidents created via SHA-256 fingerprinting).
* Browser reload and state persistence from SQLite.
* Mobile viewport (375×667) responsive layout check.
* Console error audit (0 errors) and network check (0 failed requests).

**Captured Visual Evidence:**
* Report: [`docs/milestone6_browser_qa_report.md`](docs/milestone6_browser_qa_report.md)
* Initial Dashboard State: [`docs/screenshots/milestone6_01_initial_dashboard.png`](docs/screenshots/milestone6_01_initial_dashboard.png)
* Generated Metrics: [`docs/screenshots/milestone6_02_metrics_generated.png`](docs/screenshots/milestone6_02_metrics_generated.png)
* Threshold Incidents: [`docs/screenshots/milestone6_03_threshold_detection.png`](docs/screenshots/milestone6_03_threshold_detection.png)
* Threshold Evidence Modal: [`docs/screenshots/milestone6_04_threshold_evidence_modal.png`](docs/screenshots/milestone6_04_threshold_evidence_modal.png)
* IsolationForest Detection: [`docs/screenshots/milestone6_05_isolation_forest_detection.png`](docs/screenshots/milestone6_05_isolation_forest_detection.png)
* IsolationForest Evidence Modal: [`docs/screenshots/milestone6_06_ml_evidence_modal.png`](docs/screenshots/milestone6_06_ml_evidence_modal.png)
* Persisted Across Reload: [`docs/screenshots/milestone6_07_persisted_after_reload.png`](docs/screenshots/milestone6_07_persisted_after_reload.png)
* Mobile Responsive Viewport: [`docs/screenshots/milestone6_08_mobile_responsive.png`](docs/screenshots/milestone6_08_mobile_responsive.png)

---

## Container Orchestration (Docker Compose)

CloudSentinel AI supports multi-container orchestration via root-level `compose.yaml`:

```bash
# Build images and start services in detached mode
docker compose up --build -d

# Verify service health and port mappings
docker compose ps

# Access services:
# React Dashboard:    http://localhost:3000
# Backend Health:     http://localhost:3000/health (proxied via Nginx)
# Backend Swagger:    http://localhost:8000/docs   (direct loopback)

# Stop services preserving SQLite volume data
docker compose down
```

> [!WARNING]
> **Data Safety Distinction (`docker compose down` vs. `-v`)**:
> - **Routine Local Shutdown**: Developers and operators MUST run `docker compose down` (without `-v`). This gracefully tears down container namespaces and bridge networking while preserving the named SQLite volume (`cloudsentinel-data`), keeping all ingested metrics and recorded incident evidence intact across reboots.
> - **CI Disposable Teardown**: In automated GitHub Actions CI pipelines, `docker compose down -v` is explicitly executed after tests complete. This is safe ONLY because CI runners are ephemeral, disposable sandbox virtual machines where temporary test volumes must be cleaned up to prevent runner disk leakage. **Never run `docker compose down -v` on a production or long-lived local development environment unless you intentionally wish to permanently destroy all database records.**

> [!NOTE]
> Detailed container architecture, volume lifecycle, and verification matrices are documented in [`docs/milestone-3-orchestration.md`](docs/milestone-3-orchestration.md).

---

## Continuous Integration (GitHub Actions)

CloudSentinel AI runs an automated, multi-job continuous integration pipeline pinned to stable LTS GitHub-hosted `ubuntu-24.04` runners using official Node 24 actions:

* **Workflow**: [`.github/workflows/ci.yml`](.github/workflows/ci.yml)
* **Runner Environment**: `ubuntu-24.04` (pinned LTS release for deterministic toolchain reproducibility)
* **Action Runtimes**: Official GitHub Actions (`actions/checkout@v7`, `actions/setup-python@v7`, `actions/setup-node@v7`) running natively on Node 24.
* **Verified CI Workflow Run**: [Run #38593311494 (100% Green)](https://github.com/ARKkhanz/cloudsentinel-ai/actions/runs/38593311494)

### Automated Pipeline Jobs

1. **`backend-tests`** (Ubuntu 24.04, Python 3.11):
   - Executes full 114-test regression suite (`pytest -v`).
   - Executes standalone detector evaluation benchmark (`evaluate_detectors.py`).
2. **`frontend-checks`** (Ubuntu 24.04, Node.js 24):
   - Runs clean install (`npm ci`) with dependency caching.
   - Executes ESLint linter (`npm run lint`, 0 warnings/errors).
   - Executes TypeScript compiler check and Vite production bundle (`npm run build`).
3. **`docker-integration`** (Ubuntu 24.04, Real Docker Engine & Compose):
   - Validates Compose specification (`docker compose config --quiet`).
   - Builds container images (`docker compose build`).
   - Starts multi-container stack (`docker compose up -d`).
   - Verifies direct health (`:8000/health`) and proxied Nginx health (`:3000/health`).
   - Tests telemetry generation, threshold detection, and IsolationForest anomaly detection.
   - Tests incident deduplication (0 duplicate incidents created on repeated run).
   - Tests SQLite named volume persistence across container recreation (`docker compose down` -> `docker compose up -d`).
   - Safely tears down disposable containers and test volumes upon completion (`docker compose down -v`).

---

## Known Limitations

* **Synthetic Data Prototype**: All telemetry is synthetically generated to demonstrate detection principles and evidence workflows without cloud infrastructure dependencies.
* **No Root Cause Diagnosis**: Anomaly detection identifies statistical outliers and does not infer root causes.
* **Contamination Prior**: The contamination parameter in IsolationForest is a modeling assumption (outlier budget), not an empirical ground-truth rate.
* **Static Thresholds**: Threshold rules require operational tuning and do not adapt dynamically to evolving traffic baselines.
