from datetime import datetime, timezone
import hashlib
import logging
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.exc import IntegrityError
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

logger = logging.getLogger(__name__)


def generate_incident_fingerprint(
    service: str,
    detector_name: str,
    detector_version: str,
    timestamp: datetime,
    observed_metric_values: Dict[str, Any],
    detector_config_summary: Optional[str] = None,
) -> str:
    """
    Generate a deterministic SHA-256 deduplication fingerprint for an anomaly finding.
    
    Identity Composition:
    - Service name
    - Detector identity and semantic version
    - Material detector configuration summary (e.g. thresholds or hyperparameters)
    - Timezone-aware UTC timestamp in ISO-8601 format
    - Canonicalized numerical measurements formatted to fixed precision
    
    Properties:
    - Compact: Returns f"{service}:{detector_name}:{sha256_prefix[:32]}" (fits easily within VARCHAR(160)).
    - Fixed float formatting (4 decimal places) eliminates float representation jitter.
    - Discriminating: Telemetry with changed measurements at reused timestamps generates distinct fingerprints.
    - Detector Isolation: Different detectors or configurations produce distinct keys.
    """
    obs_time_utc = (
        timestamp.astimezone(timezone.utc)
        if timestamp.tzinfo
        else timestamp.replace(tzinfo=timezone.utc)
    )
    obs_time_iso = obs_time_utc.isoformat()

    # Canonicalize metrics: sorted keys, fixed decimal formatting
    canonical_tokens = []
    for k in sorted(observed_metric_values.keys()):
        val = observed_metric_values[k]
        if k == "request_count" or isinstance(val, (int, bool)):
            canonical_tokens.append(f"{k}={int(val)}")
        elif isinstance(val, float):
            canonical_tokens.append(f"{k}={val:.4f}")
        else:
            canonical_tokens.append(f"{k}={str(val).strip()}")
    metrics_str = ";".join(canonical_tokens)

    config_str = (detector_config_summary or "").strip()

    raw_payload = (
        f"service={service.strip()}|"
        f"detector={detector_name.strip()}:{detector_version.strip()}|"
        f"config={config_str}|"
        f"time={obs_time_iso}|"
        f"metrics={metrics_str}"
    )

    digest = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()[:32]
    return f"{service.strip()}:{detector_name.strip()}:{digest}"


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
    4. Deduplicate against previously persisted incidents using deterministic SHA-256 fingerprinting.
    5. Safely persist new incidents to SQLite in an atomic transaction with integrity conflict handling.
    6. Return structured detection run response.
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
    detector_config_summary: str
    findings: List[Any]

    if detector_type == "threshold_baseline":
        detector = ThresholdDetector(
            latency_threshold_ms=150.0,
            error_rate_threshold=0.05,
        )
        detector_name = detector.name
        detector_version = detector.version
        detector_config_summary = (
            f"latency_thresh={detector.latency_threshold_ms:.2f}|error_thresh={detector.error_rate_threshold:.4f}"
        )
        detector_metadata = {
            "type": "statistical_threshold",
            "latency_threshold_ms": detector.latency_threshold_ms,
            "error_rate_threshold": detector.error_rate_threshold,
            "latency_threshold_unit": "ms",
            "error_rate_threshold_proportion": "5.0%",
        }
        findings = detector.detect(chronological_samples)

    elif detector_type == "isolation_forest":
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
        detector_config_summary = (
            f"n_est={detector.n_estimators}|contamination={detector.contamination:.4f}|seed={detector.random_state}"
        )
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

    # 3. Retrieve existing incidents for this service and detector
    existing_incident_rows = (
        db.query(
            IncidentModel.id,
            IncidentModel.dedup_key,
            IncidentModel.window_start,
            IncidentModel.observed_metric_evidence,
        )
        .filter(
            IncidentModel.service == service,
            IncidentModel.detector_name == detector_name,
        )
        .all()
    )

    existing_dedup_keys = set()
    for row in existing_incident_rows:
        if row.dedup_key:
            existing_dedup_keys.add(row.dedup_key)
        # Backward compatibility: for historical rows with legacy keys or missing keys,
        # generate the fingerprint from stored evidence so identical observations match
        if row.observed_metric_evidence and isinstance(row.observed_metric_evidence, dict) and row.window_start:
            try:
                hist_fp = generate_incident_fingerprint(
                    service=service,
                    detector_name=detector_name,
                    detector_version=detector_version,
                    timestamp=row.window_start,
                    observed_metric_values=row.observed_metric_evidence,
                    detector_config_summary=detector_config_summary,
                )
                existing_dedup_keys.add(hist_fp)
            except Exception:
                pass

    # 4. Formulate incidents and deduplicate
    new_incidents: List[IncidentModel] = []
    created_incident_ids: List[str] = []
    incidents_already_existing = 0

    for finding in findings:
        obs_time_utc = (
            finding.timestamp.astimezone(timezone.utc)
            if finding.timestamp.tzinfo
            else finding.timestamp.replace(tzinfo=timezone.utc)
        )
        obs_time_iso = obs_time_utc.isoformat()

        # Compute deterministic fingerprint key
        dedup_key = generate_incident_fingerprint(
            service=finding.service,
            detector_name=finding.detector_name,
            detector_version=finding.detector_version,
            timestamp=obs_time_utc,
            observed_metric_values=finding.observed_metric_values,
            detector_config_summary=detector_config_summary,
        )

        # Legacy key check for backward compatibility with pre-fingerprint entries
        legacy_key = f"{finding.service}:{finding.detector_name}:{obs_time_iso}"

        if dedup_key in existing_dedup_keys:
            incidents_already_existing += 1
            continue

        # If legacy key matches AND historical measurements matched, treat as already existing
        if legacy_key in existing_dedup_keys:
            # Verify if this finding matches the legacy observation metrics
            matched_legacy = False
            for row in existing_incident_rows:
                if row.dedup_key == legacy_key and row.observed_metric_evidence == finding.observed_metric_values:
                    matched_legacy = True
                    break
            if matched_legacy:
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

    # 5. Persistence of new incidents with safe concurrency conflict handling
    if new_incidents:
        try:
            db.add_all(new_incidents)
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            logger.warning(
                f"Uniqueness conflict on incident commit: {exc}. Rolling back batch and saving non-conflicting items."
            )
            for inc in new_incidents:
                try:
                    db.add(inc)
                    db.commit()
                except IntegrityError:
                    db.rollback()
                    incidents_already_existing += 1
                    if inc.id in created_incident_ids:
                        created_incident_ids.remove(inc.id)

    return DetectionRunResponse(
        status="success",
        service=service,
        detector_name=detector_name,
        detector_version=detector_version,
        samples_analyzed=len(db_samples),
        findings_count=len(findings),
        incidents_created=len(created_incident_ids),
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
