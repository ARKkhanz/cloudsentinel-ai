from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Index
from backend.app.db.base import Base


class MetricSampleModel(Base):
    """
    SQLAlchemy ORM model for metric sample observations.
    Stores operational and synthetic service telemetry with UTC timestamps.
    """
    __tablename__ = "metric_samples"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    service = Column(String(100), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    latency_ms = Column(Float, nullable=False)
    error_rate = Column(Float, nullable=False)
    request_count = Column(Integer, nullable=False)
    cpu_usage_pct = Column(Float, nullable=False)
    memory_usage_pct = Column(Float, nullable=False)
    is_synthetic = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("ix_metric_samples_service_timestamp_desc", "service", timestamp.desc()),
    )

    def __repr__(self) -> str:
        return (
            f"<MetricSampleModel(id={self.id}, service='{self.service}', "
            f"timestamp='{self.timestamp}', latency_ms={self.latency_ms})>"
        )
