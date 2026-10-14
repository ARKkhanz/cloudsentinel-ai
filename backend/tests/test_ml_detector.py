from datetime import datetime, timezone
import math
import pytest

from backend.app.detection.isolation_forest_detector import (
    FEATURE_NAMES,
    IsolationForestDetector,
    MLDetectionFinding,
)
from backend.app.detection.threshold_detector import ThresholdDetector
from backend.app.schemas.metrics import MetricSample
from backend.app.services.anomaly_generator import generate_metrics_with_anomalies


def make_sample(
    latency: float = 42.0,
    error_rate: float = 0.005,
    cpu: float = 28.0,
    memory: float = 44.0,
    requests: int = 130,
    service: str = "checkout-service",
    sample_id: int = None,
) -> MetricSample:
    """Helper to construct a valid metric sample."""
    return MetricSample(
        id=sample_id,
        service=service,
        timestamp=datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc),
        latency_ms=latency,
        error_rate=error_rate,
        request_count=requests,
        cpu_usage_pct=cpu,
        memory_usage_pct=memory,
        is_synthetic=True,
    )


def test_1_model_fitting_succeeds_on_valid_normal_data():
    """Verify IsolationForest fits cleanly on normal baseline samples."""
    train_data = generate_metrics_with_anomalies(
        service="checkout-service",
        total_samples=50,
        seed=100,
        latency_spike_count=0,
        error_spike_count=0,
    ).samples

    detector = IsolationForestDetector(random_state=42, n_estimators=50, contamination=0.05)
    assert not detector.is_fitted

    detector.fit(train_data)
    assert detector.is_fitted
    assert detector._training_sample_count == 50


def test_2_anomaly_prediction_succeeds():
    """Verify detector flags an obvious multi-metric anomalous sample."""
    train_data = generate_metrics_with_anomalies(
        total_samples=50,
        seed=100,
        latency_spike_count=0,
        error_spike_count=0,
    ).samples

    detector = IsolationForestDetector(random_state=42, contamination=0.05)
    detector.fit(train_data)

    # Severe anomaly: 450ms latency + 85% CPU + 25% error rate
    anomaly = make_sample(latency=450.0, error_rate=0.25, cpu=85.0, memory=75.0, requests=300)
    finding = detector.predict_sample(anomaly)

    assert finding is not None
    assert isinstance(finding, MLDetectionFinding)
    assert finding.prediction_label == -1
    assert finding.detector_name == "isolation_forest"


def test_3_prediction_labels_are_valid_sklearn_outputs():
    """Verify prediction labels are strictly -1 (outlier) or +1 (inlier)."""
    train_data = generate_metrics_with_anomalies(
        total_samples=50, seed=100, latency_spike_count=0, error_spike_count=0
    ).samples
    detector = IsolationForestDetector(random_state=42)
    detector.fit(train_data)

    normal = make_sample(latency=42.0, error_rate=0.005)
    anomaly = make_sample(latency=500.0, error_rate=0.30, cpu=85.0, memory=75.0, requests=250)

    # Normal sample should not be flagged (returns None from predict_sample)
    assert detector.predict_sample(normal) is None

    # Anomaly should return finding with prediction_label == -1
    f = detector.predict_sample(anomaly)
    assert f is not None
    assert f.prediction_label == -1


def test_4_anomaly_scores_are_real_numerical_values():
    """Verify decision function outputs finite float scores."""
    train_data = generate_metrics_with_anomalies(
        total_samples=50, seed=100, latency_spike_count=0, error_spike_count=0
    ).samples
    detector = IsolationForestDetector(random_state=42)
    detector.fit(train_data)

    scores = detector.score_samples(train_data[:5])
    assert len(scores) == 5
    for s in scores:
        assert isinstance(s, float)
        assert math.isfinite(s)


def test_5_repeated_runs_with_same_seed_are_reproducible():
    """Verify deterministic outputs when random_state is identical."""
    train_data = generate_metrics_with_anomalies(
        total_samples=50, seed=100, latency_spike_count=0, error_spike_count=0
    ).samples

    det1 = IsolationForestDetector(random_state=42, n_estimators=50)
    det2 = IsolationForestDetector(random_state=42, n_estimators=50)

    det1.fit(train_data)
    det2.fit(train_data)

    test_samples = [make_sample(latency=300.0), make_sample(latency=42.0)]
    scores1 = det1.score_samples(test_samples)
    scores2 = det2.score_samples(test_samples)

    assert scores1 == scores2


