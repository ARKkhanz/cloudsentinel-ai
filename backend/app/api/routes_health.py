import os
from datetime import datetime, timezone
from fastapi import APIRouter, Response

from backend.app.config import settings
from backend.app.schemas.metrics import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, summary="Service health check")
def get_health(response: Response) -> HealthResponse:
    """Return application health status, service identifier, and current UTC time."""
    db_target = (
        os.path.basename(settings.database_url.split("?")[0])
        if "sqlite" in settings.database_url
        else "external"
    )
    response.headers["x-database-target"] = db_target
    return HealthResponse(
        status="ok",
        service="cloudsentinel-backend",
        version=settings.app_version,
        timestamp=datetime.now(timezone.utc),
    )
