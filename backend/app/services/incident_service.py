from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from backend.app.detection.isolation_forest_detector import (
    FEATURE_NAMES,
    IsolationForestDetector,
    MLDetectionFinding,
)
from backend.app.detection.threshold_detector import (
    ThresholdDetector,
    ThresholdFinding,
)
from backend.app.models.incident import IncidentModel
from backend.app.models.metric import MetricSampleModel
from backend.app.schemas.incidents import (
    DetectionRunResponse,
    IncidentListResponse,
    IncidentResponse,
)
from backend.app.services.anomaly_generator import generate_metrics_with_anomalies


def run_detection_pipeline(
    db: Session,
    service: str = "demo-api",
    detector_type: str = "threshold_baseline",
    limit: int = 100,
) -> DetectionRunResponse:
    """
    Execute detection-to-incident service pipeline.
    
    Workflow:
    1. Retrieve persisted metric samples for target service from SQLite.
    2. Execute selected detector (ThresholdDetector or IsolationForestDetector).
    3. Convert genuine findings into IncidentModel instances with factual evidence.
    4. Deduplicate against previously persisted incidents for the exact same observation and detector.
    5. Persist new incidents to SQLite in an atomic transaction.
    6. Return structured detection run response.
    
    Guarantees:
    - Never fabricates detections or root causes.
    - Preserves independent findings for threshold vs isolation_forest detectors.
    - Decouples detector mathematics from database transactions.
    - Persists self-contained evidence snapshots that survive synthetic telemetry regeneration.
    """
    run_timestamp = datetime.now(timezone.utc)

    # 1. Load actual persisted samples from SQLite
    db_samples = (
        db.query(MetricSampleModel)
        .filter(MetricSampleModel.service == service)
        .order_by(MetricSampleModel.timestamp.desc())
        .limit(limit)
        .all()
    )

    if not db_samples:
        return DetectionRunResponse(
            status="success",
            service=service,
            detector_name=detector_type,
            detector_version="1.0.0",
            samples_analyzed=0,
            findings_count=0,
            incidents_created=0,
            incidents_already_existing=0,
            created_incident_ids=[],
            run_timestamp=run_timestamp,
            detector_metadata={
                "message": f"No metric observations found in SQLite database for service '{service}'."
            },
        )

    # Reverse to chronological order (oldest to newest) for detection evaluation
    chronological_samples = db_samples[::-1]

    # 2. Execute selected detector
    detector_name: str
    detector_version: str
    detector_metadata: Dict[str, Any]
    findings: List[Any]

    if detector_type == "threshold_baseline":
        detector = ThresholdDetector(
            latency_threshold_ms=150.0,
            error_rate_threshold=0.05,
        )
        detector_name = detector.name
        detector_version = detector.version
        detector_metadata = {
            "type": "statistical_threshold",
            "latency_threshold_ms": detector.latency_threshold_ms,
            "error_rate_threshold": detector.error_rate_threshold,
            "latency_threshold_unit": "ms",
            "error_rate_threshold_proportion": "5.0%",
        }
        findings = detector.detect(chronological_samples)

    elif detector_type == "isolation_forest":
        # Fit on deterministic normal reference baseline (Seed 100, 100 samples, 0 injected anomalies)
        # Keeps training strictly disjoint from evaluation samples and never accesses ground-truth labels.
        reference_train_samples = generate_metrics_with_anomalies(
            service=service,
            total_samples=100,
            seed=100,
            latency_spike_count=0,
            error_spike_count=0,
        ).samples

        detector = IsolationForestDetector(
            random_state=42,
            n_estimators=100,
            contamination=0.05,
        )
        detector.fit(reference_train_samples)

        detector_name = detector.name
        detector_version = detector.version
        detector_metadata = {
            "type": "unsupervised_isolation_forest",
            "random_state": 42,
            "n_estimators": 100,
            "contamination": 0.05,
            "training_samples": 100,
            "training_seed": 100,
            "feature_names": list(FEATURE_NAMES),
        }
        findings = detector.detect(chronological_samples)

    else:
        raise ValueError(f"Unsupported detector type: '{detector_type}'")

    # 3. Retrieve existing deduplication keys for this service and detector
    existing_keys_rows = (
        db.query(IncidentModel.dedup_key)
        .filter(
            IncidentModel.service == service,
            IncidentModel.detector_name == detector_name,
            IncidentModel.dedup_key.isnot(None),
        )
        .all()
    )
    existing_dedup_keys = {row[0] for row in existing_keys_rows}

    # 4. Formulate incidents and deduplicate
    new_incidents: List[IncidentModel] = []
    created_incident_ids: List[str] = []
    incidents_already_existing = 0

    for finding in findings:
        # Construct deterministic deduplication key
        # Incorporates service, detector_name, and observation timestamp in UTC ISO format
        obs_time_iso = (
            finding.timestamp.astimezone(timezone.utc).isoformat()
            if finding.timestamp.tzinfo
            else finding.timestamp.replace(tzinfo=timezone.utc).isoformat()
        )
        dedup_key = f"{finding.service}:{finding.detector_name}:{obs_time_iso}"

        if dedup_key in existing_dedup_keys:
            incidents_already_existing += 1
            continue

        # Build baseline evidence snapshot
        if isinstance(finding, ThresholdFinding):
            baseline_evidence = finding.evidence
        elif isinstance(finding, MLDetectionFinding):
            baseline_evidence = {
                "anomaly_score": finding.anomaly_score,
                "prediction_label": finding.prediction_label,
                "model_metadata": finding.model_metadata,
            }
        else:
            baseline_evidence = {}

        obs_time_utc = (
            finding.timestamp.astimezone(timezone.utc)
            if finding.timestamp.tzinfo
            else finding.timestamp.replace(tzinfo=timezone.utc)
        )

        incident = IncidentModel(
            id=str(uuid.uuid4()),
            service=finding.service,
            created_at=datetime.now(timezone.utc),
            severity=finding.severity,
            status="open",
            detector_name=finding.detector_name,
            detector_version=finding.detector_version,
            summary=finding.summary,
            explanation=finding.explanation,
            observed_metric_evidence=finding.observed_metric_values,
            baseline_evidence=baseline_evidence,
            window_start=obs_time_utc,
            window_end=obs_time_utc,
            metric_sample_id=finding.metric_id,
            dedup_key=dedup_key,
        )

        new_incidents.append(incident)
        created_incident_ids.append(incident.id)
        # Register in in-memory set to prevent intra-batch duplicate collisions
        existing_dedup_keys.add(dedup_key)

    # 5. Atomic persistence of new incidents
    if new_incidents:
        db.add_all(new_incidents)
        db.commit()

    return DetectionRunResponse(
        status="success",
        service=service,
        detector_name=detector_name,
        detector_version=detector_version,
        samples_analyzed=len(db_samples),
        findings_count=len(findings),
        incidents_created=len(new_incidents),
        incidents_already_existing=incidents_already_existing,
        created_incident_ids=created_incident_ids,
        run_timestamp=run_timestamp,
        detector_metadata=detector_metadata,
    )


def get_incidents(
    db: Session,
    service: Optional[str] = None,
    status: Optional[str] = None,
    detector_name: Optional[str] = None,
    limit: int = 50,
) -> IncidentListResponse:
    """
    Retrieve persisted incidents with optional filtering, ordered newest-first.
    """
    query = db.query(IncidentModel)

    if service:
        query = query.filter(IncidentModel.service == service)
    if status:
        query = query.filter(IncidentModel.status == status)
    if detector_name:
        query = query.filter(IncidentModel.detector_name == detector_name)

    # Order newest first by creation timestamp
    query = query.order_by(IncidentModel.created_at.desc())

    records = query.limit(limit).all()

    incident_items = [
        IncidentResponse.model_validate(rec)
        for rec in records
    ]

    return IncidentListResponse(
        service=service,
        total=len(incident_items),
        limit=limit,
        data=incident_items,
    )


def get_incident_by_id(
    db: Session,
    incident_id: str,
) -> Optional[IncidentModel]:
    """
    Retrieve single incident by UUID primary key.
    """
    return db.query(IncidentModel).filter(IncidentModel.id == incident_id).first()
