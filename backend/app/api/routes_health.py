from datetime import datetime, timezone
from fastapi import APIRouter

from backend.app.config import settings
from backend.app.schemas.metrics import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, summary="Service health check")
def get_health() -> HealthResponse:
    """Return application health status, service identifier, and current UTC time."""
    return HealthResponse(
        status="ok",
        service="cloudsentinel-backend",
        version=settings.app_version,
        timestamp=datetime.now(timezone.utc),
    )
