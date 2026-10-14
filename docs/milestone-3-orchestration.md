# CloudSentinel AI — Day 3 Milestone 3: Docker Compose Multi-Container Orchestration

## 1. Overview & Architecture

Day 3 Milestone 3 defines multi-container orchestration for CloudSentinel AI using the modern Docker Compose specification (`compose.yaml`).

The orchestration environment runs two core application services within an isolated bridge network, with persistent SQLite storage mounted from a dedicated Docker named volume:

```
+-----------------------------------------------------------------------------------+
| Host System (Developer Machine)                                                   |
|                                                                                   |
|  Browser / Developer Requests                                                     |
|    |                                          |                                   |
|    | HTTP: http://localhost:3000              | HTTP: http://localhost:8000/docs  |
|    v (127.0.0.1:3000 -> 80)                   v (127.0.0.1:8000 -> 8000)          |
+----+------------------------------------------+-----------------------------------+
| Docker Compose Environment (`cloudsentinel-network` bridge)                       |
|                                                                                   |
|   +------------------------------------+                                          |
|   | `frontend` (Nginx 1.27 Alpine)     |                                          |
|   | - Serves React SPA (port 80)       |                                          |
|   | - Proxies /health & /api/*         |                                          |
|   +-----------------+------------------+                                          |
|                     | proxy_pass http://backend:8000                              |
|                     v                                                             |
|   +------------------------------------+      +--------------------------------+  |
|   | `backend` (Python 3.11-slim)       |      | `cloudsentinel-data`           |  |
|   | - FastAPI ASGI on 0.0.0.0:8000     | ===> | (Docker Named Volume)          |  |
|   | - User: cloudsentinel (non-root)   |      | Mount: /app/backend/data       |  |
|   | - Single Uvicorn worker            |      | Persistent SQLite database     |  |
|   | - Healthcheck: GET /health         |      +--------------------------------+  |
|   +------------------------------------+                                          |
+-----------------------------------------------------------------------------------+
```

---

## 2. Service Definitions

### Backend Service (`backend`)
- **Container Name**: `cloudsentinel-backend`
- **Build Context**: Repository root (`.`), Dockerfile: `backend/Dockerfile`
- **Internal Port**: `8000`
- **Published Port**: `127.0.0.1:8000:8000` (restricted to host loopback for direct Swagger/OpenAPI documentation access at `http://localhost:8000/docs`)
- **Non-Root Execution**: Runs strictly as user `cloudsentinel:appgroup`
- **Single Uvicorn Worker**: Preserves concurrency safety for SQLite transactions
- **Volume Mount**: Named volume `cloudsentinel-data` mounted at `/app/backend/data`
- **Database URL**: `sqlite:////app/backend/data/cloudsentinel.db`
- **Allowed Origins**: `http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173`
- **Health Check**:
  - Endpoint: `GET /health` (`http://127.0.0.1:8000/health`)
  - Test: Executed via Python standard library `urllib.request` (no curl/wget dependency)
  - Interval: `10s`, Timeout: `5s`, Retries: `5`
  - Start Period: `15s` (conservative startup tolerance for cold-container Python/Scikit-Learn initialization)
- **Restart Policy**: `restart: unless-stopped`

### Frontend Service (`frontend`)
- **Container Name**: `cloudsentinel-frontend`
- **Build Context**: Repository root (`.`), Dockerfile: `frontend/Dockerfile`
- **Build Argument**: `VITE_API_BASE_URL=""` (inlines relative URLs for same-origin proxying via Nginx)
- **Container Port**: `80`
- **Published Port**: `127.0.0.1:3000:80` (restricted to host loopback for dashboard access)
- **Startup Dependency**:
  ```yaml
  depends_on:
    backend:
      condition: service_healthy
  ```
  Guarantees Nginx will not accept traffic until FastAPI has successfully booted and passed `/health`.
- **Restart Policy**: `restart: unless-stopped`

---

## 3. Container Networking

A custom bridge network named `cloudsentinel-network` connects both services:
- Docker's embedded DNS server (`127.0.0.11`) allows `frontend` to resolve `backend` by service name.
- Nginx proxies requests internally:
  - `/health` → `http://backend:8000/health`
  - `/api/metrics` → `http://backend:8000/api/metrics`
  - `/api/demo/generate` → `http://backend:8000/api/demo/generate`
  - `/api/detection/run` → `http://backend:8000/api/detection/run`
  - `/api/incidents` → `http://backend:8000/api/incidents`
