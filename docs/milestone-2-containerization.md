# CloudSentinel AI — Day 3 Milestone 2: Container Definitions & Nginx Architecture

## 1. Backend Dockerfile Architecture

The backend image (`backend/Dockerfile`) is structured as follows:

- **Base Image**: Official `python:3.11-slim`, minimizing surface area and vulnerabilities while avoiding toolchain bloat.
- **Build Context**: Root directory (`.`), ensuring Python package imports (`backend.app.main:app`) resolve naturally without path workarounds.
- **Environment**:
  - `PYTHONUNBUFFERED=1`: Ensures logs are emitted immediately to standard output for container log aggregation.
  - `PYTHONDONTWRITEBYTECODE=1`: Avoids writing ephemeral `.pyc` files into container layers.
  - `PYTHONPATH=/app`: Asserts consistent module resolution regardless of execution directory.
  - `DATABASE_URL="sqlite:////app/backend/data/cloudsentinel.db"`: Points SQLite directly to the dedicated persistent volume path.
- **Layer Caching**: Dependency declarations (`backend/requirements.txt`) are copied and installed (`pip install --no-cache-dir`) before application code is copied.
- **Non-Root User**: Dedicated system user `cloudsentinel` and group `appgroup` execute the service.
- **Runtime Command**: Single Uvicorn worker bound to `0.0.0.0:8000` (`uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1`), preserving SQLite concurrency safety.
- **Health Check**: Targets `http://127.0.0.1:8000/health` using Python's standard library (`urllib.request`) to avoid external dependencies like `curl` or `wget`.

## 2. Frontend Multi-Stage Build

The frontend image (`frontend/Dockerfile`) uses a two-stage design:

1. **Stage 1 (Builder — `node:24-alpine`)**:
   - Copies `frontend/package.json` and `frontend/package-lock.json`.
   - Runs `npm ci` for deterministic, clean package installation.
   - Copies frontend source code and TypeScript configs.
   - Injects `VITE_API_BASE_URL=""` at build time so the compiled bundle makes relative API requests.
   - Runs `npm run build` (`tsc -b && vite build`) to generate optimized static assets in `/app/dist`.
2. **Stage 2 (Runtime — `nginx:1.27-alpine`)**:
   - Discards Node.js runtime, build tools, source code, and `node_modules` entirely.
   - Copies only compiled assets from `/app/dist` to `/usr/share/nginx/html`.
   - Copies custom `frontend/nginx.conf` to `/etc/nginx/conf.d/default.conf`.
   - Exposes container port 80.
   - Nginx master process runs with required privileges to bind port 80, dropping privileges to the unprivileged `nginx` system user for all worker processes.

## 3. Nginx Reverse Proxy Routing

Nginx acts as both the static asset web server and the single entry point reverse proxy:

- **SPA Routing (`/`)**: Serves compiled static assets with fallback (`try_files $uri $uri/ /index.html;`) to support React client-side navigation.
- **Health Routing (`/health`)**: Proxies incoming requests directly to `http://backend:8000/health`.
- **API Routing (`/api/`)**: Proxies incoming requests directly to `http://backend:8000/api/`, preserving HTTP methods, request payloads, and query parameters.
- **Headers & Timeouts**: Preserves `Host`, `X-Real-IP`, `X-Forwarded-For`, and `X-Forwarded-Proto` with a 60-second connection, send, and read timeout.
- **Gzip Compression**: Pre-compresses text, javascript, css, and json responses over 1 KB.

### Future Request Paths

| Initiator | Browser URL | Nginx Upstream Forward | Backend Target |
| :--- | :--- | :--- | :--- |
| Browser SPA | `http://localhost:3000/` | Local filesystem (`index.html`) | N/A (Static Asset) |
| Browser API | `http://localhost:3000/api/metrics` | `http://backend:8000/api/metrics` | FastAPI Route |
| Browser Health | `http://localhost:3000/health` | `http://backend:8000/health` | FastAPI Health Route |

## 4. Local Development vs Production API Configuration

- **Development Mode**: In local development (`npm run dev`), `VITE_API_BASE_URL` is undefined, defaulting in `src/api/client.ts` to `http://localhost:8000` with FastAPI CORS middleware permitting origin `http://localhost:5173`.
- **Production Mode**: In Docker, `VITE_API_BASE_URL=""` is baked into the JavaScript bundle. All requests are relative (`/health`, `/api/metrics`). The browser makes same-origin requests to the Nginx host (`localhost:3000`), completely bypassing cross-origin restrictions without exposing Docker-internal DNS (`backend:8000`) to the browser.

## 5. Expected Container Ports

- **Backend Container (`backend`)**: Listens on internal container port `8000`.
- **Frontend Container (`frontend`)**: Listens on internal container port `80`.
- **Host Exposure (Future Compose)**: Port `80` will be published to host port `3000` (`3000:80`). Backend port `8000` remains internal to the Docker bridge network.

## 6. SQLite Directory and Non-Root Permissions

- The backend container creates directory `/app/backend/data` and assigns recursive ownership to `cloudsentinel:appgroup`.
- When SQLite initializes `cloudsentinel.db`, the non-root user possesses write permissions for the directory and database lock/journal files (`.db-journal`, `.db-wal`, `.db-shm`).
- In Milestone 3, mounting a named Docker volume to `/app/backend/data` preserves initialized data across container recreation cycles.

## 7. Future Root-Level Docker Build Commands

When a Docker engine is available:

```bash
# Build backend image from repository root
docker build -t cloudsentinel-backend:latest -f backend/Dockerfile .

# Build frontend image from repository root
docker build -t cloudsentinel-frontend:latest -f frontend/Dockerfile .
```

## 8. Verification Status Matrix

| Component / Check | Verification Level | Status / Finding |
| :--- | :--- | :--- |
| Backend Dockerfile Syntax & Context | Static Inspection | **VERIFIED** (Valid syntax, Debian 11-slim, standard stdlib healthcheck) |
| Frontend Dockerfile Multi-Stage | Static Inspection | **VERIFIED** (Valid Node 24 Alpine builder -> Nginx 1.27 Alpine runtime) |
| Nginx Reverse Proxy Config | Static Inspection | **VERIFIED** (Valid directives, SPA fallback, correct upstream paths) |
| Root `.dockerignore` Rules | Static Inspection | **VERIFIED** (Excludes venv, node_modules, caches, local databases, QA media) |
| Frontend TypeScript & ESLint Check | Automated Local Run | **VERIFIED** (`npm run lint` exited 0; 0 warnings/errors) |
| Frontend Production Build Check | Automated Local Run | **VERIFIED** (`npm run build` completed in ~1.0s) |
| Production Relative URL Inlining | Automated Local Run | **VERIFIED** (Confirmed `VITE_API_BASE_URL=""` inlines relative URLs with no `localhost:8000` leaks) |
| Backend 114-Test Regression Suite | Automated Local Run | **VERIFIED** (114/114 pytest tests passed in 12.83s) |
| ML Detector Benchmark Integrity | Automated Local Run | **VERIFIED** (Threshold: F1=1.0000; IsolationForest: F1=0.8000) |
| Local Docker Build Execution | Container Engine | **UNVERIFIED AT RUNTIME** (Docker CLI & engine not installed on host) |
| Local Container Network Execution | Container Engine | **UNVERIFIED AT RUNTIME** (Scheduled for Day 3 Milestone 4 via GitHub Actions) |
