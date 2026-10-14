from fastapi import APIRouter, Query

from backend.app.schemas.metrics import MetricListResponse
from backend.app.services.metric_generator import generate_synthetic_metrics

router = APIRouter(prefix="/api", tags=["Metrics"])


@router.get(
    "/metrics",
    response_model=MetricListResponse,
    summary="Retrieve reproducible synthetic service metrics",
)
def get_metrics(
    service: str = Query(
        default="demo-api",
        min_length=1,
        max_length=100,
        description="Target service identifier",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description="Number of metric samples to retrieve (bounded 1 to 200)",
    ),
) -> MetricListResponse:
    """
    Retrieve deterministic synthetic telemetry metrics for a service.
    
    Returns samples in descending chronological order (newest first).
    All data is generated with a fixed seed and fixed UTC reference timestamp
    to ensure reproducibility across test and demo runs.
    """
    samples = generate_synthetic_metrics(service=service, limit=limit)
    return MetricListResponse(
        service=service,
        total_samples=len(samples),
        order="descending",
        is_synthetic=True,
        data=samples,
    )
