# CloudSentinel AI — Technical Evaluator Verification Guide

> **An evidence-backed reliability engineering prototype that ingests synthetic cloud service telemetry, detects operational anomalies via transparent threshold rules and multivariate IsolationForest machine learning, deduplicates alert incidents via cryptographic fingerprinting, and provides factual numerical evidence for developer investigation.**

---

## 1. Project Purpose in Plain English

Modern cloud infrastructure produces high-velocity telemetry (latency, error rates, resource utilization). Detecting and triaging operational anomalies presents two classic reliability engineering challenges:
1. **Alert Fatigue**: Naive detection rules spam on-call engineers with duplicate alerts for ongoing degradation.
2. **Opaque "Black Box" Warnings**: Anomaly alerts often fail to explain *why* an observation was flagged, leaving developers without verifiable evidence.

**CloudSentinel AI** demonstrates an end-to-end, reproducible solution to both problems:
- **Dual Detection Paradigms**: A deterministic **Threshold Baseline Detector** (`latency_ms > 150.0`, `error_rate > 0.05`) and an unsupervised **IsolationForest Machine Learning Detector** (evaluating 5 multivariate features: `latency_ms`, `error_rate`, `cpu_usage_pct`, `memory_usage_pct`, `request_count`).
- **Factual Evidence Chains**: Every created incident preserves an immutable snapshot of observed telemetry measurements alongside explicit mathematical boundaries (threshold excess or decision path score).
- **Canonical SHA-256 Deduplication**: Incidents compute a deterministic SHA-256 fingerprint over the service, detector identity, configuration summary, observation timestamp, and canonicalized numerical measurements, guaranteeing that repeat detection passes create **zero duplicate alerts**.
- **Unified Interface**: A responsive React 18 + TypeScript single-page application (using standard React hooks and native `fetch`) served either standalone via Vite or behind an Nginx reverse proxy.

---

## 2. System Architecture & Real API Contract

```text
[Synthetic Telemetry Generator]
       │ (100 samples, 5 injected spikes: Seed 42)
       ▼
[SQLite Storage Engine: metric_samples]
       │
       ▼
[Incident Service Layer]
   ├──> Threshold Baseline Detector (latency_ms > 150.0ms, error_rate > 0.05)
   └──> IsolationForest ML Detector (5 features: latency, error, cpu, mem, requests)
       │
       ▼
[Deterministic SHA-256 Deduplication]
       │ (Fingerprint: service:detector:sha256[:32] -> dedup_key)
       ▼
[SQLite Storage Engine: incidents]
       │ (Stores immutable evidence snapshots)
       ▼
[FastAPI REST API]
       │ GET  /health              -> Application process responsiveness check
       │ GET  /api/metrics         -> Query persisted telemetry observations
       │ POST /api/metrics         -> Ingest single validated metric observation
       │ POST /api/demo/generate   -> Seed synthetic telemetry with injected anomalies
       │ POST /api/detection/run   -> Trigger detection pipeline & generate incidents
       │ GET  /api/incidents       -> Retrieve persisted incident records (newest first)
       │ GET  /api/incidents/{id}  -> Retrieve full evidence payload for specific incident
       ▼
[Nginx Reverse Proxy / Vite Server]
       │ (Port 3000 in Docker / Port 5173 in Dev)
       ▼
[React 18 TypeScript Dashboard]
   - Service Health Status Badge
   - Metric KPI Summary Cards
   - Telemetry Observation Table (Latest 50 rows displayed, 100 persisted)
   - Incidents Table & Severity Badges
   - Forensic Evidence Inspection Modal
```

---

## 3. Journey A: Quick Demonstration (~3 Minutes)

