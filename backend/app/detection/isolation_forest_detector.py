from datetime import datetime
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np
from pydantic import BaseModel, Field
from sklearn.ensemble import IsolationForest

from backend.app.schemas.metrics import MetricSample

# Canonical fixed order of numerical features used for multivariate anomaly detection
FEATURE_NAMES: Tuple[str, ...] = (
    "latency_ms",
    "error_rate",
    "cpu_usage_pct",
    "memory_usage_pct",
    "request_count",
)


class MLDetectionFinding(BaseModel):
    """
    Structured multivariate anomaly detection finding produced by IsolationForest.
    
    Provides factual mathematical evidence (anomaly score and decision function)
    without fabricating root cause attribution that unsupervised tree isolation
    does not provide.
    """
    service: str = Field(..., description="Service identifier associated with the observation")
    timestamp: datetime = Field(..., description="UTC timestamp of the anomalous observation")
    metric_id: Optional[int] = Field(None, description="Database record primary key if persisted")
    detector_name: str = Field("isolation_forest", description="Identifier of the detector algorithm")
    detector_version: str = Field("1.0.0", description="Version of the detector model implementation")
    severity: str = Field(..., description="Severity level based on anomaly score severity: 'critical' or 'warning'")
    summary: str = Field(..., description="Concise human-readable title of the multivariate anomaly")
    anomaly_score: float = Field(..., description="Raw decision_function score (negative values denote outliers)")
    prediction_label: int = Field(-1, description="Binary classification output: -1 for outlier, +1 for inlier")
    observed_metric_values: Dict[str, float] = Field(
        ...,
        description="Factual numerical metric measurements at time of detection",
    )
    model_metadata: Dict[str, Any] = Field(
        ...,
        description="Parameters and hyperparameters of the fitted IsolationForest model",
    )
    explanation: str = Field(
        ...,
        description="Factual, non-speculative explanation of the IsolationForest decision",
    )


