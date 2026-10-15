# CloudSentinel AI — Technical Evaluator Verification Guide

> **An evidence-backed reliability engineering prototype that ingests synthetic cloud service telemetry, detects operational anomalies via transparent threshold rules and multivariate IsolationForest machine learning, deduplicates alert incidents via cryptographic fingerprinting, and provides factual numerical evidence for developer investigation.**

---

## 1. Project Purpose in Plain English

Modern cloud infrastructure produces high-velocity telemetry (latency, error rates, resource utilization). Detecting and triaging operational anomalies usually presents two severe engineering challenges:
1. **Alert Fatigue**: Naive detection rules spam on-call engineers with duplicate alerts for ongoing degradation.
2. **Opaque "Black Box" Warnings**: Anomaly alerts often fail to explain *why* an observation was flagged, leaving developers without verifiable evidence.

**CloudSentinel AI** demonstrates an end-to-end, reproducible solution to both problems:
- **Dual Detection Paradigms**: A deterministic **Threshold Baseline Detector** (rule-based) and an unsupervised **IsolationForest Machine Learning Detector** (Scikit-Learn).
- **Factual Evidence Chains**: Every created incident preserves an immutable snapshot of observed telemetry measurements alongside explicit mathematical boundaries (threshold excess or decision path score).
- **Fingerprint Deduplication**: Incidents compute a deterministic SHA-256 fingerprint over the service, detector configuration, and observation window, guaranteeing that repeat detection passes create **zero duplicate alerts**.
- **Unified Interface**: A responsive React 18 + TypeScript single-page application served either standalone via Vite or behind an Nginx reverse proxy concealing internal container networks.

---

## 2. System Architecture & Data Flow

```
[Synthetic Telemetry Generator]
       │ (100 samples, 5 injected spikes: Seed 42)
       ▼
[SQLite Storage Engine: metric_samples]
       │
       ▼
[Incident Service Layer]
  ├──> Threshold Baseline Detector (>150ms latency, >5% error rate)
  └──> IsolationForest ML Detector (Multivariate subspace density scoring)
       │
       ▼
[Deterministic SHA-256 Deduplication]
       │ (Filters known alert fingerprints)
       ▼
[SQLite Storage Engine: incidents]
       │ (Stores immutable evidence snapshots)
       ▼
[FastAPI REST API / Health Probes]
       │ (Port 8000)
       ▼
[Nginx Reverse Proxy / Vite Server]
       │ (Port 3000 in Docker / Port 5173 in Dev)
       ▼
[React TypeScript Dashboard]
  - Service Health Badge
  - Metric KPI Summary Cards
  - Telemetry Observation Table (Latest 50 rows displayed)
  - Incidents Table & Filter Controls
  - Forensic Evidence Inspection Modal
```

---

## 3. Journey A: Quick Demonstration (~3 Minutes)

*Designed for an evaluator who has the local dev server or Docker containers already running.*

