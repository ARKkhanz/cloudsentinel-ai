"""
CloudSentinel AI — Reproducible Anomaly Detector Evaluation Script
Evaluates ThresholdDetector and IsolationForestDetector against held-out synthetic telemetry.

Methodology:
- Clean Training Baseline: Seed 100, 100 normal samples (0 injected anomalies).
- Held-out Evaluation Set: Seed 42, 100 samples (3 latency spikes, 2 error rate surges = 5 ground-truth anomalies).
- Feature Vectors: ('latency_ms', 'error_rate', 'cpu_usage_pct', 'memory_usage_pct', 'request_count').
- Strict Separation: Zero leakage; detectors only evaluate numerical telemetry, never ground-truth labels.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

# Ensure repository root is on sys.path
repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from backend.app.detection.isolation_forest_detector import (
    FEATURE_NAMES,
    IsolationForestDetector,
    MLDetectionFinding,
)
from backend.app.detection.threshold_detector import (
    ThresholdDetector,
    ThresholdFinding,
)
from backend.app.services.anomaly_generator import (
    DEFAULT_REFERENCE_TIME,
    generate_metrics_with_anomalies,
)


@dataclass
class EvaluationMetrics:
    detector_name: str
    detector_type: str
    total_samples: int
    ground_truth_anomalies: int
    predicted_anomalies: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    false_positive_rate: float
    config: Dict[str, Any]


def calculate_metrics(
    y_true: List[int],
    y_pred: List[int],
    detector_name: str,
    detector_type: str,
    config: Dict[str, Any],
) -> EvaluationMetrics:
    """
    Compute confusion matrix counts and classification metrics with division-by-zero safety.
    
    Formulas:
    - TP: y_true=1 and y_pred=1
    - FP: y_true=0 and y_pred=1
    - TN: y_true=0 and y_pred=0
    - FN: y_true=1 and y_pred=0
    - Precision = TP / (TP + FP)
    - Recall = TP / (TP + FN)
    - F1 = 2 * Precision * Recall / (Precision + Recall)
    - FPR = FP / (FP + TN)
    """
    if len(y_true) != len(y_pred):
        raise ValueError(f"Length mismatch: y_true ({len(y_true)}) != y_pred ({len(y_pred)})")

    tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 1)
    fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 1)
    tn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 0)
    fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 0)

    total = len(y_true)
    assert tp + fp + tn + fn == total, f"Confusion sum ({tp + fp + tn + fn}) != total ({total})"

    gt_anomalies = sum(y_true)
    pred_anomalies = sum(y_pred)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2.0 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    return EvaluationMetrics(
        detector_name=detector_name,
        detector_type=detector_type,
        total_samples=total,
        ground_truth_anomalies=gt_anomalies,
        predicted_anomalies=pred_anomalies,
        true_positives=tp,
        false_positives=fp,
        true_negatives=tn,
        false_negatives=fn,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1_score=round(f1, 4),
        false_positive_rate=round(fpr, 4),
        config=config,
    )


def run_evaluation(
    service: str = "demo-api",
    train_seed: int = 100,
    train_samples: int = 100,
    eval_seed: int = 42,
    eval_samples: int = 100,
    latency_spikes: int = 3,
    error_spikes: int = 2,
    threshold_latency_ms: float = 150.0,
    threshold_error_rate: float = 0.05,
    if_random_state: int = 42,
    if_n_estimators: int = 100,
    if_contamination: float = 0.05,
) -> Tuple[Dict[str, EvaluationMetrics], Dict[str, Any]]:
    """
    Execute controlled, reproducible evaluation of ThresholdDetector and IsolationForestDetector.
    """
    # 1. Generate clean training baseline (strictly 0 anomalies)
    train_gen = generate_metrics_with_anomalies(
        service=service,
        total_samples=train_samples,
        seed=train_seed,
        latency_spike_count=0,
        error_spike_count=0,
    )
    training_data = train_gen.samples
    assert len(training_data) == train_samples
    assert len(train_gen.ground_truth) == 0

    # 2. Generate held-out evaluation dataset with injected anomalies
    eval_gen = generate_metrics_with_anomalies(
        service=service,
        total_samples=eval_samples,
        seed=eval_seed,
        latency_spike_count=latency_spikes,
        error_spike_count=error_spikes,
    )
    eval_data = eval_gen.samples
    ground_truth_list = eval_gen.ground_truth

    # Map ground-truth anomalies to binary array (1 for anomaly, 0 for normal)
    gt_indices = {gt.sample_index for gt in ground_truth_list}
    y_true = [1 if i in gt_indices else 0 for i in range(eval_samples)]
    assert sum(y_true) == latency_spikes + error_spikes

    # 3. Evaluate ThresholdDetector
    t_detector = ThresholdDetector(
        latency_threshold_ms=threshold_latency_ms,
        error_rate_threshold=threshold_error_rate,
    )
    t_config = {
        "latency_threshold_ms": threshold_latency_ms,
        "error_rate_threshold": threshold_error_rate,
    }

    t_findings_map = {}
    y_pred_threshold: List[int] = []
    for idx, sample in enumerate(eval_data):
        finding = t_detector.detect_sample(sample)
        if finding is not None:
            y_pred_threshold.append(1)
            t_findings_map[idx] = finding
        else:
            y_pred_threshold.append(0)

    threshold_metrics = calculate_metrics(
        y_true=y_true,
        y_pred=y_pred_threshold,
        detector_name=t_detector.name,
        detector_type="statistical_threshold",
        config=t_config,
    )

    # 4. Evaluate IsolationForestDetector
    ml_detector = IsolationForestDetector(
        random_state=if_random_state,
        n_estimators=if_n_estimators,
        contamination=if_contamination,
    )
    ml_detector.fit(training_data)
    ml_config = {
        "random_state": if_random_state,
        "n_estimators": if_n_estimators,
        "contamination": if_contamination,
        "training_samples": train_samples,
        "training_seed": train_seed,
        "feature_names": list(FEATURE_NAMES),
    }

    ml_findings_map = {}
    y_pred_ml: List[int] = []
    for idx, sample in enumerate(eval_data):
        finding = ml_detector.predict_sample(sample)
        if finding is not None:
            y_pred_ml.append(1)
            ml_findings_map[idx] = finding
        else:
            y_pred_ml.append(0)

    ml_metrics = calculate_metrics(
        y_true=y_true,
        y_pred=y_pred_ml,
        detector_name=ml_detector.name,
        detector_type="unsupervised_isolation_forest",
        config=ml_config,
    )

    # Detailed qualitative trace
    trace: Dict[str, Any] = {
        "metadata": {
            "service": service,
            "train_samples": train_samples,
            "train_seed": train_seed,
            "eval_samples": eval_samples,
            "eval_seed": eval_seed,
            "latency_spikes_injected": latency_spikes,
            "error_spikes_injected": error_spikes,
            "total_ground_truth_anomalies": sum(y_true),
        },
        "ground_truth_items": [
            {
                "sample_index": gt.sample_index,
                "timestamp": gt.timestamp.isoformat(),
                "anomaly_type": gt.anomaly_type,
                "injected_value": gt.injected_value,
                "baseline_mean": gt.baseline_mean,
            }
            for gt in ground_truth_list
        ],
        "threshold_findings": {
            str(idx): {
                "observed": f.observed_metric_values,
                "conditions": f.triggered_conditions,
                "summary": f.summary,
            }
            for idx, f in t_findings_map.items()
        },
        "ml_findings": {
            str(idx): {
                "observed": f.observed_metric_values,
                "anomaly_score": f.anomaly_score,
                "summary": f.summary,
            }
            for idx, f in ml_findings_map.items()
        },
    }

    results = {
        "threshold_baseline": threshold_metrics,
        "isolation_forest": ml_metrics,
    }

    return results, trace


def print_evaluation_report(results: Dict[str, EvaluationMetrics], trace: Dict[str, Any]) -> None:
    """Print structured, publication-quality evaluation table to stdout."""
    print("=" * 82)
    print(" CLOUDSENTINEL AI — DETECTOR BENCHMARK & EVALUATION REPORT")
    print("=" * 82)
    meta = trace["metadata"]
    print(f"Dataset Configuration:")
    print(f"  Training Baseline : {meta['train_samples']} samples (Seed {meta['train_seed']}, 0 anomalies injected)")
    print(f"  Evaluation Set    : {meta['eval_samples']} samples (Seed {meta['eval_seed']}, {meta['total_ground_truth_anomalies']} anomalies injected)")
    print(f"  Injected Breakdown: {meta['latency_spikes_injected']} latency spikes, {meta['error_spikes_injected']} error surges")
    print("-" * 82)

    headers = f"{'Metric / Property':<28} | {'Threshold Baseline':<24} | {'IsolationForest':<24}"
    print(headers)
    print("-" * 82)

    t = results["threshold_baseline"]
    m = results["isolation_forest"]

    rows = [
        ("Algorithm Type", t.detector_type, m.detector_type),
        ("Total Samples Evaluated", str(t.total_samples), str(m.total_samples)),
        ("Ground-Truth Anomalies", str(t.ground_truth_anomalies), str(m.ground_truth_anomalies)),
        ("Predicted Anomalies", str(t.predicted_anomalies), str(m.predicted_anomalies)),
        ("True Positives (TP)", str(t.true_positives), str(m.true_positives)),
        ("False Positives (FP)", str(t.false_positives), str(m.false_positives)),
        ("True Negatives (TN)", str(t.true_negatives), str(m.true_negatives)),
        ("False Negatives (FN)", str(t.false_negatives), str(m.false_negatives)),
        ("Precision", f"{t.precision:.4f} ({t.precision*100:.1f}%)", f"{m.precision:.4f} ({m.precision*100:.1f}%)"),
        ("Recall", f"{t.recall:.4f} ({t.recall*100:.1f}%)", f"{m.recall:.4f} ({m.recall*100:.1f}%)"),
        ("F1 Score", f"{t.f1_score:.4f}", f"{m.f1_score:.4f}"),
        ("False-Positive Rate (FPR)", f"{t.false_positive_rate:.4f} ({t.false_positive_rate*100:.2f}%)", f"{m.false_positive_rate:.4f} ({m.false_positive_rate*100:.2f}%)"),
    ]

    for label, t_val, m_val in rows:
        print(f"{label:<28} | {t_val:<24} | {m_val:<24}")

    print("=" * 82)
    print("\nConfusion Matrices:")
    print("  Threshold Baseline:")
    print(f"    [[TN={t.true_negatives}, FP={t.false_positives}],")
    print(f"     [FN={t.false_negatives}, TP={t.true_positives}]]")
    print("  IsolationForest:")
    print(f"    [[TN={m.true_negatives}, FP={m.false_positives}],")
    print(f"     [FN={m.false_negatives}, TP={m.true_positives}]]")
    print("=" * 82)


if __name__ == "__main__":
    results, trace = run_evaluation()
    print_evaluation_report(results, trace)

    # Save deterministic JSON artifact
    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "evaluation_results.json")
    
    export_payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            k: asdict(v) for k, v in results.items()
        },
        "trace": trace,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(export_payload, f, indent=2)
    print(f"\nSaved evaluation metrics to: {out_path}\n")
