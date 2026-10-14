from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes_demo import router as demo_router
from backend.app.api.routes_detection import router as detection_router
from backend.app.api.routes_health import router as health_router
from backend.app.api.routes_incidents import router as incidents_router
from backend.app.api.routes_metrics import router as metrics_router
from backend.app.config import settings
from backend.app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database schema is initialized on startup
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="CloudSentinel AI — Service Reliability & Metric Ingestion API",
    lifespan=lifespan,
)

# Explicit CORS configuration for frontend interaction
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route modules
app.include_router(health_router)
app.include_router(metrics_router)
app.include_router(demo_router)
app.include_router(detection_router)
app.include_router(incidents_router)


@app.get("/", include_in_schema=False)
def root():
    return {
        "message": "Welcome to CloudSentinel AI API",
        "health": "/health",
        "docs": "/docs",
        "metrics": "/api/metrics",
        "demo_generate": "/api/demo/generate",
    }
