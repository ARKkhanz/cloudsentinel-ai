from typing import List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.metric import MetricSampleModel
from backend.app.schemas.metrics import (
    MetricListResponse,
    MetricSample,
    MetricSampleCreate,
)

router = APIRouter(prefix="/api", tags=["Metrics"])


@router.get(
    "/metrics",
    response_model=MetricListResponse,
    summary="Retrieve persisted service telemetry observations",
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
    db: Session = Depends(get_db),
) -> MetricListResponse:
    """
    Retrieve persisted telemetry metric samples for a specified service.

    Returns observations from SQLite in chronological descending order (newest first).
    Does NOT automatically generate new synthetic data on GET requests; if the database
    is empty, returns an empty list with total_samples=0.
    """
    records = (
        db.query(MetricSampleModel)
        .filter(MetricSampleModel.service == service)
        .order_by(MetricSampleModel.timestamp.desc())
        .limit(limit)
        .all()
    )

    samples = [
        MetricSample(
            id=r.id,
            service=r.service,
            timestamp=r.timestamp,
            latency_ms=r.latency_ms,
            error_rate=r.error_rate,
            request_count=r.request_count,
            cpu_usage_pct=r.cpu_usage_pct,
            memory_usage_pct=r.memory_usage_pct,
            is_synthetic=r.is_synthetic,
        )
        for r in records
    ]

    return MetricListResponse(
        service=service,
        total_samples=len(samples),
        order="descending",
        is_synthetic=all(s.is_synthetic for s in samples) if samples else True,
        data=samples,
    )


@router.post(
    "/metrics",
    response_model=MetricSample,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a validated service metric sample",
)
def create_metric(
    metric_in: MetricSampleCreate,
    db: Session = Depends(get_db),
) -> MetricSample:
    """
    Ingest and persist a validated telemetry metric observation into SQLite.

    Rejects invalid bounds (e.g. error_rate not in 0..1, negative latency, empty service)
    with HTTP 422 Unprocessable Entity.
    """
    db_metric = MetricSampleModel(
        service=metric_in.service,
        timestamp=metric_in.timestamp,
        latency_ms=metric_in.latency_ms,
        error_rate=metric_in.error_rate,
        request_count=metric_in.request_count,
        cpu_usage_pct=metric_in.cpu_usage_pct,
        memory_usage_pct=metric_in.memory_usage_pct,
        is_synthetic=metric_in.is_synthetic,
    )
    db.add(db_metric)
    db.commit()
    db.refresh(db_metric)
    return MetricSample.model_validate(db_metric)