def test_6_feature_ordering_remains_consistent():
    """Verify FEATURE_NAMES tuple specifies exact 5 features in documented order."""
    expected = ("latency_ms", "error_rate", "cpu_usage_pct", "memory_usage_pct", "request_count")
    assert FEATURE_NAMES == expected

    detector = IsolationForestDetector()
    sample = make_sample(latency=40.0, error_rate=0.01, cpu=25.0, memory=45.0, requests=120)
    features, meta = detector._extract_features(sample)

    assert features == [40.0, 0.01, 25.0, 45.0, 120.0]


def test_7_missing_features_are_rejected():
    """Verify dictionary missing a feature raises ValueError."""
    detector = IsolationForestDetector()
    incomplete = {
        "service": "checkout-service",
        "latency_ms": 40.0,
        "error_rate": 0.01,
        # missing cpu, memory, request_count
    }
    with pytest.raises(ValueError, match="Missing required feature"):
        detector._extract_features(incomplete)


def test_8_nan_and_infinite_values_are_rejected():
    """Verify non-finite float values (NaN, Inf, -Inf) are rejected with ValueError."""
    detector = IsolationForestDetector()
    base = {
        "service": "checkout-service",
        "latency_ms": 40.0,
        "error_rate": 0.01,
        "cpu_usage_pct": 25.0,
        "memory_usage_pct": 45.0,
        "request_count": 120,
    }

    # NaN
    with pytest.raises(ValueError, match="must be finite, got non-finite value nan"):
        detector._extract_features({**base, "latency_ms": float("nan")})

    # Positive Infinity
    with pytest.raises(ValueError, match="must be finite, got non-finite value inf"):
        detector._extract_features({**base, "error_rate": float("inf")})

    # Negative Infinity
    with pytest.raises(ValueError, match="must be finite, got non-finite value -inf"):
        detector._extract_features({**base, "cpu_usage_pct": float("-inf")})


def test_9_non_numeric_inputs_are_handled_safely():
    """Verify strings, booleans, or None values raise TypeError or ValueError."""
    detector = IsolationForestDetector()
    base = {
        "service": "checkout-service",
        "latency_ms": 40.0,
        "error_rate": 0.01,
        "cpu_usage_pct": 25.0,
        "memory_usage_pct": 45.0,
        "request_count": 120,
    }

    # String value
    with pytest.raises(TypeError, match="must be numeric"):
        detector._extract_features({**base, "latency_ms": "high"})

    # Boolean value
    with pytest.raises(TypeError, match="got boolean"):
        detector._extract_features({**base, "latency_ms": False})

    # None value
    with pytest.raises(ValueError, match="cannot be None"):
        detector._extract_features({**base, "latency_ms": None})


def test_10_empty_training_datasets_are_rejected():
    """Verify fit() rejects empty sample sequence."""
    detector = IsolationForestDetector()
    with pytest.raises(ValueError, match="Training dataset cannot be empty"):
        detector.fit([])


def test_11_insufficient_training_data_is_handled():
    """Verify fit() rejects fewer than 10 samples."""
    detector = IsolationForestDetector()
    small_data = [make_sample() for _ in range(5)]
    with pytest.raises(ValueError, match="Insufficient training data"):
        detector.fit(small_data)


def test_12_unfitted_prediction_fails_clearly():
    """Verify predict_sample, score_samples, and detect fail if model is not fitted."""
    detector = IsolationForestDetector()
    sample = make_sample()

    with pytest.raises(RuntimeError, match="must be fitted before predicting"):
        detector.predict_sample(sample)

    with pytest.raises(RuntimeError, match="must be fitted before scoring"):
        detector.score_samples([sample])

    with pytest.raises(RuntimeError, match="must be fitted before running detect"):
        detector.detect([sample])


def test_13_ground_truth_labels_not_included_in_feature_matrices():
    """
    CRITICAL ANTI-LEAKAGE: Verify features extracted for IsolationForest contain
    exclusively the 5 operational metric measurements.
    """
    sample = make_sample()
    detector = IsolationForestDetector()
    features, meta = detector._extract_features(sample)

    # Dimensionality must be exactly 5
    assert len(features) == 5
    assert "is_anomaly" not in meta["observed_values"]
    assert "anomaly_type" not in meta["observed_values"]
    assert "ground_truth" not in meta["observed_values"]