- Browser clients only communicate with `http://localhost:3000`. Docker's internal hostnames are never exposed to or resolved by the client browser.

---

## 4. SQLite Volume Persistence & Permissions

### Persistence Lifecycle
- **Named Volume**: `cloudsentinel-data` (driver: `local`).
- **Mount Target**: `/app/backend/data`.
- **Stop / Start / Recreate**:
  - `docker compose stop` / `docker compose start`: Volume remains intact.
  - `docker compose down`: Removes containers and network, but **preserves** the named volume.
  - Subsequent `docker compose up -d`: Re-attaches the existing volume and retains all telemetry and incident records.
  - Image Rebuilds: Rebuilding images (`docker compose up --build -d`) does not touch or reinitialize data inside the volume.
- **Destructive Deletion**: Only `docker compose down -v` removes declared volumes. Standard cleanup commands should always omit `-v`.

### Non-Root Permission Handling
- In `backend/Dockerfile`, the directory `/app/backend/data` is created and assigned recursive ownership to `cloudsentinel:appgroup` before the volume mount point is established.
- When Docker creates and mounts a named volume for a container, it copies the image directory's initial metadata and file permissions into the volume.
- Consequently, the non-root user `cloudsentinel` retains read/write permissions to create `cloudsentinel.db`, SQLite write-ahead logs (`.db-wal`), shared memory files (`.db-shm`), and rollback journals (`.db-journal`).

---

## 5. Verification Commands (When Docker Engine is Available)

The following commands can be executed when a Docker engine is running:

```bash
# 1. Validate Compose file syntax without running containers
docker compose config

# 2. Build and start services in detached mode
docker compose up --build -d

# 3. Check service health and container status
docker compose ps

# 4. View recent container logs
docker compose logs --tail=100 -f

# 5. Direct backend health check (via loopback port 8000)
curl -i http://localhost:8000/health

# 6. Proxied backend health check (via Nginx port 3000)
curl -i http://localhost:3000/health

# 7. Frontend SPA entry point
curl -i http://localhost:3000/

# 8. Proxied telemetry API via Nginx
curl -i "http://localhost:3000/api/metrics?service=demo-api&limit=5"

# 9. Verify database file exists on volume
docker compose exec backend ls -la /app/backend/data

# 10. Stop and remove containers (preserving volume data)
docker compose down
```

---

## 6. Verification Status Matrix

| Component / Requirement | Verification Level | Status | Notes |
| :--- | :--- | :--- | :--- |
| **`compose.yaml` Syntax** | PyYAML Static Parse | **VERIFIED** | Valid modern Compose specification, no obsolete version field |
| **Service Topologies & Contexts** | Schema Assertions | **VERIFIED** | Valid paths (`backend/Dockerfile`, `frontend/Dockerfile`), context `.` |
| **Port Mappings & Loopback** | Schema Assertions | **VERIFIED** | Restricted to `127.0.0.1:8000:8000` and `127.0.0.1:3000:80` |
| **Named Volume Specification** | Schema Assertions | **VERIFIED** | `cloudsentinel-data` mounted at `/app/backend/data` |
| **Health Check Startup Tolerance** | Schema Assertions | **VERIFIED** | `start_period: 15s`, `retries: 5`, `interval: 10s`, `timeout: 5s` |
| **Frontend Startup Dependency** | Schema Assertions | **VERIFIED** | `depends_on.backend.condition: service_healthy` |
| **Backend Regression Suite** | Automated Pytest Run | **VERIFIED** | 114 passed, 0 failed in 13.46s |
| **Frontend Linting** | Automated ESLint Run | **VERIFIED** | 0 errors, 0 warnings |
| **Frontend Production Build** | Automated Vite Build | **VERIFIED** | Clean build in 1.08s |
| **Detector Evaluation Baseline** | Evaluation Benchmark | **VERIFIED** | Threshold F1=1.0000; IsolationForest F1=0.8000 |
| **Local Docker Daemon Execution** | Host Environment | **UNVERIFIED AT RUNTIME** | Docker CLI and engine not installed on local host machine |
| **Multi-Container Runtime Network** | Host Environment | **UNVERIFIED AT RUNTIME** | Scheduled for Day 3 Milestone 4 via GitHub Actions hosted runners |
