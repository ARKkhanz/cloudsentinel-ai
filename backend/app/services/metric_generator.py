import random
from datetime import datetime, timedelta, timezone
from typing import List

from backend.app.schemas.metrics import MetricSample

# Fixed UTC reference timestamp for deterministic generation
DEFAULT_REFERENCE_TIME = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)
DEFAULT_SEED = 42


def generate_synthetic_metrics(
    service: str = "demo-api",
    limit: int = 50,
    seed: int = DEFAULT_SEED,
    reference_time: datetime = DEFAULT_REFERENCE_TIME,
) -> List[MetricSample]:
    """
    Generate reproducible synthetic metric samples.
    
    Uses an isolated random.Random(seed) instance and a fixed UTC reference
    timestamp to guarantee that identical inputs produce bit-for-bit identical telemetry.
    
    Samples are returned in descending chronological order (newest first, index 0).
    """
    rng = random.Random(seed)
    samples: List[MetricSample] = []
    
    for i in range(limit):
        # Step backwards in time: index 0 is reference_time, index 1 is 1 min earlier, etc.
        sample_time = reference_time - timedelta(minutes=i)
        
        # Normal service telemetry behavior with mild realistic jitter
        latency = max(5.0, round(rng.gauss(mu=42.0, sigma=6.0), 2))
        error_rate = max(0.0, min(1.0, round(abs(rng.gauss(mu=0.005, sigma=0.003)), 4)))
        request_count = max(10, int(rng.gauss(mu=125, sigma=15)))
        cpu_usage = max(5.0, min(100.0, round(rng.gauss(mu=28.5, sigma=4.0), 2)))
        memory_usage = max(10.0, min(100.0, round(rng.gauss(mu=44.0, sigma=2.5), 2)))
        
        sample = MetricSample(
            service=service,
            timestamp=sample_time,
            latency_ms=latency,
            error_rate=error_rate,
            request_count=request_count,
            cpu_usage_pct=cpu_usage,
            memory_usage_pct=memory_usage,
            is_synthetic=True,
        )
        samples.append(sample)
        
    return samples
