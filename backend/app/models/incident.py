import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, JSON, Index, Integer
from backend.app.db.base import Base


class IncidentModel(Base):
    """
    SQLAlchemy ORM model for evidence-backed anomaly detection incidents.
    Stores detector attribution, root summary, detailed explanation, and raw telemetry evidence.
    """
    __tablename__ = "incidents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    service = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    severity = Column(String(20), nullable=False)  # "critical", "warning", "info"
    status = Column(String(20), nullable=False, default="open")  # "open", "investigating", "resolved"
    detector_name = Column(String(50), nullable=False, index=True)  # "threshold_baseline", "isolation_forest"
    detector_version = Column(String(20), nullable=False, default="1.0.0")
    summary = Column(String(255), nullable=False)
    explanation = Column(Text, nullable=False)
    observed_metric_evidence = Column(JSON, nullable=False)
    baseline_evidence = Column(JSON, nullable=False)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    metric_sample_id = Column(Integer, nullable=True, index=True)
    dedup_key = Column(String(160), unique=True, index=True, nullable=True)

    __table_args__ = (
        Index("ix_incidents_service_created_desc", "service", created_at.desc()),
    )

    def __repr__(self) -> str:
        return (
            f"<IncidentModel(id='{self.id}', service='{self.service}', "
            f"severity='{self.severity}', detector='{self.detector_name}')>"
        )
