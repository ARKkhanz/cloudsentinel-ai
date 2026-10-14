from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.incidents import (
    DetectionRunRequest,
    DetectionRunResponse,
)
from backend.app.services.incident_service import run_detection_pipeline

router = APIRouter(prefix="/api/detection", tags=["Detection"])


@router.post(
    "/run",
    response_model=DetectionRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger anomaly detection run and generate evidence-backed incidents",
)
def run_detection(
    request: DetectionRunRequest,
    db: Session = Depends(get_db),
) -> DetectionRunResponse:
    """
    Execute detection pipeline on persisted metric samples for a specified service.
    
    Supports:
    - 'threshold_baseline': Evaluates persisted metrics against statistical rules.
    - 'isolation_forest': Evaluates persisted metrics with multivariate IsolationForest fitted on clean reference baseline.
    
    Persists findings as SQLite incidents with complete numerical evidence snapshots.
    Prevents duplicate alerts on repeated executions without suppressing cross-detector findings.
    """
    return run_detection_pipeline(
        db=db,
        service=request.service,
        detector_type=request.detector,
        limit=request.limit,
    )