class IsolationForestDetector:
    """
    Multivariate anomaly detector utilizing Scikit-Learn's IsolationForest.
    
    IsolationForest works by recursively partitioning feature space using random axis-aligned
    splits. Because anomalies have distinct multi-metric values, they require significantly
    fewer random partitions to isolate from normal dense clusters (shorter average tree path length).
    
    CRITICAL ARCHITECTURAL CONSTRAINTS:
    - Features: Strictly uses FEATURE_NAMES ('latency_ms', 'error_rate', 'cpu_usage_pct',
      'memory_usage_pct', 'request_count') in deterministic order.
    - Zero Leakage: Never includes timestamps, IDs, synthetic flags, or ground-truth labels.
    - Data Separation: Model must be fitted on clean baseline training data, and scored on a
      disjoint held-out evaluation dataset.
    - Contamination: Contamination parameter is a modeling assumption (expected outlier proportion),
      not an empirical label.
    """

    def __init__(
        self,
        random_state: int = 42,
        n_estimators: int = 100,
        contamination: float = 0.05,
        name: str = "isolation_forest",
        version: str = "1.0.0",
    ) -> None:
        if n_estimators <= 0:
            raise ValueError(f"n_estimators must be a positive integer, got {n_estimators}")
        if not (0.0 < contamination <= 0.5):
            raise ValueError(f"contamination must be in range (0.0, 0.5], got {contamination}")

        self.random_state = random_state
        self.n_estimators = n_estimators
        self.contamination = contamination
        self.name = name
        self.version = version

        self.model = IsolationForest(
            n_estimators=self.n_estimators,
            contamination=self.contamination,
            random_state=self.random_state,
        )
        self._is_fitted: bool = False
        self._training_sample_count: int = 0

    @property
    def is_fitted(self) -> bool:
        """Returns True if the detector has been fitted on training data."""
        return self._is_fitted

    def _validate_finite_number(self, field_name: str, value: Any) -> float:
        """Validate that a field value is present, non-boolean numeric, and finite."""
        if value is None:
            raise ValueError(f"Missing required metric value for '{field_name}' (value cannot be None)")
        if isinstance(value, bool):
            raise TypeError(f"Metric field '{field_name}' must be a numerical value, got boolean")
        try:
            num = float(value)
        except (ValueError, TypeError) as exc:
            raise TypeError(f"Metric field '{field_name}' must be numeric, got {type(value).__name__}") from exc

        if not math.isfinite(num):
            raise ValueError(f"Metric field '{field_name}' must be finite, got non-finite value {num}")
        return num

    def _extract_features(
        self,
        sample: Union[MetricSample, Any, Dict[str, Any]],
    ) -> Tuple[List[float], Dict[str, Any]]:
        """
        Extract numerical features in strict FEATURE_NAMES order and metadata.
        Rejects missing, non-numeric, or non-finite values.
        """
        features: List[float] = []
        observed_values: Dict[str, float] = {}

        if isinstance(sample, dict):
            service = sample.get("service", "unknown")
            timestamp = sample.get("timestamp")
            metric_id = sample.get("id")
            for feat_name in FEATURE_NAMES:
                if feat_name not in sample:
                    raise ValueError(f"Missing required feature: '{feat_name}'")
                val = self._validate_finite_number(feat_name, sample[feat_name])
                features.append(val)
                observed_values[feat_name] = val
        else:
            service = getattr(sample, "service", "unknown")
            timestamp = getattr(sample, "timestamp", None)
            metric_id = getattr(sample, "id", None)
            for feat_name in FEATURE_NAMES:
                if not hasattr(sample, feat_name):
                    raise ValueError(f"Missing required feature: '{feat_name}'")
                val = self._validate_finite_number(feat_name, getattr(sample, feat_name))
                features.append(val)
                observed_values[feat_name] = val

        meta = {
            "service": service,
            "timestamp": timestamp,
            "id": metric_id,
            "observed_values": observed_values,
        }
        return features, meta

    def fit(
        self,
        samples: Sequence[Union[MetricSample, Any, Dict[str, Any]]],
    ) -> "IsolationForestDetector":
        """
        Fit the IsolationForest model on a baseline training dataset.
        
        Args:
            samples: Sequence of metric samples representing normal operational behavior.
            
        Raises:
            ValueError: If the training dataset is empty or contains fewer than 10 samples.
            ValueError / TypeError: If any sample contains missing, non-numeric, or non-finite values.
        """
        if not samples:
            raise ValueError("Training dataset cannot be empty")
        if len(samples) < 10:
            raise ValueError(
                f"Insufficient training data: IsolationForest requires at least 10 samples to fit, "
                f"got {len(samples)}"
            )

        X_rows: List[List[float]] = []
        for sample in samples:
            features, _ = self._extract_features(sample)
            X_rows.append(features)

        X = np.array(X_rows, dtype=np.float64)
        self.model.fit(X)
        self._is_fitted = True
        self._training_sample_count = len(samples)
        return self

    def score_samples(
        self,
        samples: Sequence[Union[MetricSample, Any, Dict[str, Any]]],
    ) -> List[float]:
        """
        Compute raw anomaly decision function scores for a sequence of samples.
        
        In Scikit-Learn's IsolationForest, decision_function returns:
        - Negative values for anomalous outliers.
        - Positive values for normal inliers.
        """
        if not self._is_fitted:
            raise RuntimeError("IsolationForestDetector must be fitted before scoring samples")
        if not samples:
            return []

        X_rows: List[List[float]] = []
        for sample in samples:
            features, _ = self._extract_features(sample)
            X_rows.append(features)

        X = np.array(X_rows, dtype=np.float64)
        scores: np.ndarray = self.model.decision_function(X)
        return scores.tolist()

    def predict_sample(
        self,
        sample: Union[MetricSample, Any, Dict[str, Any]],
    ) -> Optional[MLDetectionFinding]:
        """
        Predict whether a single observation is an outlier.
        
        Returns:
            MLDetectionFinding if the observation is predicted as an outlier (predict = -1).
            None if the observation is classified as normal (predict = +1).
        """
        if not self._is_fitted:
            raise RuntimeError("IsolationForestDetector must be fitted before predicting samples")

        features, meta = self._extract_features(sample)
        X = np.array([features], dtype=np.float64)

        pred = int(self.model.predict(X)[0])  # -1 for outlier, +1 for inlier
        score = float(self.model.decision_function(X)[0])

        if pred != -1:
            return None

        # Severity mapping: very negative scores (< -0.15) represent extreme subspace outliers
        severity = "critical" if score < -0.15 else "warning"
        summary = (
            f"Multivariate Anomaly Detected by IsolationForest on {meta['service']} "
            f"(score: {score:.4f})"
        )

        model_meta = {
            "n_estimators": self.n_estimators,
            "contamination": self.contamination,
            "random_state": self.random_state,
            "feature_names": list(FEATURE_NAMES),
            "training_sample_count": self._training_sample_count,
        }

        explanation = (
            f"IsolationForest classified this observation as an outlier based on its combined "
            f"numerical telemetry features ({', '.join(FEATURE_NAMES)}). The recorded decision "
            f"score was {score:.4f} (negative decision score indicates isolation in anomalous subspace)."
        )

        return MLDetectionFinding(
            service=meta["service"],
            timestamp=meta["timestamp"] or datetime.now(),
            metric_id=meta["id"],
            detector_name=self.name,
            detector_version=self.version,
            severity=severity,
            summary=summary,
            anomaly_score=round(score, 4),
            prediction_label=pred,
            observed_metric_values=meta["observed_values"],
            model_metadata=model_meta,
            explanation=explanation,
        )

    def detect(
        self,
        samples: Sequence[Union[MetricSample, Any, Dict[str, Any]]],
    ) -> List[MLDetectionFinding]:
        """
        Evaluate a sequence of metric samples and return all detected multivariate findings.
        
        Maintains chronological order of input observations.
        """
        if not self._is_fitted:
            raise RuntimeError("IsolationForestDetector must be fitted before running detect()")
        if not samples:
            return []

        X_rows: List[List[float]] = []
        metas: List[Dict[str, Any]] = []

        for sample in samples:
            features, meta = self._extract_features(sample)
            X_rows.append(features)
            metas.append(meta)

        X = np.array(X_rows, dtype=np.float64)
        preds = self.model.predict(X)
        scores = self.model.decision_function(X)

        findings: List[MLDetectionFinding] = []
        for i, (pred, score, meta) in enumerate(zip(preds, scores, metas)):
            if pred == -1:
                severity = "critical" if score < -0.15 else "warning"
                summary = (
                    f"Multivariate Anomaly Detected by IsolationForest on {meta['service']} "
                    f"(score: {score:.4f})"
                )
                model_meta = {
                    "n_estimators": self.n_estimators,
                    "contamination": self.contamination,
                    "random_state": self.random_state,
                    "feature_names": list(FEATURE_NAMES),
                    "training_sample_count": self._training_sample_count,
                }
                explanation = (
                    f"IsolationForest classified this observation as an outlier based on its combined "
                    f"numerical telemetry features ({', '.join(FEATURE_NAMES)}). The recorded decision "
                    f"score was {score:.4f} (negative decision score indicates isolation in anomalous subspace)."
                )
                findings.append(
                    MLDetectionFinding(
                        service=meta["service"],
                        timestamp=meta["timestamp"] or datetime.now(),
                        metric_id=meta["id"],
                        detector_name=self.name,
                        detector_version=self.version,
                        severity=severity,
                        summary=summary,
                        anomaly_score=round(float(score), 4),
                        prediction_label=int(pred),
                        observed_metric_values=meta["observed_values"],
                        model_metadata=model_meta,
                        explanation=explanation,
                    )
                )

        return findings
