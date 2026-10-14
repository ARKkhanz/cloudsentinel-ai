from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class DetectionRunRequest(BaseModel):
    """
    Request model for triggering a detection pipeline execution.
    """
    service: str = Field(
        default="demo-api",
        description="Service identifier whose persisted metrics will be evaluated",
        min_length=1,
        max_length=100,
    )
    detector: str = Field(
        ...,
        description="Detector algorithm to run: 'threshold_baseline' or 'isolation_forest'",
    )
    limit: int = Field(
        default=100,
        description="Maximum number of most recent persisted metric samples to evaluate",
        ge=1,
        le=1000,
    )

    @field_validator("detector")
    @classmethod
    def validate_detector(cls, v: str) -> str:
        valid_detectors = ("threshold_baseline", "isolation_forest")
        cleaned = v.strip().lower()
        if cleaned not in valid_detectors:
            raise ValueError(
                f"Unsupported detector '{v}'. Must be one of: {', '.join(valid_detectors)}"
            )
        return cleaned


class DetectionRunResponse(BaseModel):
    """
    Structured outcome of a detection pipeline run.
    Reports analyzed sample counts, findings, and created vs deduplicated incidents.
    """
    status: str = Field("success", description="Overall execution status")
    service: str = Field(..., description="Service identifier evaluated")
    detector_name: str = Field(..., description="Detector algorithm executed")
    detector_version: str = Field(..., description="Version of the detector")
    samples_analyzed: int = Field(..., description="Number of persisted samples retrieved and scored")
    findings_count: int = Field(..., description="Total anomalous findings returned by the detector")
    incidents_created: int = Field(..., description="Count of new incident records persisted to SQLite")
    incidents_already_existing: int = Field(..., description="Count of duplicate findings skipped")
    created_incident_ids: List[str] = Field(default_factory=list, description="UUIDs of newly created incidents")
    run_timestamp: datetime = Field(..., description="UTC timestamp when the detection run executed")
    detector_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration parameters or baseline properties of the detector",
    )


class IncidentResponse(BaseModel):
    """
    Complete persisted incident representation including factual evidence snapshot.
    """
    id: str = Field(..., description="Unique incident UUID")
    service: str = Field(..., description="Monitored service identifier")
    created_at: datetime = Field(..., description="UTC timestamp when incident was generated and persisted")
    severity: str = Field(..., description="Severity classification: 'critical' or 'warning'")
    status: str = Field(..., description="Operational status: 'open', 'investigating', 'resolved'")
    detector_name: str = Field(..., description="Name of the detector that flagged this incident")
    detector_version: str = Field(..., description="Version of detector rules/model")
    summary: str = Field(..., description="Concise human-readable incident headline")
    explanation: str = Field(..., description="Factual explanation of the breach or outlier score")
    observed_metric_evidence: Dict[str, Any] = Field(
        ...,
        description="Factual numerical measurements recorded at the time of observation",
    )
    baseline_evidence: Dict[str, Any] = Field(
        ...,
        description="Threshold limits or IsolationForest model parameters and score",
    )
    window_start: datetime = Field(..., description="Start of observation detection window (UTC)")
    window_end: datetime = Field(..., description="End of observation detection window (UTC)")
    metric_sample_id: Optional[int] = Field(None, description="Primary key of originating metric sample if known")
    dedup_key: Optional[str] = Field(None, description="Deterministic deduplication identifier")

    model_config = ConfigDict(from_attributes=True)


class IncidentListResponse(BaseModel):
    """
    Paginated/filtered collection of persisted incidents.
    """
    service: Optional[str] = Field(None, description="Filter service if specified in query")
    total: int = Field(..., description="Total matching incidents returned")
    limit: int = Field(..., description="Query result limit applied")
    data: List[IncidentResponse] = Field(..., description="List of incidents ordered newest first")
