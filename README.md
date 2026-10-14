# CloudSentinel AI

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
- **Day 3: Quality, Docker & GitHub Actions CI** *(Planned)*
- **Day 4: End-to-End Verification, Documentation & Demo** *(Planned)*

---

## Notice on Telemetry & Prototype Scope
All metric observations ingested and displayed by CloudSentinel AI are **strictly synthetic** and generated deterministically with isolated random seeds and explicit UTC reference timestamps.

CloudSentinel AI is a portfolio-grade reliability engineering prototype. It provides factual mathematical evidence (threshold boundaries and IsolationForest decision scores) and does NOT claim automated root-cause diagnosis or production monitoring.

---

## Technology Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Frontend UI** | React 18 + TypeScript + Vite | Reactive dashboard, action controls toolbar, KPI cards, observations table, and incident evidence modal |
| **Backend API** | Python 3.11 + FastAPI + Uvicorn | ASGI web service, route handlers, CORS middleware, detection pipeline |
| **Persistence** | SQLite + SQLAlchemy 2.x | ACID persistence for metric samples and deduplicated incident evidence snapshots |
| **Machine Learning** | Scikit-Learn (IsolationForest) + NumPy | Unsupervised multivariate anomaly detection with reproducible random seeds |
| **Validation** | Pydantic v2 | Strict request validation, response serialization, and timestamp normalization |
| **Testing** | pytest + TestClient + Google Chrome CDP | 96-test automated backend suite + 11-test real Google Chrome browser QA journey |
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
│   │   │   └── incident_service.py  # Service layer: detection, deduplication, persistence
│   │   ├── db/
│   │   │   ├── base.py           # DeclarativeBase
│   │   │   └── session.py        # SQLite engine, SessionLocal, and init_db() sync
│   │   ├── config.py             # Settings, CORS origins, and SQLite database path
│   │   └── main.py               # FastAPI application factory and router registration
│   ├── tests/
│   │   ├── conftest.py           # In-memory SQLite fixtures and test clients
│   │   ├── test_health.py        # Health route tests (3 tests)
│   │   ├── test_metrics.py       # Telemetry route tests (15 tests)
│   │   ├── test_persistence.py   # Database lifecycle tests (6 tests)
│   │   ├── test_demo_generation.py # Anomaly injection tests (15 tests)
│   │   ├── test_threshold_detector.py # Threshold detector tests (18 tests)
│   │   ├── test_ml_detector.py   # IsolationForest detector tests (18 tests)
│   │   ├── test_incidents.py     # Incident generation & deduplication tests (21 tests)
│   │   ├── automated_browser_qa.py   # Day 1 Chrome CDP browser runner (29 tests)
│   │   └── milestone5_browser_qa.py  # Day 2 Milestone 5 Chrome CDP runner (11 tests)
│   └── requirements.txt          # Python dependencies
├── docs/
│   ├── learning-notes.md         # Comprehensive engineering & learning guide
│   ├── day1_automated_browser_qa_report.md     # Day 1 browser QA report
│   ├── milestone5_browser_qa_report.md # Milestone 5 browser QA report
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
Open a PowerShell terminal in the repository root:

```powershell
cd C:\Users\USER\.gemini\antigravity-ide\scratch\cloudsentinel-ai

# Activate virtual environment
.\backend\.venv\Scripts\Activate.ps1

# Run FastAPI backend service
.\backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
FastAPI runs at `http://127.0.0.1:8000`. Swagger documentation is available at `http://127.0.0.1:8000/docs`.

### 2. Frontend Setup & Startup
Open a second PowerShell terminal in the repository root:

```powershell
cd C:\Users\USER\.gemini\antigravity-ide\scratch\cloudsentinel-ai\frontend

# Start the Vite development server
npm run dev -- --host 127.0.0.1 --port 5173
```
Dashboard is served at `http://127.0.0.1:5173`.

---

## API Endpoints Specification

### 1. `GET /health`
Readiness probe returning backend health and database connectivity.

### 2. `GET /api/metrics`
Retrieve persisted or synthetic metrics ordered descending by timestamp.

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
Execute anomaly detection pipeline against persisted metrics in SQLite.
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

### 1. Backend pytest Suite (96 Tests, 100% Pass)
```powershell
cd C:\Users\USER\.gemini\antigravity-ide\scratch\cloudsentinel-ai
.\backend\.venv\Scripts\python.exe -m pytest -v
```
*Result*: **96 passed, 0 failed** in ~8.3s across all 7 test modules.

### 2. Frontend Production Build
```powershell
cd C:\Users\USER\.gemini\antigravity-ide\scratch\cloudsentinel-ai\frontend
npm run build
```
*Result*: TypeScript compilation check (`tsc -b`) and Vite production bundle passed in 1.07s.

### 3. Real Google Chrome Automated Browser QA
```powershell
cd C:\Users\USER\.gemini\antigravity-ide\scratch\cloudsentinel-ai
.\backend\.venv\Scripts\python.exe backend\tests\milestone5_browser_qa.py
```
*Result*: **11/11 PASSED (100%)** in Google Chrome via Chrome DevTools Protocol (CDP):
* Initial health connection verification.
* Synthetic telemetry generation with 5 injected anomalies.
* KPI cards and observations table updates.
* Threshold detection execution and incident table populating.
* Threshold incident evidence modal inspection (measurements vs rules).
* IsolationForest detection execution and multivariate incident populating.
* IsolationForest evidence modal inspection (decision score & model parameters).
* Duplicate prevention on repeated detection run (0 new incidents created).
* Browser reload and state persistence from SQLite.
* Mobile viewport (390×844) responsive layout check.
* Console error audit (0 errors) and network check (0 failed requests).

**Captured Visual Evidence:**
* Report: [`docs/milestone5_browser_qa_report.md`](docs/milestone5_browser_qa_report.md)
* Initial Dashboard State: [`docs/screenshots/milestone5_01_initial_state.png`](docs/screenshots/milestone5_01_initial_state.png)
* Generated Metrics: [`docs/screenshots/milestone5_02_metrics_generated.png`](docs/screenshots/milestone5_02_metrics_generated.png)
* Threshold Incidents: [`docs/screenshots/milestone5_03_threshold_incidents.png`](docs/screenshots/milestone5_03_threshold_incidents.png)
* Threshold Evidence Modal: [`docs/screenshots/milestone5_04_threshold_evidence_modal.png`](docs/screenshots/milestone5_04_threshold_evidence_modal.png)
* IsolationForest Evidence Modal: [`docs/screenshots/milestone5_05_ml_evidence_modal.png`](docs/screenshots/milestone5_05_ml_evidence_modal.png)
* Mobile Responsive Viewport: [`docs/screenshots/milestone5_06_mobile_responsive.png`](docs/screenshots/milestone5_06_mobile_responsive.png)
* Full Persisted Dashboard: [`docs/screenshots/milestone5_07_full_dashboard.png`](docs/screenshots/milestone5_07_full_dashboard.png)

---

## Known Limitations & Milestone 6 Roadmap

* **Reference Baseline Training**: IsolationForest is fitted on a deterministic clean baseline generated from Seed 100 with zero injected anomalies. Formal comparative evaluation (precision, recall, F1-score) will be executed in Milestone 6.
* **No Root Cause Diagnosis**: Anomaly detection identifies statistical outliers and does not infer root causes.
* **Single Service Focus**: Default configuration focuses on `demo-api`. Multi-service cross-correlation is planned for future milestones.
