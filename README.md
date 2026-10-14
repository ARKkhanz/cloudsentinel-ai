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
- **Day 2: Persistence, Anomaly Detection & Incidents** *(Planned)*
- **Day 3: Quality, Docker & GitHub Actions CI** *(Planned)*
- **Day 4: End-to-End Verification, Documentation & Demo** *(Planned)*

---

## Notice on Telemetry & Prototype Scope
All metric observations ingested and displayed by CloudSentinel AI during Day 1 are **strictly synthetic** and generated deterministically with an isolated random seed (`seed=42`) and a fixed UTC reference timestamp (`2026-10-14T12:00:00Z`).

CloudSentinel AI is a portfolio-grade reliability engineering prototype. It does not claim production monitoring, real outage prediction, or unmeasured accuracy.

---

## Technology Stack (Day 1)

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Frontend UI** | React 18 + TypeScript + Vite | Reactive dashboard, metric overview cards, observations table, state management |
| **Backend API** | Python 3.11 + FastAPI + Uvicorn | ASGI web service, route handlers, CORS middleware |
| **Validation** | Pydantic v2 | Strict request query and response contract schema enforcement |
| **Testing** | pytest + httpx (TestClient) | Automated API integration tests, schema validation, determinism checks |
| **Version Control** | Git + GitHub CLI | Checked-in milestones, verified commits on GitHub `main` branch |

---

## Repository Structure

```text
cloudsentinel-ai/
├── frontend/                     # React + TypeScript + Vite Dashboard
│   ├── src/
│   │   ├── api/
│   │   │   └── client.ts         # Centralized HTTP client (fetchHealth, fetchMetrics)
│   │   ├── types/
│   │   │   └── metrics.ts        # TypeScript interfaces matching backend schemas
│   │   ├── App.tsx               # Reactive dashboard container & state coordinator
│   │   ├── main.tsx              # React DOM mounting entry point
│   │   ├── index.css             # Polished dark-mode styling & responsive layout
│   │   └── vite-env.d.ts         # Vite client type definitions
│   ├── package.json              # Frontend dependencies and build scripts
│   ├── tsconfig.json             # Root TypeScript configuration
│   ├── tsconfig.app.json         # Application TypeScript configuration
│   ├── tsconfig.node.json        # Build tool TypeScript configuration
│   ├── vite.config.ts            # Vite dev server configuration (127.0.0.1:5173)
│   ├── index.html                # Single Page Application HTML root
│   └── .env.example              # Frontend environment placeholders
├── backend/                      # FastAPI Python Web Service
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes_health.py  # GET /health
│   │   │   └── routes_metrics.py # GET /api/metrics
│   │   ├── schemas/
│   │   │   └── metrics.py        # Pydantic models (HealthResponse, MetricSample, MetricListResponse)
│   │   ├── services/
│   │   │   └── metric_generator.py # Deterministic seeded synthetic metric generator
│   │   ├── config.py             # App settings and CORS allowed origins
│   │   └── main.py               # FastAPI application factory and router assembly
│   ├── tests/
│   │   ├── conftest.py           # Pytest TestClient fixture
│   │   ├── test_health.py        # Health route, status code, and CORS unit tests
│   │   ├── test_metrics.py       # Metrics validation, schema, order, and determinism tests
│   │   └── verify_milestone4_integration.py # Live Uvicorn socket & lifecycle test script
│   └── requirements.txt          # Python dependencies
├── docs/
│   └── learning-notes.md         # Architecture, request flow, and comprehension guide
├── .env.example                  # Root environment template (no secrets)
├── .gitignore                    # Python, Node, OS, and secret exclusion rules
└── README.md                     # Project documentation
```

---

## Local Setup & Startup Guide (Windows / PowerShell)

### Prerequisites
* **Python 3.10+** (tested on Python 3.11)
* **Node.js 18+ & npm** (tested on Node v24.19.0 / npm 11.17.0)
* **Git**

### 1. Backend Setup & Startup
Open a PowerShell terminal in the repository root:

