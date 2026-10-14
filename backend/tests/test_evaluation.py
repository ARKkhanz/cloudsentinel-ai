"""
Automated unit and regression tests for detector evaluation, metric mathematics,
confusion matrix properties, dataset isolation, and reproducibility.
"""

from typing import List
import pytest

from backend.app.detection.isolation_forest_detector import (
    FEATURE_NAMES,
    IsolationForestDetector,
)
from backend.app.detection.threshold_detector import ThresholdDetector
from backend.app.services.anomaly_generator import generate_metrics_with_anomalies
from backend.scripts.evaluate_detectors import (
    calculate_metrics,
    run_evaluation,
)


def test_1_confusion_matrix_and_metric_calculations():
    """
    Verify accurate TP/FP/TN/FN counts, Precision, Recall, F1, and FPR on known ground-truth vectors.
    """
    # 10 samples: 3 ground-truth anomalies (indices 0, 1, 2)
    y_true = [1, 1, 1, 0, 0, 0, 0, 0, 0, 0]
    # Predictions: flags 0, 1 (TP=2), misses 2 (FN=1), flags 3 (FP=1), correctly clears 4-9 (TN=6)
    y_pred = [1, 1, 0, 1, 0, 0, 0, 0, 0, 0]

    metrics = calculate_metrics(
        y_true=y_true,
        y_pred=y_pred,
        detector_name="test_detector",
        detector_type="test_type",
        config={},
    )

    assert metrics.total_samples == 10
    assert metrics.ground_truth_anomalies == 3
    assert metrics.predicted_anomalies == 3
    assert metrics.true_positives == 2
    assert metrics.false_positives == 1
    assert metrics.true_negatives == 6
    assert metrics.false_negatives == 1

    # Precision = 2 / (2 + 1) = 0.6667
    assert metrics.precision == pytest.approx(2 / 3, abs=1e-4)
    # Recall = 2 / (2 + 1) = 0.6667
    assert metrics.recall == pytest.approx(2 / 3, abs=1e-4)
    # F1 = 2 * (2/3 * 2/3) / (4/3) = 2/3 = 0.6667
    assert metrics.f1_score == pytest.approx(2 / 3, abs=1e-4)
    # FPR = 1 / (1 + 6) = 1/7 = 0.1429
    assert metrics.false_positive_rate == pytest.approx(1 / 7, abs=1e-4)


def test_2_zero_denominator_behavior():
    """
    Verify mathematical safety when zero anomalies are predicted or zero ground truth exists.
    Must return 0.0 rather than raising ZeroDivisionError.
    """
    # Case A: No positive predictions (TP=0, FP=0) -> Precision denominator = 0
    y_true_a = [1, 1, 0, 0]
    y_pred_a = [0, 0, 0, 0]
    metrics_a = calculate_metrics(y_true_a, y_pred_a, "det_a", "type_a", {})
    assert metrics_a.true_positives == 0
    assert metrics_a.false_positives == 0
    assert metrics_a.precision == 0.0
    assert metrics_a.recall == 0.0
    assert metrics_a.f1_score == 0.0
    assert metrics_a.false_positive_rate == 0.0

    # Case B: No ground truth anomalies (TP=0, FN=0) -> Recall denominator = 0
    y_true_b = [0, 0, 0, 0]
    y_pred_b = [1, 0, 0, 0]
    metrics_b = calculate_metrics(y_true_b, y_pred_b, "det_b", "type_b", {})
    assert metrics_b.true_positives == 0
    assert metrics_b.false_positives == 1
    assert metrics_b.precision == 0.0
    assert metrics_b.recall == 0.0
    assert metrics_b.f1_score == 0.0
    assert metrics_b.false_positive_rate == pytest.approx(1 / 4, abs=1e-4)


def test_3_confusion_matrix_sum_equals_total_samples():
    """Verify TP + FP + TN + FN == total_samples in all scenarios."""
    cases = [
        ([1, 0, 1, 0, 1], [1, 1, 1, 0, 0]),
        ([0, 0, 0], [0, 0, 0]),
        ([1, 1, 1], [1, 1, 1]),
        ([1, 0, 0, 1, 0, 0, 0], [0, 1, 0, 0, 0, 1, 0]),
    ]
    for yt, yp in cases:
        m = calculate_metrics(yt, yp, "test", "test", {})
        assert m.true_positives + m.false_positives + m.true_negatives + m.false_negatives == len(yt)


