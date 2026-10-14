import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from backend.app.schemas.demo import GroundTruthAnomaly
from backend.app.schemas.metrics import MetricSample

# Canonical fixed UTC reference timestamp for reproducible generation
DEFAULT_REFERENCE_TIME = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)
DEFAULT_SEED = 42

# Baseline distribution parameters for normal service behavior
BASELINE_LATENCY_MU = 42.0
BASELINE_LATENCY_SIGMA = 5.0
BASELINE_ERROR_MU = 0.005
BASELINE_ERROR_SIGMA = 0.002
BASELINE_REQUESTS_MU = 130.0
BASELINE_REQUESTS_SIGMA = 15.0
BASELINE_CPU_MU = 28.0
BASELINE_CPU_SIGMA = 3.5
BASELINE_MEMORY_MU = 44.0
BASELINE_MEMORY_SIGMA = 2.0


@dataclass
class AnomalyGenerationResult:
    """Container holding generated metric samples and separate ground-truth labels."""
    samples: List[MetricSample]
    ground_truth: List[GroundTruthAnomaly]


def generate_metrics_with_anomalies(
    service: str = "checkout-service",
    total_samples: int = 100,
    seed: int = DEFAULT_SEED,
    latency_spike_count: int = 3,
    error_spike_count: int = 2,
    reference_time: Optional[datetime] = None,
) -> AnomalyGenerationResult:
    """
    Generate reproducible synthetic metric observations with controlled injected anomalies.
    
    Architecture guarantees:
    1. Isolated RNG: Uses an isolated random.Random(seed) instance.
    2. UTC Timestamps: All samples have timezone-aware UTC timestamps.
    3. Descending Order: Index 0 is newest (reference_time), Index N-1 is oldest.
    4. Clean Baseline: Preserves normal baseline observations at both ends of the series.
    5. Ground-Truth Separation: Ground-truth metadata is returned separately from the
       telemetry sample objects, preventing accidental feature leakage into ML models.
    6. Realistic Value Bounds: All metrics conform strictly to Pydantic validation bounds.
    """
    if reference_time is None:
        ref_time = DEFAULT_REFERENCE_TIME
    elif reference_time.tzinfo is None:
        ref_time = reference_time.replace(tzinfo=timezone.utc)
    else:
        ref_time = reference_time.astimezone(timezone.utc)

    rng = random.Random(seed)

    # Candidate indices for anomaly injection, preserving a baseline buffer at edges
    edge_buffer = max(5, total_samples // 10)
    candidate_indices = list(range(edge_buffer, total_samples - edge_buffer))

    total_requested = latency_spike_count + error_spike_count
    if total_requested > len(candidate_indices):
        raise ValueError(
            f"Cannot inject {total_requested} anomalies into candidate window of size {len(candidate_indices)}. "
            f"Increase total_samples or reduce anomaly counts."
        )

    # Deterministically select anomaly slots
    latency_indices = set(sorted(rng.sample(candidate_indices, latency_spike_count)))
    remaining_candidates = [idx for idx in candidate_indices if idx not in latency_indices]
    error_indices = set(sorted(rng.sample(remaining_candidates, error_spike_count)))

    samples: List[MetricSample] = []
    ground_truth: List[GroundTruthAnomaly] = []

    for i in range(total_samples):
        # Step backwards in time: index 0 is newest (reference_time)
        sample_time = ref_time - timedelta(minutes=i)

        if i in latency_indices:
            # Injected Latency Spike: dramatic surge (e.g. 320ms - 520ms vs 42ms baseline)
            latency = max(5.0, round(rng.uniform(320.0, 520.0), 2))
            error_rate = max(0.0, min(1.0, round(abs(rng.gauss(mu=BASELINE_ERROR_MU, sigma=BASELINE_ERROR_SIGMA)), 4)))
            request_count = max(10, int(rng.gauss(mu=BASELINE_REQUESTS_MU, sigma=BASELINE_REQUESTS_SIGMA)))
            cpu_usage = max(0.0, min(100.0, round(rng.uniform(70.0, 92.0), 2)))
            memory_usage = max(0.0, min(100.0, round(rng.gauss(mu=BASELINE_MEMORY_MU, sigma=BASELINE_MEMORY_SIGMA), 2)))

            gt = GroundTruthAnomaly(
                sample_index=i,
                timestamp=sample_time,
                anomaly_type="latency_spike",
                description=f"Injected latency degradation to {latency}ms (baseline ~{BASELINE_LATENCY_MU}ms)",
                injected_value=latency,
                baseline_mean=BASELINE_LATENCY_MU,
            )
            ground_truth.append(gt)

        elif i in error_indices:
            # Injected Error Rate Surge: severe 5xx error spike (e.g. 15% - 35% vs 0.5% baseline)
            latency = max(5.0, round(rng.uniform(50.0, 75.0), 2))
            error_rate = max(0.0, min(1.0, round(rng.uniform(0.15, 0.35), 4)))
            request_count = max(10, int(rng.gauss(mu=BASELINE_REQUESTS_MU, sigma=BASELINE_REQUESTS_SIGMA)))
            cpu_usage = max(0.0, min(100.0, round(rng.gauss(mu=BASELINE_CPU_MU, sigma=BASELINE_CPU_SIGMA), 2)))
            memory_usage = max(0.0, min(100.0, round(rng.gauss(mu=BASELINE_MEMORY_MU, sigma=BASELINE_MEMORY_SIGMA), 2)))

            gt = GroundTruthAnomaly(
                sample_index=i,
                timestamp=sample_time,
                anomaly_type="error_rate_spike",
                description=f"Injected error rate surge to {round(error_rate * 100, 2)}% (baseline ~0.5%)",
                injected_value=error_rate,
                baseline_mean=BASELINE_ERROR_MU,
            )
            ground_truth.append(gt)

        else:
            # Normal baseline telemetry observation with realistic Gaussian noise
            latency = max(5.0, round(rng.gauss(mu=BASELINE_LATENCY_MU, sigma=BASELINE_LATENCY_SIGMA), 2))
            error_rate = max(0.0, min(1.0, round(abs(rng.gauss(mu=BASELINE_ERROR_MU, sigma=BASELINE_ERROR_SIGMA)), 4)))
            request_count = max(10, int(rng.gauss(mu=BASELINE_REQUESTS_MU, sigma=BASELINE_REQUESTS_SIGMA)))
            cpu_usage = max(0.0, min(100.0, round(rng.gauss(mu=BASELINE_CPU_MU, sigma=BASELINE_CPU_SIGMA), 2)))
            memory_usage = max(0.0, min(100.0, round(rng.gauss(mu=BASELINE_MEMORY_MU, sigma=BASELINE_MEMORY_SIGMA), 2)))

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

    return AnomalyGenerationResult(samples=samples, ground_truth=ground_truth)


def get_ground_truth_labels(
    service: str = "checkout-service",
    total_samples: int = 100,
    seed: int = DEFAULT_SEED,
    latency_spike_count: int = 3,
    error_spike_count: int = 2,
    reference_time: Optional[datetime] = None,
) -> List[GroundTruthAnomaly]:
    """
    Deterministic helper to retrieve ground-truth labels for a given generation configuration.
    
    Enables future evaluation and comparison workflows (Milestone 5) to access ground-truth
    anomaly labels without querying or modifying the detector feature matrix.
    """
    result = generate_metrics_with_anomalies(
        service=service,
        total_samples=total_samples,
        seed=seed,
        latency_spike_count=latency_spike_count,
        error_spike_count=error_spike_count,
        reference_time=reference_time,
    )
    return result.ground_truth
