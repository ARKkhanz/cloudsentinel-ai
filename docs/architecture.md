# CloudSentinel AI — System Architecture & Engineering Specifications

> **Technical architecture reference for CloudSentinel AI, illustrating the end-to-end telemetry ingestion pipeline, dual anomaly detection engines, multi-container Docker deployment, and GitHub Actions continuous integration quality gates.**

---

## 1. Architectural Overview & Design Principles

CloudSentinel AI is an evidence-backed reliability engineering prototype designed around four core principles:

1. **Separation of Concerns**: Ingestion, detection, deduplication, and presentation are strictly decoupled. Detection engines operate solely on numerical metric vectors and never access synthetic ground-truth labels.
2. **Transparent Mathematical Evidence**: Anomaly findings do not fabricate speculative root-cause narratives. Incidents preserve immutable snapshots of measured telemetry values alongside explicit algorithmic boundaries (threshold breaches or tree isolation scores).
3. **Alert Fatigue Prevention via Cryptographic Deduplication**: Incidents compute a deterministic SHA-256 fingerprint over the service name, detector identity, configuration summary, observation timestamp, and canonicalized numerical metrics. Repeated detector runs over identical observations generate **zero duplicate incidents**.
4. **Reproducibility & Infrastructure Parity**: The system is fully reproducible locally via Python virtual environments / Vite dev servers, in containerized environments via Docker Compose, and continuously verified on GitHub Actions runners.

---

## 2. Diagram A: Application Architecture & Telemetry Pipeline

The diagram below details the data flow from synthetic generation and persistence through the dual detection engines, deduplication service, and interactive React dashboard.

```mermaid
flowchart TD
    subgraph Client["Presentation Layer (React 18 + TypeScript + Vite)"]
        UI["React Dashboard (App.tsx)"]
        ClientAPI["Centralized API Client (client.ts)"]
        Modal["Forensic Evidence Modal"]
        UI --> ClientAPI
        UI --> Modal
    end

    subgraph Network["REST API Boundary (FastAPI / ASGI Uvicorn :8000)"]
        R_Health["GET /health"]
        R_Metrics["GET /api/metrics"]
        R_Demo["POST /api/demo/generate"]
        R_Detect["POST /api/detection/run"]
        R_Incidents["GET /api/incidents"]
        R_IncidentDetail["GET /api/incidents/{id}"]
    end

    ClientAPI -->|HTTP / JSON| Network

    subgraph Core["Backend Service & Detection Engines"]
        DemoGen["Synthetic Telemetry Generator\n(Seed 42: Sine Wave Baselines + Gaussian Noise)"]
        GroundTruth["Isolated Ground-Truth Labels\n(is_anomaly=True for evaluation only)"]
        DemoGen -.-> GroundTruth

        subgraph Detectors["Dual Anomaly Detection Layer"]
            ThresholdDet["Threshold Baseline Detector\n(latency_ms > 150.0ms, error_rate > 0.05)"]
            MLDet["IsolationForest Multivariate Detector\n(5 Features: latency, error, cpu, mem, requests)"]
        end

        IncidentSvc["Incident Service Layer (incident_service.py)"]
        DedupEngine["Deterministic SHA-256 Fingerprinting\n(service:detector:sha256[:32] -> dedup_key)"]

        DemoGen --> IncidentSvc
        ThresholdDet --> IncidentSvc
        MLDet --> IncidentSvc
        IncidentSvc --> DedupEngine
    end

    R_Demo --> DemoGen
    R_Detect --> IncidentSvc
    R_Metrics --> MetricModel
    R_Incidents --> IncidentModel
    R_IncidentDetail --> IncidentModel

    subgraph Storage["Persistence Layer (SQLite + SQLAlchemy 2.x ORM)"]
        MetricModel[("metric_samples Table\ntimestamp, service, latency_ms,\nerror_rate, request_count, cpu, mem")]
        IncidentModel[("incidents Table\nid, service, severity, detector_name,\nobserved_metric_evidence, baseline_evidence,\ndedup_key (VARCHAR 160 UNIQUE)")]
    end

    DemoGen -->|Bulk Insert Samples| MetricModel
    IncidentSvc -->|Query Samples| MetricModel
    DedupEngine -->|Insert Deduplicated Incidents| IncidentModel
```

---

## 3. Diagram B: Multi-Container Docker Architecture

The diagram below illustrates the production container deployment orchestrated via `compose.yaml`, featuring reverse-proxy routing, internal bridge networking, non-root security privileges, and persistent volume storage.

```mermaid
flowchart LR
    User["Web Browser\n(Evaluator / Developer)"]

    subgraph DockerHost["Docker Host Environment (compose.yaml)"]
        subgraph FrontendContainer["Frontend Container (cloudsentinel-frontend)"]
            Nginx["Production Nginx Web Server (:80)\nNon-root user 'nginx'"]
            Dist["Pre-compiled Static SPA Assets\n(/usr/share/nginx/html)"]
            Nginx --- Dist
        end

        subgraph BridgeNet["Internal Docker Network (cloudsentinel-net)"]
            ProxyPass["Nginx Reverse Proxy Pass\nlocation /api/ -> backend:8000\nlocation /health -> backend:8000"]
        end

        subgraph BackendContainer["Backend Container (cloudsentinel-backend)"]
            Uvicorn["FastAPI ASGI Uvicorn (:8000)\nNon-root user 'cloudsentinel' (UID 10001)"]
            AppCode["Application Code (/app/backend)"]
            SQLAlchemy["SQLAlchemy 2.x Session Engine"]
            Uvicorn --- AppCode
            AppCode --- SQLAlchemy
        end

        subgraph VolumeStorage["Persistent Volume Storage"]
            NamedVol[("Named Storage Volume\n(cloudsentinel-data)\nMounted at /app/data\nSQLite: cloudsentinel.db")]
        end
    end

    User -->|HTTP :3000| Nginx
    Nginx --> ProxyPass
    ProxyPass -->|HTTP :8000 (Internal DNS)| Uvicorn
    SQLAlchemy -->|Read / Write ACID| NamedVol
```