```powershell
# Navigate to backend directory
cd C:\Users\USER\.gemini\antigravity-ide\scratch\cloudsentinel-ai\backend

# Create Python virtual environment
python -m venv .venv

# Activate virtual environment (PowerShell)
.\.venv\Scripts\Activate.ps1

# Install backend dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# Start the FastAPI backend server
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
The FastAPI backend will start at `http://127.0.0.1:8000`. You can view the automatic OpenAPI documentation at `http://127.0.0.1:8000/docs`.

### 2. Frontend Setup & Startup
Open a second PowerShell terminal in the repository root:

```powershell
# Navigate to frontend directory
cd C:\Users\USER\.gemini\antigravity-ide\scratch\cloudsentinel-ai\frontend

# Install dependencies
npm install

# Start the Vite development server
npm run dev
```
The dashboard will start at `http://127.0.0.1:5173`.

---

## API Endpoints Specification

### 1. `GET /health`
* **Purpose**: Health and readiness check.
* **Response Status**: `HTTP 200 OK`
* **Response Payload**:
  ```json
  {
    "status": "ok",
    "service": "cloudsentinel-backend",
    "version": "0.1.0",
    "timestamp": "2026-10-14T08:46:10.485942Z"
  }
  ```

### 2. `GET /api/metrics`
* **Purpose**: Retrieve reproducible synthetic service telemetry samples.
* **Query Parameters**:
  * `service` *(optional string, default `"demo-api"`, length: 1–100)*: Target service identifier.
  * `limit` *(optional integer, default `50`, bounds: `1..200`)*: Number of samples to return.
* **Validation**: Limits outside `1..200` or invalid types return `HTTP 422 Unprocessable Entity`.
* **Response Payload**:
  ```json
  {
    "service": "demo-api",
    "total_samples": 50,
    "order": "descending",
    "is_synthetic": true,
    "data": [
      {
        "service": "demo-api",
        "timestamp": "2026-10-14T12:00:00Z",
        "latency_ms": 41.14,
        "error_rate": 0.0045,
        "request_count": 123,
        "cpu_usage_pct": 31.31,
        "memory_usage_pct": 43.68,
        "is_synthetic": true
      }
    ]
  }
  ```

---

## Testing & Verification Commands

### Run Backend pytest Suite
```powershell
cd C:\Users\USER\.gemini\antigravity-ide\scratch\cloudsentinel-ai
.\backend\.venv\Scripts\python.exe -m pytest -v
```
*Current Result*: **17 passed, 0 failed** in ~1.0s.

### Run Live Backend HTTP Lifecycle Test
```powershell
.\backend\.venv\Scripts\python.exe backend\tests\verify_milestone4_integration.py
```
*Current Result*: Verified live FastAPI startup, network socket responses, CORS headers, error-state detection, and server restart recovery.

### Run Frontend Production Build Check
```powershell
cd C:\Users\USER\.gemini\antigravity-ide\scratch\cloudsentinel-ai\frontend
npm run build
```
*Current Result*: TypeScript compiler check (`tsc -b`) and Vite production bundling passed with zero errors.

---

## Reproducing the Day 1 Demo in Google Chrome

1. Start the FastAPI backend on port 8000.
2. Start the Vite frontend on port 5173.
3. Open Google Chrome and navigate to `http://localhost:5173`.
4. Observe the green badge: `Backend: Online (cloudsentinel-backend v0.1.0)`.
5. Review the 5 KPI summary cards (Avg Latency, Avg Error Rate, Total Volume, Resource Utilization).
6. Inspect the 50 synthetic telemetry observation rows sorted chronologically descending.
7. Click **Refresh** to verify on-demand state reloading.
8. Stop the backend server in PowerShell (`Ctrl+C`).
9. Click **Refresh** in Chrome: notice the red alert banner, offline badge, and the explicit `STALE CACHED DATA` warning protecting against presenting stale metrics as live.
10. Restart the backend server and click **Retry Connection**: observe instant recovery back to the online populated state.

---

## Known Limitations & Day 2 Roadmap

* **In-Memory Telemetry**: Metrics are deterministically generated on the fly; SQLite persistence will be introduced on Day 2.
* **No Anomaly Detection Yet**: Telemetry currently represents normal operational baseline variation. Scikit-learn `IsolationForest` and heuristic threshold baselines will be implemented on Day 2.
* **Manual Refresh**: Auto-polling / WebSockets are intentionally deferred to avoid unnecessary complexity during the initial vertical slice.
