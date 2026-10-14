from datetime import datetime, timezone
import pytest

from backend.app.detection.threshold_detector import ThresholdDetector, ThresholdFinding
from backend.app.schemas.metrics import MetricSample
from backend.app.services.anomaly_generator import generate_metrics_with_anomalies


def create_sample(
    service: str = "checkout-service",
    latency_ms: float = 42.0,
    error_rate: float = 0.005,
    sample_id: int = None,
    timestamp: datetime = None,
) -> MetricSample:
    """Helper to construct a single test metric sample."""
    return MetricSample(
        id=sample_id,
        service=service,
        timestamp=timestamp or datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc),
        latency_ms=latency_ms,
        error_rate=error_rate,
        request_count=100,
        cpu_usage_pct=30.0,
        memory_usage_pct=40.0,
        is_synthetic=True,
    )


def test_1_normal_samples_produce_no_findings():
    """Verify normal baseline observations do not trigger threshold alerts."""
    detector = ThresholdDetector(latency_threshold_ms=150.0, error_rate_threshold=0.05)
    sample = create_sample(latency_ms=45.0, error_rate=0.008)

    finding = detector.detect_sample(sample)
    assert finding is None

    # Test list of normal samples
    batch = [
        create_sample(latency_ms=40.0, error_rate=0.004),
        create_sample(latency_ms=44.0, error_rate=0.006),
        create_sample(latency_ms=50.0, error_rate=0.009),
    ]
    findings = detector.detect(batch)
    assert len(findings) == 0


def test_2_high_latency_generates_finding():
    """Verify latency exceeding threshold triggers finding with correct severity and evidence."""
    detector = ThresholdDetector(latency_threshold_ms=150.0, error_rate_threshold=0.05)
    sample = create_sample(latency_ms=325.50, error_rate=0.005)

    finding = detector.detect_sample(sample)
    assert finding is not None
    assert finding.severity == "warning"
    assert finding.triggered_conditions == ["latency_ms_exceeded"]
    assert "latency" in finding.summary.lower()
    assert finding.observed_metric_values["latency_ms"] == 325.50
    assert "325.50 ms exceeded" in finding.explanation
    assert finding.evidence["comparisons"]["latency_ms"]["excess"] == 175.50


def test_3_high_error_rate_generates_finding():
    """Verify error rate exceeding threshold triggers finding with critical severity."""
    detector = ThresholdDetector(latency_threshold_ms=150.0, error_rate_threshold=0.05)
    sample = create_sample(latency_ms=42.0, error_rate=0.225)

    finding = detector.detect_sample(sample)
    assert finding is not None
    assert finding.severity == "critical"
    assert finding.triggered_conditions == ["error_rate_exceeded"]
    assert "error" in finding.summary.lower()
    assert finding.observed_metric_values["error_rate"] == 0.225
    assert "22.50%" in finding.explanation
    assert "error_rate" in finding.evidence["comparisons"]


def test_4_sample_breaching_both_conditions():
    """
    Verify dual breach triggers a single consolidated finding (no duplicate alerts)
    with critical severity and both conditions recorded.
    """
    detector = ThresholdDetector(latency_threshold_ms=150.0, error_rate_threshold=0.05)
    sample = create_sample(latency_ms=410.0, error_rate=0.18)

    # Calling detect must yield exactly 1 finding, NOT 2
    findings = detector.detect([sample])
    assert len(findings) == 1

    finding = findings[0]
    assert finding.severity == "critical"
    assert set(finding.triggered_conditions) == {"latency_ms_exceeded", "error_rate_exceeded"}
    assert "Multiple Threshold Breaches" in finding.summary
    assert "latency_ms" in finding.evidence["comparisons"]
    assert "error_rate" in finding.evidence["comparisons"]
    assert "Multiple thresholds breached" in finding.explanation


def test_5_values_exactly_equal_to_thresholds():
    """Verify boundary condition: values exactly equal to thresholds are NOT breaches (strictly >)."""
    detector = ThresholdDetector(latency_threshold_ms=150.0, error_rate_threshold=0.05)
    sample = create_sample(latency_ms=150.0, error_rate=0.05)

    finding = detector.detect_sample(sample)
    assert finding is None, "Values exactly equal to threshold must not trigger breach"


def test_6_values_just_below_thresholds():
    """Verify values marginally below threshold produce no finding."""
    detector = ThresholdDetector(latency_threshold_ms=150.0, error_rate_threshold=0.05)
    sample = create_sample(latency_ms=149.99, error_rate=0.0499)

    finding = detector.detect_sample(sample)
    assert finding is None


def test_7_values_just_above_thresholds():
    """Verify values marginally above threshold trigger breach."""
    detector = ThresholdDetector(latency_threshold_ms=150.0, error_rate_threshold=0.05)

    # Just above latency
    lat_sample = create_sample(latency_ms=150.01, error_rate=0.01)
    f_lat = detector.detect_sample(lat_sample)
    assert f_lat is not None
    assert f_lat.triggered_conditions == ["latency_ms_exceeded"]

    # Just above error rate
    err_sample = create_sample(latency_ms=50.0, error_rate=0.0501)
    f_err = detector.detect_sample(err_sample)
    assert f_err is not None
    assert f_err.triggered_conditions == ["error_rate_exceeded"]