def test_4_rejection_of_mismatched_vector_lengths():
    """Verify calculate_metrics rejects differing vector lengths."""
    with pytest.raises(ValueError, match="Length mismatch"):
        calculate_metrics([1, 0, 1], [1, 0], "test", "test", {})


def test_5_stable_feature_names_order():
    """Verify canonical ML feature names and ordering are immutable."""
    assert FEATURE_NAMES == (
        "latency_ms",
        "error_rate",
        "cpu_usage_pct",
        "memory_usage_pct",
        "request_count",
    )


def test_6_training_and_evaluation_data_separation():
    """
    Verify training and evaluation datasets are completely independent:
    - Training has 0 anomalies.
    - Evaluation has 5 injected anomalies.
    - Timestamps and numeric values are disjoint.
    """
    train_gen = generate_metrics_with_anomalies(total_samples=100, seed=100, latency_spike_count=0, error_spike_count=0)
    eval_gen = generate_metrics_with_anomalies(total_samples=100, seed=42, latency_spike_count=3, error_spike_count=2)

    assert len(train_gen.ground_truth) == 0
    assert len(eval_gen.ground_truth) == 5

    # Check distinct values
    train_latencies = [s.latency_ms for s in train_gen.samples]
    eval_latencies = [s.latency_ms for s in eval_gen.samples]
    assert train_latencies != eval_latencies

    # Check maximum latency: eval has injected spikes > 300ms, train baseline stays < 70ms
    assert max(eval_latencies) > 300.0
    assert max(train_latencies) < 70.0


def test_7_no_ground_truth_leakage_in_features():
    """
    Verify that telemetry objects supplied to detectors contain only numerical measurements
    and never include ground-truth flags or labels.
    """
    eval_gen = generate_metrics_with_anomalies(total_samples=50, seed=42)
    for sample in eval_gen.samples:
        d = sample.model_dump()
        assert "ground_truth" not in d
        assert "is_anomaly" not in d
        assert "anomaly_type" not in d


def test_8_reproducible_evaluation_execution():
    """
    Verify that running the evaluation pipeline produces identical results on repeated calls.
    """
    res1, _ = run_evaluation()
    res2, _ = run_evaluation()

    t1, t2 = res1["threshold_baseline"], res2["threshold_baseline"]
    assert t1.true_positives == t2.true_positives
    assert t1.false_positives == t2.false_positives
    assert t1.f1_score == t2.f1_score

    m1, m2 = res1["isolation_forest"], res2["isolation_forest"]
    assert m1.true_positives == m2.true_positives
    assert m1.false_positives == m2.false_positives
    assert m1.f1_score == m2.f1_score


def test_9_empirical_detector_evaluation_metrics():
    """
    Assert the exact measured confusion matrices for ThresholdDetector and IsolationForestDetector
    on the standard benchmark (Seed 100 Train / Seed 42 Eval, 3 latency spikes, 2 error surges).
    """
    results, trace = run_evaluation()

    # Threshold Detector
    t = results["threshold_baseline"]
    assert t.total_samples == 100
    assert t.ground_truth_anomalies == 5
    assert t.predicted_anomalies == 5
    assert t.true_positives == 5
    assert t.false_positives == 0
    assert t.true_negatives == 95
    assert t.false_negatives == 0
    assert t.precision == 1.0
    assert t.recall == 1.0
    assert t.f1_score == 1.0
    assert t.false_positive_rate == 0.0

    # IsolationForest Detector
    m = results["isolation_forest"]
    assert m.total_samples == 100
    assert m.ground_truth_anomalies == 5
    assert m.predicted_anomalies == 5
    assert m.true_positives == 4
    assert m.false_positives == 1
    assert m.true_negatives == 94
    assert m.false_negatives == 1
    assert m.precision == 0.8
    assert m.recall == 0.8
    assert m.f1_score == 0.8
    assert m.false_positive_rate == pytest.approx(1 / 95, abs=1e-4)