> [!NOTE]
> **Scope Clarification**: The ~3-minute estimate assumes a developer or evaluator has already installed prerequisites and started the backend and frontend services. For a complete fresh machine installation from scratch, see [Journey B](#4-journey-b-fresh-reproduction-from-clean-machine).

### Step 1: Open the Dashboard
Navigate to:
- **Local Dev Server**: [`http://127.0.0.1:5173`](http://127.0.0.1:5173) (or `http://localhost:5173`)
- **Docker Compose Stack**: [`http://localhost:3000`](http://localhost:3000)

**What to Observe**:
- The header displays the **CloudSentinel AI** title and an online badge: `Backend: Online (cloudsentinel-backend v0.1.0)`.
- If the database is fresh, the observation table displays *"No telemetry observations persisted for this service yet. Click 'Generate Synthetic Data' to seed the database."*

### Step 2: Generate Canonical Synthetic Telemetry
Click the primary button in the action toolbar:
```text
[ ⚡ Generate Synthetic Data ]
```

**What to Observe**:
- An emerald feedback banner appears:
  `Successfully generated and persisted 100 observations with 5 injected anomalies for 'demo-api'.`
- **KPI Summary Cards Update**:
  - *Monitored Service*: `demo-api` (footer shows `50 samples (descending)`)
  - *Average Latency*: ~66.2 ms (baseline mean ~42ms + 3 injected spikes)
  - *Average Error Rate*: ~1.5% (baseline mean ~0.5% + 2 injected surges)
  - *Total Requests*: ~4,000+
  - *Avg CPU / Memory*: Displays calculated window averages
- **Observations Table**: Populates with chronological telemetry rows (Timestamp, Service, Latency, Error Rate, Requests, CPU, Memory, Data Source: `SYNTHETIC`).
- **Display Limit Notice**: The table shows the latest 50 observations to maintain snappy browser DOM rendering; all 100 observations are safely persisted in SQLite. Individual rows show a `SYNTHETIC` source tag—anomalies are identified and surfaced strictly by the detection engines in the incidents panel.

### Step 3: Run Threshold Baseline Anomaly Detection
Click the second action button:
```text
[ 📊 Run Threshold Detection ]
```

**What to Observe**:
- A feedback banner confirms:
  `Threshold Detection completed on 100 samples: 5 findings, 5 new incidents created (0 deduplicated).`
- **Active Incidents Table Populates**: 5 threshold incident rows appear:
  - Detector: `THRESHOLD_BASELINE` (v1.0.0).
  - Severities: `WARNING` (for latency spikes exceeding 150.0ms) or `CRITICAL` (for error rate surges exceeding 0.05 / 5.0%).
  - Headlines: Factual summary (e.g., *"Elevated Latency on demo-api (503.7 ms)"* or *"High Error Rate on demo-api (16.2%)"*).

### Step 4: Inspect Factual Numerical Evidence
On any incident row, click the **View Evidence** button:
```text
[ View Evidence ]
```

**What to Observe**:
- The **Incident Investigation Modal** opens.
- **Observed Numerical Metric Measurements**: Displays the exact readings at the time of observation (e.g., Latency: `503.72 ms`, Error Rate: `0.92%`, Requests: `42`, CPU: `34.1%`, Memory: `58.2%`).
- **Baseline / Detector Evidence Comparison**:
  - Displays configured rule boundaries (`latency_ms > 150.0`, `error_rate > 0.05`).
  - Explanation details the exact threshold exceeded and the measured delta.
- Click **Close** (`✕`) or press Escape to dismiss the modal.

### Step 5: Run IsolationForest Multivariate ML Detection
Click the third action button:
```text
[ 🌲 Run IsolationForest Detection ]
```

**What to Observe**:
- A feedback banner confirms:
  `IsolationForest Detection completed on 100 samples: 5 findings, 5 new incidents created (0 deduplicated).`
- **Active Incidents Table Updates**: Total incidents increase from 5 to 10.
- 5 new incidents display the purple `ISOLATION_FOREST` badge (v1.0.0).

### Step 6: Inspect Machine Learning Anomaly Score
Click **View Evidence** on any `ISOLATION_FOREST` incident row:

**What to Observe**:
- The modal reveals multivariate evidence:
  - *Decision Score*: A negative score (e.g., `-0.0011` to `-0.0373`). Negative values indicate geometric outlier isolation in fewer random partition splits than reference normal density.
  - *Classification Label*: `-1 (Outlier)`.
  - *Model Parameters*: `n_estimators=100`, `contamination=0.05`, `training_sample_count=100 normal samples`.
  - *Evaluated Features*: 5 canonical numerical metrics (`latency_ms`, `error_rate`, `cpu_usage_pct`, `memory_usage_pct`, `request_count`).
- Click **Close** (`✕`).

### Step 7: Demonstrate Deduplication (Alert Fatigue Prevention)
Click **📊 Run Threshold Detection** a second time:
```text
[ 📊 Run Threshold Detection ]
```

**What to Observe**:
- The feedback banner confirms:
  `Threshold Detection completed on 100 samples: 5 findings, 0 new incidents created (5 deduplicated).`
- The incident table row count **remains exactly 10**.
- Zero duplicate records are created because the canonical SHA-256 fingerprint matches existing incident `dedup_key` values in SQLite.

### Step 8: Confirm SQLite Persistence Across Page Reload
Press `F5` or `Ctrl+R` in your browser to reload the page.

**What to Observe**:
- All 10 incidents, all KPI calculations, and the 50 displayed telemetry rows immediately reappear from the SQLite database.

---

## 4. Journey B: Fresh Reproduction from Clean Machine

*Designed for an evaluator reproducing the project from scratch on a clean workstation.*

> [!NOTE]
> **Evaluation Mode & Environment Distinction**:
> - **Prepared Demonstration (Journey A)**: Validates functional workflows, UI state, and deduplication against a prepared local or containerized deployment in ~3 minutes.
> - **Fresh-Machine Reproduction (Journey B)**: Validates cloning into an empty workspace, creating virtual environments, installing clean dependencies, running builds, and starting services from scratch.
> - **Local Windows Workstation Execution**: Validates standalone Python 3.11 backend and React 18 Vite SPA development runtimes directly.
> - **GitHub-Hosted Linux Docker Execution**: Automatically validates multi-container Docker Compose build, health checks, internal bridge networking, and SQLite named volume persistence on `ubuntu-24.04` cloud runners.

### Supported Prerequisites
| Component | Supported Version | Notes |
| :--- | :--- | :--- |
| **Operating System** | Windows 10/11, Linux, macOS | Cross-platform Python & Node |
| **Python** | 3.11.x (tested on 3.11.9) | Requires `pip` and `venv` |
| **Node.js** | 20.x, 22.x, or 24.x (tested on 24.19.0) | Requires `npm` (tested on 11.17.0) |
| **Git** | 2.40+ | For cloning and version checks |
| **Google Chrome (Optional)** | 120+ | Required only if executing automated Chrome QA suite |
| **Docker (Optional)** | Engine 24+, Compose v2 | Only needed if evaluating container mode |

---

### Step-by-Step Installation & Startup

#### 1. Clone the Repository
```bash
git clone https://github.com/ARKkhanz/cloudsentinel-ai.git
cd cloudsentinel-ai
```

#### 2. Set Up Python Virtual Environment & Install Backend Dependencies
```bash
# On Windows (PowerShell):
python -m venv backend/.venv
.\backend\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r backend/requirements.txt

# On Linux / macOS (bash):
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
```

#### 3. Install Frontend Dependencies
```bash
cd frontend
npm ci
cd ..
```

#### 4. Start the FastAPI Backend
```bash
# Windows PowerShell (Development mode):
.\backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# Windows PowerShell (Isolated QA mode for browser testing):
$env:DATABASE_URL="sqlite:///./backend/data/day4_evaluator_qa.db"; .\backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# Linux / macOS:
./backend/.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

*Verification*: Open a new terminal and verify health:
```bash
curl -i http://127.0.0.1:8000/health
```
**Expected Response**:
- HTTP Status: `200 OK`
- Header: `x-database-target: cloudsentinel.db` (or `day4_evaluator_qa.db` if started with isolated URI)
- Body: `{"status":"ok","service":"cloudsentinel-backend","version":"0.1.0","timestamp":"...","database":"connected"}`

> [!IMPORTANT]
> **Health Check Truthfulness**: `GET /health` verifies process and HTTP routing responsiveness. The `"database":"connected"` field is a default schema attribute; actual database operational readiness is proven by executing queries against `GET /api/metrics` or `POST /api/demo/generate`. SQLite schema tables are initialized automatically on startup via FastAPI's `lifespan` hook.

#### 5. Start the React Vite Development Server
In a second terminal:
```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```
*Verification*: Vite outputs:
```text
  VITE v5.4.21  ready in ~500 ms
  ➜  Local:   http://127.0.0.1:5173/
```

#### 6. Open the Application
Open Google Chrome, Edge, Firefox, or Safari and navigate to:
```text
http://127.0.0.1:5173/
```
You can now proceed through [Journey A (Quick Demonstration)](#3-journey-a-quick-demonstration-3-minutes) above.

---

## 5. Alternative: Multi-Container Docker Compose Execution

If Docker and Docker Compose are installed on your machine:

```bash
# 1. Build images and start containers:
docker compose up --build -d

# 2. Check service status:
docker compose ps

# 3. Access the application:
# React Dashboard (via Nginx proxy): http://localhost:3000
# Backend Health Check:              http://localhost:3000/health
# OpenAPI / Swagger Docs:            http://localhost:8000/docs

# 4. Safe Teardown (Preserving SQLite named data volume):
docker compose down
```

> [!WARNING]
> **Data Safety Rule**: Always run `docker compose down` (WITHOUT `-v`). The `-v` flag destroys the named storage volume (`cloudsentinel-data`), deleting all persisted telemetry and incidents.

---

## 6. Verification & Automated Test Commands

All test suites can be executed independently from the repository root:

### 1. Backend Regression Suite (114 Tests)
```bash
# Windows:
.\backend\.venv\Scripts\python.exe -m pytest -v

# Linux / macOS:
./backend/.venv/bin/python -m pytest -v
```
- **Verified Reference Result**: `114 passed, 0 failed` in ~13 seconds across all 8 test modules.

### 2. Frontend Linting & Production Build
```bash
cd frontend
npm run lint    # ESLint 10 check: 0 errors, 0 warnings
npm run build   # TypeScript & Vite bundle: ~1.0s compilation
cd ..
```

### 3. Machine Learning Detector Benchmark
```bash
# Windows:
.\backend\.venv\Scripts\python.exe backend/scripts/evaluate_detectors.py

# Linux / macOS:
./backend/.venv/bin/python backend/scripts/evaluate_detectors.py
```
- **Verified Reference Results**:
  - **Threshold Baseline**: Precision: `1.0000`, Recall: `1.0000`, F1: `1.0000` (`[[95, 0], [0, 5]]`)
  - **IsolationForest**: Precision: `0.8000`, Recall: `0.8000`, F1: `0.8000` (`[[94, 1], [1, 4]]`)
  - *Scope Note*: Benchmark comparison applies strictly to the canonical 100-sample synthetic dataset with 5 injected anomalies.

### 4. Real Chrome Automated Browser QA
```bash
# Ensure backend was launched with isolated DATABASE_URL and frontend is on :5173:
.\backend\.venv\Scripts\python.exe backend/tests/day4_milestone1_browser_qa.py
```
- **Verified Reference Result**: `13/13 PASSED (100%)` in real Google Chrome headless CDP.
- **Safety Preflight Check**: If the backend is mistakenly running on `cloudsentinel.db`, the script aborts immediately with code 1 to protect your development data.
- **Exit Status**: Exits with code 0 on all-pass; exits with nonzero code (1) if any assertion or safety check fails.

### 5. GitHub Actions Continuous Integration
The complete codebase is continuously verified on every commit using GitHub-hosted `ubuntu-24.04` runners:
- **Verified 100% Green Run**: [Run 38746777690](https://github.com/ARKkhanz/cloudsentinel-ai/actions/runs/38746777690)
- **CI Jobs**:
  1. `Frontend Lint & Production Build` (Ubuntu 24.04, Node 24): Pass (17s)
  2. `Backend Unit Tests & ML Evaluation` (Ubuntu 24.04, Python 3.11): Pass (41s)
  3. `Docker Compose Integration & Persistence` (Ubuntu 24.04, Real Docker): Pass (50s)

---

## 7. Common Troubleshooting & Gotchas

1. **Backend Connected to Primary Database during QA**:
   - Error: `CRITICAL SAFETY ABORT: Backend is connected to primary user database 'cloudsentinel.db'.`
   - Fix: Start backend with an isolated database URI:
     ```powershell
     $env:DATABASE_URL="sqlite:///./backend/data/day4_evaluator_qa.db"; .\backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
     ```

2. **Port 8000 or Port 5173 Already in Use**:
   - Check if a previous instance is still running:
     ```powershell
     # Windows:
     Get-NetTCPConnection -LocalPort 8000, 5173 -ErrorAction SilentlyContinue
     # Linux / macOS:
     lsof -i :8000 -i :5173
     ```
   - Terminate the conflicting process or specify an alternative port.

3. **Windows PowerShell Script Execution Policy**:
   - If `activate` gives an execution policy restriction:
     ```powershell
     Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
     ```

4. **CORS Errors During Local Development**:
   - The backend allows `http://localhost:5173` and `http://127.0.0.1:5173` by default in `backend/app/config.py`.

5. **SQLite Write Contention**:
   - Uvicorn is intentionally configured with `--workers 1` to prevent write contention and database lock timeouts in SQLite.

---

## 8. Technical Boundaries & Scientific Integrity

To maintain strict scientific and engineering rigor, CloudSentinel AI adheres to these documented boundaries:
1. **Synthetic Telemetry**: Telemetry is generated deterministically using mathematical distributions (sine waves + Gaussian noise) to demonstrate detection and investigation patterns. It is not live production traffic.
2. **Ground Truth Isolation**: The synthetic generator labels anomalies (`is_anomaly=True`) strictly for post-detection scoring; these labels are never exposed as detector inputs.
3. **Threshold Baseline Characteristics**: The 1.0 F1 score achieved by the threshold detector is an artifact of synthetic injection magnitudes exceeding static boundaries by design (`latency_ms > 150.0`, `error_rate > 0.05`). Real-world production telemetry involves non-linear drift and seasonal variance.
4. **IsolationForest Decision Boundary**: scikit-learn's `IsolationForest` derives its decision threshold from the training score distribution; `contamination=0.05` does not guarantee an exact 5% quota on unseen evaluation batches.
5. **No Root-Cause Fabrication**: The prototype surfaces factual mathematical evidence (breached thresholds and decision scores). It does **NOT** fabricate narrative root-cause explanations (e.g. claiming a memory leak or database deadlock).
6. **Unsupervised ML Score Meaning**: Anomaly scores represent tree traversal isolation depth, **NOT** calibrated outage probabilities.
7. **No Destructive Auto-Remediation**: CloudSentinel AI is an observability and decision-support prototype. It does not execute automated restarts or infrastructure mutations.
8. **No Future Outage Forecasting**: Detectors identify statistical deviations in observed telemetry; they do not forecast future failure timestamps.