def test_8_empty_input():
    """Verify empty input list produces empty findings list without errors."""
    detector = ThresholdDetector()
    findings = detector.detect([])
    assert findings == []


def test_9_deterministic_results():
    """Verify identical input samples produce identical findings repeatedly."""
    detector = ThresholdDetector()
    sample = create_sample(latency_ms=300.0, error_rate=0.15)

    f1 = detector.detect_sample(sample)
    f2 = detector.detect_sample(sample)

    assert f1.model_dump() == f2.model_dump()


def test_10_correct_detector_identity():
    """Verify detector identity metadata in findings."""
    detector = ThresholdDetector(name="custom_threshold_rules", version="2.1.0")
    sample = create_sample(latency_ms=250.0)

    finding = detector.detect_sample(sample)
    assert finding.detector_name == "custom_threshold_rules"
    assert finding.detector_version == "2.1.0"


def test_11_evidence_matches_actual_observed_values():
    """Verify evidence structure faithfully reports observed numerical values and units."""
    detector = ThresholdDetector(latency_threshold_ms=150.0, error_rate_threshold=0.05)
    sample = create_sample(latency_ms=280.75, error_rate=0.003)

    finding = detector.detect_sample(sample)
    assert finding.evidence["comparisons"]["latency_ms"]["observed"] == 280.75
    assert finding.evidence["comparisons"]["latency_ms"]["threshold"] == 150.0
    assert finding.evidence["comparisons"]["latency_ms"]["unit"] == "ms"
    assert finding.observed_metric_values["cpu_usage_pct"] == 30.0
    assert finding.observed_metric_values["memory_usage_pct"] == 40.0


def test_12_correct_threshold_reporting():
    """Verify threshold values in finding accurately reflect detector configuration."""
    detector = ThresholdDetector(latency_threshold_ms=175.0, error_rate_threshold=0.08)
    sample = create_sample(latency_ms=200.0, error_rate=0.10)

    finding = detector.detect_sample(sample)
    assert finding.threshold_values["latency_ms"] == 175.0
    assert finding.threshold_values["error_rate"] == 0.08


def test_13_ground_truth_labels_not_used_as_detector_features():
    """
    CRITICAL: Confirm detector operates purely on telemetry features and does NOT require
    or inspect ground-truth anomaly labels.
    """
    detector = ThresholdDetector()
    # Sample has NO ground_truth or anomaly attributes
    raw_dict = {
        "service": "billing-service",
        "timestamp": datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc),
        "latency_ms": 350.0,
        "error_rate": 0.002,
        "request_count": 80,
        "cpu_usage_pct": 50.0,
        "memory_usage_pct": 60.0,
    }
    assert "is_anomaly" not in raw_dict
    assert "ground_truth" not in raw_dict

    finding = detector.detect_sample(raw_dict)
    assert finding is not None
    assert finding.triggered_conditions == ["latency_ms_exceeded"]


def test_14_proper_handling_of_configured_threshold_values():
    """Verify initialization parameter validation rejects invalid thresholds."""
    with pytest.raises(ValueError, match="latency_threshold_ms must be positive"):
        ThresholdDetector(latency_threshold_ms=-10.0)

    with pytest.raises(ValueError, match="error_rate_threshold must be a proportion"):
        ThresholdDetector(error_rate_threshold=1.5)

    with pytest.raises(ValueError, match="error_rate_threshold must be a proportion"):
        ThresholdDetector(error_rate_threshold=-0.1)


def test_15_compatibility_with_existing_synthetic_generator():
    """Verify detector processes output from generate_metrics_with_anomalies cleanly."""
    gen_result = generate_metrics_with_anomalies(
        service="checkout-service",
        total_samples=100,
        seed=42,
        latency_spike_count=3,
        error_spike_count=2,
    )
    detector = ThresholdDetector(latency_threshold_ms=150.0, error_rate_threshold=0.05)
    findings = detector.detect(gen_result.samples)

    # Exactly 5 injected anomalies in seed 42 should be detected
    assert len(findings) == 5

    # Check that each finding matches one of the ground-truth timestamps
    gt_timestamps = {gt.timestamp for gt in gen_result.ground_truth}
    for finding in findings:
        assert finding.timestamp in gt_timestamps


def test_16_stable_behavior_when_metrics_include_optional_db_ids():
    """Verify metric_id is preserved when samples have database primary key IDs."""
    detector = ThresholdDetector(latency_threshold_ms=150.0)
    sample_with_id = create_sample(latency_ms=250.0, sample_id=987)

    finding = detector.detect_sample(sample_with_id)
    assert finding is not None
    assert finding.metric_id == 987

    # Metric without ID
    sample_no_id = create_sample(latency_ms=250.0, sample_id=None)
    finding_no_id = detector.detect_sample(sample_no_id)
    assert finding_no_id.metric_id is None
