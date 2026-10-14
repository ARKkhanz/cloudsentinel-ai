from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.metric import MetricSampleModel
from backend.app.schemas.demo import (
    DemoGenerateRequest,
    DemoGenerateResponse,
)
from backend.app.services.anomaly_generator import generate_metrics_with_anomalies

router = APIRouter(prefix="/api/demo", tags=["Demo Generation"])


@router.post(
    "/generate",
    response_model=DemoGenerateResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate and persist reproducible synthetic telemetry with injected anomalies",
)
def generate_demo_dataset(
    request: DemoGenerateRequest,
    db: Session = Depends(get_db),
) -> DemoGenerateResponse:
    """
    Generate deterministic synthetic service metrics with controlled anomaly injections
    and persist them to the SQLite database.

    Guarantees:
    - Controlled Duplication: If replace_existing=True, clears prior synthetic records
      for the target service only. Never deletes user-ingested data (is_synthetic=False)
      or data from other services.
    - Ground-Truth Separation: Returns explicit ground-truth anomaly labels in the API
      response without polluting the metric feature matrix.
    - No Fabricated Incidents: Does NOT create incident records or fake detection alerts.
    """
    # 1. Run deterministic anomaly generator
    gen_result = generate_metrics_with_anomalies(
        service=request.service,
        total_samples=request.total_samples,
        seed=request.seed,
        latency_spike_count=request.latency_spike_count,
        error_spike_count=request.error_spike_count,
    )

    # 2. Apply controlled dataset regeneration policy
    if request.replace_existing:
        db.query(MetricSampleModel).filter(
            MetricSampleModel.service == request.service,
            MetricSampleModel.is_synthetic.is_(True),
        ).delete(synchronize_session=False)

    # 3. Persist new samples to database
    db_records = [
        MetricSampleModel(
            service=sample.service,
            timestamp=sample.timestamp,
            latency_ms=sample.latency_ms,
            error_rate=sample.error_rate,
            request_count=sample.request_count,
            cpu_usage_pct=sample.cpu_usage_pct,
            memory_usage_pct=sample.memory_usage_pct,
            is_synthetic=sample.is_synthetic,
        )
        for sample in gen_result.samples
    ]
    db.add_all(db_records)
    db.commit()

    # 4. Formulate response metadata
    unique_types = sorted(list(set(gt.anomaly_type for gt in gen_result.ground_truth)))
    timestamps = [s.timestamp for s in gen_result.samples]

    return DemoGenerateResponse(
        status="success",
        service=request.service,
        total_samples=len(gen_result.samples),
        seed=request.seed,
        is_synthetic=True,
        anomalies_injected=len(gen_result.ground_truth),
        anomaly_types=unique_types,
        injected_anomalies=gen_result.ground_truth,
        generation_policy="replace_existing_synthetic" if request.replace_existing else "append_batch",
        time_range_start=min(timestamps),
        time_range_end=max(timestamps),
        created_at=datetime.now(timezone.utc),
    )