def test_14_training_and_evaluation_datasets_remain_separate():
    """Verify model fitted on training seed 100 detects anomalies in disjoint evaluation seed 42."""
    # Training data: 60 clean samples from seed 100
    train_res = generate_metrics_with_anomalies(
        service="checkout-service",
        total_samples=60,
        seed=100,
        latency_spike_count=0,
        error_spike_count=0,
    )
    assert len(train_res.ground_truth) == 0

    # Evaluation data: 50 samples from seed 42 with 2 latency spikes and 1 error spike
    eval_res = generate_metrics_with_anomalies(
        service="checkout-service",
        total_samples=50,
        seed=42,
        latency_spike_count=2,
        error_spike_count=1,
    )
    assert len(eval_res.ground_truth) == 3

    detector = IsolationForestDetector(random_state=42, contamination=0.06)
    detector.fit(train_res.samples)

    findings = detector.detect(eval_res.samples)
    assert len(findings) > 0


def test_15_existing_synthetic_samples_work_with_ml_detector():
    """Verify detector processes standard MetricSample objects generated by existing services."""
    samples = generate_metrics_with_anomalies(total_samples=40, seed=77).samples
    detector = IsolationForestDetector(random_state=42)
    detector.fit(samples)

    findings = detector.detect(samples)
    assert isinstance(findings, list)


def test_16_detector_metadata_is_present_and_accurate():
    """Verify finding contains complete model hyperparameters and metadata."""
    train_data = generate_metrics_with_anomalies(
        total_samples=40, seed=100, latency_spike_count=0, error_spike_count=0
    ).samples

    detector = IsolationForestDetector(
        random_state=99,
        n_estimators=120,
        contamination=0.08,
        name="custom_iforest",
        version="1.2.0",
    )
    detector.fit(train_data)

    severe_spike = make_sample(latency=500.0, error_rate=0.30, cpu=90.0)
    finding = detector.predict_sample(severe_spike)

    assert finding is not None
    assert finding.detector_name == "custom_iforest"
    assert finding.detector_version == "1.2.0"
    assert finding.model_metadata["n_estimators"] == 120
    assert finding.model_metadata["contamination"] == 0.08
    assert finding.model_metadata["random_state"] == 99
    assert finding.model_metadata["training_sample_count"] == 40
    assert finding.model_metadata["feature_names"] == list(FEATURE_NAMES)


def test_17_detection_findings_contain_real_observed_evidence():
    """Verify observed_metric_values faithfully preserves input measurements."""
    train_data = generate_metrics_with_anomalies(
        total_samples=40, seed=100, latency_spike_count=0, error_spike_count=0
    ).samples
    detector = IsolationForestDetector(random_state=42)
    detector.fit(train_data)

    spike = make_sample(latency=412.50, error_rate=0.185, cpu=78.2, memory=52.1, requests=220)
    finding = detector.predict_sample(spike)

    assert finding is not None
    obs = finding.observed_metric_values
    assert obs["latency_ms"] == 412.50
    assert obs["error_rate"] == 0.185
    assert obs["cpu_usage_pct"] == 78.2
    assert obs["memory_usage_pct"] == 52.1
    assert obs["request_count"] == 220
    assert str(finding.anomaly_score) in finding.explanation


def test_18_existing_threshold_detector_remains_functional():
    """Verify coexistence: ThresholdDetector and IsolationForestDetector operate independently."""
    sample = make_sample(latency=450.0, error_rate=0.20, cpu=80.0, memory=70.0, requests=200)

    # Threshold detector
    t_detector = ThresholdDetector()
    t_finding = t_detector.detect_sample(sample)
    assert t_finding is not None
    assert t_finding.detector_name == "threshold_baseline"

    # ML detector
    train_data = generate_metrics_with_anomalies(
        total_samples=40, seed=100, latency_spike_count=0, error_spike_count=0
    ).samples
    ml_detector = IsolationForestDetector(random_state=42)
    ml_detector.fit(train_data)
    ml_finding = ml_detector.predict_sample(sample)
    assert ml_finding is not None
    assert ml_finding.detector_name == "isolation_forest"