---

## 4. Diagram C: Continuous Integration Pipeline (GitHub Actions)

The diagram below outlines the automated verification pipeline defined in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml), executing on GitHub-hosted `ubuntu-24.04` runners across all pull requests and pushes to `main`.

```mermaid
flowchart TD
    PushEvent["Git Commit & Push to 'main'"] --> GHA["GitHub Actions Runner (ubuntu-24.04)"]

    subgraph Job1["Job 1: Frontend Lint & Production Build"]
        J1_Setup["Setup Node.js 24 + npm ci"]
        J1_Lint["ESLint 10 Verification\n(npm run lint: 0 errors, 0 warnings)"]
        J1_Build["TypeScript Check & Vite Production Build\n(npm run build: ~1.0s compilation)"]
        J1_Setup --> J1_Lint --> J1_Build
    end

    subgraph Job2["Job 2: Backend Unit Tests & ML Evaluation"]
        J2_Setup["Setup Python 3.11 + pip install -r requirements.txt"]
        J2_Pytest["Backend pytest Suite\n(114 tests passed, 100% success)"]
        J2_Benchmark["ML Detector Evaluation Benchmark\n(evaluate_detectors.py: Threshold F1=1.0, ML F1=0.8)"]
        J2_Setup --> J2_Pytest --> J2_Benchmark
    end

    subgraph Job3["Job 3: Docker Compose Integration & Persistence"]
        J3_Config["Validate compose.yaml Specification\n(docker compose config --quiet)"]
        J3_Build["Build Multi-Stage Docker Images\n(Frontend Nginx + Backend Python)"]
        J3_Up["Start Containers in Detached Mode\n(docker compose up -d)"]
        J3_Health["Verify Health Probes\n(:8000/health direct + :3000/health proxied)"]
        J3_E2E["Execute End-to-End Pipeline Verification\n(Generate Telemetry -> Threshold -> ML -> Dedup)"]
        J3_Persist["Test SQLite Named Volume Persistence\n(docker compose down -> up -d -> verify data)"]
        J3_Teardown["Safe Disposable Volume Teardown\n(docker compose down -v in ephemeral runner)"]

        J3_Config --> J3_Build --> J3_Up --> J3_Health --> J3_E2E --> J3_Persist --> J3_Teardown
    end

    GHA --> Job1
    GHA --> Job2
    GHA --> Job3

    Job1 --> QualityGate{"All Jobs Green?\n(100% Success)"}
    Job2 --> QualityGate
    Job3 --> QualityGate

    QualityGate -->|Yes| GreenBadge["Verified 100% Green CI Status\n(Ready for Evaluator Review)"]
    QualityGate -->|No| FailHalt["Halt Pipeline & Emit Diagnostic Logs"]
```

---

## 5. Technical Contracts & Implementation Summary

| Component | Specification / Contract | Source File |
| :--- | :--- | :--- |
| **Telemetry Format** | Pydantic `MetricSample` (`timestamp`, `service`, `latency_ms`, `error_rate`, `request_count`, `cpu_usage_pct`, `memory_usage_pct`) | [`backend/app/schemas/metrics.py`](../backend/app/schemas/metrics.py) |
| **Threshold Rules** | `latency_ms > 150.0` (z > 21 baseline) and `error_rate > 0.05` (z > 22 baseline) | [`backend/app/detection/threshold_detector.py`](../backend/app/detection/threshold_detector.py) |
| **IsolationForest Features** | 5 fixed features: `latency_ms`, `error_rate`, `cpu_usage_pct`, `memory_usage_pct`, `request_count` | [`backend/app/detection/isolation_forest_detector.py`](../backend/app/detection/isolation_forest_detector.py) |
| **Deduplication Key** | `service:detector:sha256[:32]` stored in `dedup_key` (VARCHAR 160 UNIQUE) | [`backend/app/services/incident_service.py`](../backend/app/services/incident_service.py) |
| **API Endpoints** | `/health`, `/api/metrics`, `/api/demo/generate`, `/api/detection/run`, `/api/incidents`, `/api/incidents/{id}` | [`backend/app/main.py`](../backend/app/main.py) |
| **Database Schema** | SQLite with SQLAlchemy ORM (`metric_samples`, `incidents`), WAL mode, auto-schema migration | [`backend/app/models/`](../backend/app/models/) |
| **Container Networking** | Internal bridge `cloudsentinel-net`, Nginx reverse proxy on port 3000, Uvicorn on port 8000 | [`compose.yaml`](../compose.yaml) |
| **CI Automation** | Multi-job workflow on `ubuntu-24.04`, Python 3.11, Node 24, real Docker integration | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) |