### Step 1: Open the Dashboard
Navigate to:
- **Local Dev Server**: [`http://127.0.0.1:5173`](http://127.0.0.1:5173) (or `http://localhost:5173`)
- **Docker Compose Stack**: [`http://localhost:3000`](http://localhost:3000)

**What to Observe**:
- The header displays the **CloudSentinel AI** title and a glowing green badge: `BACKEND: ONLINE (CLOUDSENTINEL-BACKEND V0.1.0)`.
- If database is fresh, the observation table displays *"No metric samples available. Click 'Generate Synthetic Demo Data' to populate the database."*

### Step 2: Generate Canonical Synthetic Telemetry
Click the primary button in the action toolbar:
```
[ ⚡ Generate Synthetic Demo Data ]
```

**What to Observe**:
- A temporary loading spinner appears on the button.
- An emerald feedback banner appears:
  `"Successfully generated and persisted 100 observations with 5 injected anomalies for 'demo-api'."`
- **KPI Summary Cards Update**:
  - *Monitored Service*: `demo-api` (100 samples in SQLite)
  - *Average Latency*: ~103.5 ms
  - *Average Error Rate*: ~1.46%
  - *Average CPU*: ~34.8%
- **Observations Table**: Populates with chronological telemetry rows (Timestamp, Latency, Error Rate, CPU, Memory, Requests, Status).
- **Display Limit Notice**: The table shows the latest 50 observations to maintain snappy browser DOM rendering; all 100 observations are safely persisted in SQLite. Anomalies are highlighted with red `ANOMALY` badges.

### Step 3: Run Threshold Baseline Anomaly Detection
Click the second action button:
```
[ 🎯 Run Threshold Detection ]
```

**What to Observe**:
- A blue feedback banner confirms:
  `"Detection complete: Evaluated 100 samples -> 5 findings, 5 new incidents created (0 skipped)."`
- **Active Incidents Table Populates**: 5 threshold incident rows appear:
  - Severity: `CRITICAL` (for error rate surges > 5%) or `WARNING` (for latency spikes > 150ms).
  - Detector: `THRESHOLD_BASELINE` (v1.0.0).
  - Headline: Factual summary (e.g., *"Elevated Latency on demo-api (503.7 ms)"*).

### Step 4: Inspect Factual Numerical Evidence
On any incident row, click the **Inspect Evidence** button:
```
[ 🔍 Inspect Evidence ]
```

**What to Observe**:
- The **Incident Investigation Modal** opens.
- **Observed Telemetry Measurements**: Displays the exact readings at the time of observation (e.g., Latency: `503.72 ms`, Error Rate: `0.92%`, CPU: `34.1%`).
- **Baseline / Detector Evidence Comparison**:
  - *Breached Condition*: `latency_ms: 503.72 ms > threshold 150.0 ms (+353.72 ms excess)`
  - *Threshold Rule*: `latency_ms > 150.0 ms`
- Click **Close** (`✕`) to return to the dashboard.

### Step 5: Run IsolationForest Multivariate ML Detection
Click the third action button:
```
[ 🤖 Run IsolationForest Detection ]
```

**What to Observe**:
- A feedback banner confirms:
  `"Detection complete: Evaluated 100 samples -> 5 findings, 5 new incidents created (0 skipped)."`
- **Active Incidents Table Updates**: Total incidents increase from 5 to 10.
- 5 new incidents display the purple `ISOLATION_FOREST` badge (v1.0.0).

### Step 6: Inspect Machine Learning Anomaly Score
Click **Inspect Evidence** on any `ISOLATION_FOREST` incident row:

**What to Observe**:
- The modal reveals multivariate evidence:
  - *Decision Score*: A negative score (e.g., `-0.0011` or `-0.0373`). Negative values indicate geometric isolation in fewer tree partitions than normal baseline density.
  - *Model Hyperparameters*: `contamination=0.05`, `n_estimators=100`, `features=[latency_ms, error_rate_pct, cpu_utilization_pct, memory_utilization_pct, request_count]`.
- Click **Close** (`✕`).

### Step 7: Demonstrate Deduplication (Alert Fatigue Prevention)
Click **Run Threshold Detection** a second time:
```
[ 🎯 Run Threshold Detection ]
```

**What to Observe**:
- The feedback banner confirms:
  `"Detection complete: Evaluated 100 samples -> 5 findings, 0 new incidents created (5 skipped as duplicates)."`
- The incident table row count **remains exactly 10**.
- Zero duplicate rows are created in the database because the deterministic SHA-256 fingerprint matches existing incident records.

### Step 8: Confirm SQLite Persistence Across Page Reload
Press `F5` or `Ctrl+R` in your browser to reload the page.

**What to Observe**:
- All 10 incidents, all KPI calculations, and the 50 displayed telemetry rows immediately reappear from the SQLite database.

---

## 4. Journey B: Fresh Reproduction from Clean Machine

*Designed for an evaluator setting up the project on a clean computer.*

### Supported Prerequisites
| Component | Supported Version | Notes |
| :--- | :--- | :--- |
| **Operating System** | Windows 10/11, macOS, Linux | Cross-platform Python & Node |
| **Python** | 3.11.x (tested on 3.11.9) | Requires `pip` and `venv` |
| **Node.js** | 20.x, 22.x, or 24.x (tested on 24.19.0) | Requires `npm` (tested on 11.17.0) |
| **Git** | 2.40+ | For cloning and version checks |
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
.\backend\.venv\Scripts\Activate.ps1
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
# From repository root with virtual environment activated:
# Windows PowerShell:
.\backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# Linux / macOS:
./backend/.venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
*Verification*: Open a new terminal and verify health:
```bash
curl http://127.0.0.1:8000/health
# Expected Response:
# {"status":"ok","service":"cloudsentinel-backend","version":"0.1.0",...,"database":"connected"}
```
*(Notice: SQLite automatically initializes database tables on startup via `init_db()` lifecycle hook).*

#### 5. Start the React Vite Development Server
In a second terminal:
```bash
cd frontend
npm run dev
```
*Verification*: Vite outputs:
```
  VITE v5.4.21  ready in ~300 ms
  ➜  Local:   http://127.0.0.1:5173/
```

#### 6. Open the Application
Open Google Chrome, Edge, Firefox, or Safari and navigate to:
```
http://127.0.0.1:5173/
```
You can now proceed through **Journey A (Quick Demonstration)** above.

---

## 5. Alternative: Multi-Container Docker Compose Execution

If Docker and Docker Compose are installed on your machine, you can run the entire multi-container stack with a single command:

```bash
# 1. Build images and start containers in detached mode:
docker compose up --build -d

# 2. Check service status:
docker compose ps

# 3. Access the application:
# React Dashboard (via Nginx):  http://localhost:3000
# Backend Health Check:         http://localhost:3000/health
# OpenAPI / Swagger Docs:       http://localhost:8000/docs

# 4. Safe Teardown (Preserving SQLite data volume):
docker compose down
```

> [!WARNING]
> **Data Safety Rule**: Always run `docker compose down` (WITHOUT `-v`). The `-v` flag deletes the named storage volume (`cloudsentinel-data`), destroying all persisted telemetry and incidents. The `-v` flag is reserved strictly for ephemeral CI sandbox environments.

---

## 6. Verification & Automated Test Commands

All test suites can be executed independently from the repository root:

### 1. Backend Regression Suite (114 Tests)
```bash
# Windows:
.\backend\.venv\Scripts\python.exe -m pytest -v

# Linux / macOS:
./backend/.venv/bin/pytest -v
```
- **Verified Reference Result**: `114 passed, 0 failed` in ~12–15 seconds across all 8 modules.

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

### 4. Real Chrome Automated Browser QA
```bash
# Windows with backend on :8000 and frontend on :5173:
.\backend\.venv\Scripts\python.exe backend/tests/day4_milestone1_browser_qa.py
```
- **Verified Reference Result**: `12/12 PASSED (100%)` in real Google Chrome headless CDP.

### 5. GitHub Actions Continuous Integration Link
The complete codebase is continuously verified on every commit using GitHub-hosted `ubuntu-24.04` runners:
- **Verified 100% Green Run**: [https://github.com/ARKkhanz/cloudsentinel-ai/actions/runs/38595647392](https://github.com/ARKkhanz/cloudsentinel-ai/actions/runs/38595647392)
- **CI Jobs**:
  1. `Backend Unit Tests & ML Evaluation` (Ubuntu 24.04, Python 3.11): Pass (36s)
  2. `Frontend Lint & Production Build` (Ubuntu 24.04, Node 24): Pass (19s)
  3. `Docker Compose Integration & Persistence` (Ubuntu 24.04, Real Docker): Pass (54s)

---

## 7. Common Troubleshooting & Gotchas

1. **Port 8000 or Port 5173 Already in Use**:
   - Check if a previous instance is still running:
     ```powershell
     # Windows:
     Get-NetTCPConnection -LocalPort 8000, 5173 -ErrorAction SilentlyContinue
     # Linux / macOS:
     lsof -i :8000 -i :5173
     ```
   - Terminate the conflicting process or specify an alternative port:
     ```bash
     uvicorn backend.app.main:app --port 8001
     ```
     *(Note: Update `VITE_API_BASE_URL` in `frontend/.env.development` if changing backend port).*

2. **Windows PowerShell Script Execution Policy**:
   - If `Activate.ps1` gives an execution policy restriction:
     ```powershell
     Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
     ```

3. **CORS Errors During Local Development**:
   - The backend allows `http://localhost:5173` and `http://127.0.0.1:5173` by default in `backend/app/config.py`. If using custom hostnames, add them to `ALLOWED_ORIGINS="http://myhost:5173"`.

4. **Database File Locked (SQLite Concurrency)**:
   - SQLite allows multiple concurrent readers but a single writer. Uvicorn is intentionally configured with `--workers 1` to prevent write contention and lock timeouts.

---

## 8. Technical Boundaries & Scientific Integrity

To maintain strict scientific and engineering rigor, CloudSentinel AI adheres to these documented boundaries:
1. **Synthetic Telemetry**: Telemetry is generated deterministically to demonstrate detection and investigation patterns without cloud infrastructure costs. It is not live production traffic.
2. **Ground Truth Isolation**: The synthetic generator labels anomalies for benchmark scoring; these labels are strictly isolated and never fed into detector feature vectors.
3. **No Root-Cause Fabrication**: The prototype surfaces factual mathematical evidence (breached thresholds and decision scores). It does **NOT** fabricate narrative root-cause explanations (e.g. claiming a memory leak or database deadlock).
4. **Unsupervised ML Score Meaning**: A negative IsolationForest score indicates geometric isolation path length, **NOT** an outage probability.
5. **No Destructive Auto-Remediation**: CloudSentinel AI is an investigation and decision-support prototype. It does not execute automated restarts or infrastructure mutations.
