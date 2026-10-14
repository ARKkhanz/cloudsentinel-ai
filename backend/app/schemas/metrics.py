from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Schema for GET /health endpoint."""
    status: str = Field(..., description="Health status string, e.g. 'ok'")
    service: str = Field(..., description="Service identifier")
    version: str = Field(..., description="Application version")
    timestamp: datetime = Field(..., description="Current server UTC timestamp")


class MetricSample(BaseModel):
    """Single service telemetry sample."""
    service: str = Field(..., description="Identifier of the monitored service")
    timestamp: datetime = Field(..., description="Sample timestamp (UTC)")
    latency_ms: float = Field(..., ge=0.0, description="Observed round-trip latency in milliseconds")
    error_rate: float = Field(..., ge=0.0, le=1.0, description="Error rate proportion (0.0 to 1.0)")
    request_count: int = Field(..., ge=0, description="Total requests handled in this interval")
    cpu_usage_pct: float = Field(..., ge=0.0, le=100.0, description="CPU utilization percentage")
    memory_usage_pct: float = Field(..., ge=0.0, le=100.0, description="Memory utilization percentage")
    is_synthetic: bool = Field(True, description="Explicit flag indicating data is synthetic demo telemetry")


class MetricListResponse(BaseModel):
    """Schema for GET /api/metrics response."""
    service: str = Field(..., description="Service name queried")
    total_samples: int = Field(..., description="Number of metric samples returned")
    order: str = Field("descending", description="Chronological ordering of data ('descending' = newest first)")
    is_synthetic: bool = Field(True, description="Explicit flag confirming dataset is synthetic")
    data: List[MetricSample] = Field(..., description="List of metric sample objects")
