from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


class DemoGenerateRequest(BaseModel):
    """Configuration options for POST /api/demo/generate."""
    service: str = Field(
        default="checkout-service",
        min_length=1,
        max_length=100,
        description="Target service identifier for metric generation",
    )
    total_samples: int = Field(
        default=100,
        ge=20,
        le=500,
        description="Total metric samples to generate (bounded 20 to 500)",
    )
    seed: int = Field(
        default=42,
        ge=0,
        description="Non-negative random seed for deterministic generation",
    )
    latency_spike_count: int = Field(
        default=3,
        ge=0,
        le=50,
        description="Number of latency spike anomalies to inject",
    )
    error_spike_count: int = Field(
        default=2,
        ge=0,
        le=50,
        description="Number of error rate spike anomalies to inject",
    )
    replace_existing: bool = Field(
        default=True,
        description="If True, replaces previous synthetic demo metrics for this service",
    )

    @model_validator(mode="after")
    def validate_anomaly_density(self) -> "DemoGenerateRequest":
        total_anomalies = self.latency_spike_count + self.error_spike_count
        max_allowed = self.total_samples // 2
        if total_anomalies > max_allowed:
            raise ValueError(
                f"Total requested anomalies ({total_anomalies}) exceeds 50% of total samples "
                f"({max_allowed}). Anomaly density must allow a clean normal baseline."
            )
        return self


class GroundTruthAnomaly(BaseModel):
    """
    Ground-truth metadata describing an injected synthetic anomaly.
    
    IMPORTANT: Ground-truth labels are kept separate from the numerical detector
    feature matrix to prevent label leakage into ML training or inference.
    """
    sample_index: int = Field(..., description="Chronological index in generation batch (0 = newest)")
    timestamp: datetime = Field(..., description="UTC timestamp of the anomalous sample")
    anomaly_type: str = Field(..., description="Category of anomaly: 'latency_spike' or 'error_rate_spike'")
    description: str = Field(..., description="Human-readable explanation of injected conditions")
    injected_value: float = Field(..., description="Injected anomaly value (ms or proportion)")
    baseline_mean: float = Field(..., description="Expected normal baseline mean for comparison")


class DemoGenerateResponse(BaseModel):
    """Structured response returned by POST /api/demo/generate."""
    status: str = Field("success", description="Generation status outcome")
    service: str = Field(..., description="Target service identifier")
    total_samples: int = Field(..., description="Total metric samples generated and persisted")
    seed: int = Field(..., description="Random seed used for generation")
    is_synthetic: bool = Field(True, description="Explicit flag confirming dataset is synthetic demo data")
    anomalies_injected: int = Field(..., description="Total count of injected anomalies")
    anomaly_types: List[str] = Field(..., description="List of unique anomaly types present in dataset")
    injected_anomalies: List[GroundTruthAnomaly] = Field(
        default_factory=list,
        description="Ground-truth anomaly labels for model evaluation and validation",
    )
    generation_policy: str = Field(
        ...,
        description="Dataset regeneration policy applied: 'replace_existing_synthetic' or 'append_batch'",
    )
    time_range_start: datetime = Field(..., description="Oldest observation UTC timestamp in dataset")
    time_range_end: datetime = Field(..., description="Newest observation UTC timestamp in dataset")
    created_at: datetime = Field(..., description="UTC timestamp when generation executed")
