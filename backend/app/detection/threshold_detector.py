from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

from backend.app.schemas.metrics import MetricSample


def _normalize_utc_timestamp(ts: Any) -> datetime:
    """Normalize input timestamp to timezone-aware UTC datetime. Rejects missing or non-datetime values."""
    if ts is None:
        raise ValueError("Missing required observation timestamp for detection finding")
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts)
        except Exception as exc:
            raise ValueError(f"Invalid timestamp format: {ts}") from exc
    if not isinstance(ts, datetime):
        raise TypeError(f"Timestamp must be a datetime or ISO string, got {type(ts).__name__}")
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


class ThresholdFinding(BaseModel):
    """
    Structured anomaly detection finding produced by the threshold baseline detector.
    
    Contains complete factual evidence of the breach without fabricating root causes,
    ready for future incident generation and auditability.
    """
    service: str = Field(..., description="Service identifier associated with the observation")
    timestamp: datetime = Field(..., description="UTC timestamp of the anomalous observation")
    metric_id: Optional[int] = Field(None, description="Database record primary key if persisted")
    detector_name: str = Field("threshold_baseline", description="Identifier of the detector algorithm")
    detector_version: str = Field("1.0.0", description="Version of the detector rule set")
    severity: str = Field(..., description="Severity level: 'critical' or 'warning'")
    summary: str = Field(..., description="Concise human-readable title of the breach")
    triggered_conditions: List[str] = Field(..., description="List of threshold rules breached")
    observed_metric_values: Dict[str, float] = Field(
        ...,
        description="Factual numerical metric measurements at time of detection",
    )
    threshold_values: Dict[str, float] = Field(
        ...,
        description="Configured threshold limits used during evaluation",
    )
    evidence: Dict[str, Any] = Field(
        ...,
        description="Structured comparison evidence detailing measurements vs thresholds",
    )
    explanation: str = Field(
        ...,
        description="Dynamic, factual explanation of the observed threshold breach",
    )


class ThresholdDetector:
    """
    Transparent, rule-based threshold baseline anomaly detector.
    
    Evaluates telemetry samples against configurable statistical boundaries.
    Operates strictly on numerical measurements—never accesses ground-truth anomaly
    labels, ensuring complete independence from synthetic generator metadata.
    
    Default Threshold Justification:
    - latency_threshold_ms = 150.0ms:
      Normal baseline has mean mu=42.0ms, sigma=5.0ms. A 150.0ms threshold is
      >21 standard deviations above normal baseline (z > 21), eliminating false
      alarms on normal traffic while reliably capturing synthetic spikes (320-520ms).
    - error_rate_threshold = 0.05 (5.0%):
      Normal baseline has mean mu=0.005 (0.5%), sigma=0.002. A 0.05 threshold is
      >22 standard deviations above baseline (z > 22), cleanly capturing synthetic
      surges (15-35%) without triggering on expected random baseline fluctuations.
    """

    def __init__(
        self,
        latency_threshold_ms: float = 150.0,
        error_rate_threshold: float = 0.05,
        name: str = "threshold_baseline",
        version: str = "1.0.0",
    ) -> None:
        if latency_threshold_ms <= 0:
            raise ValueError(f"latency_threshold_ms must be positive, got {latency_threshold_ms}")
        if not (0.0 <= error_rate_threshold <= 1.0):
            raise ValueError(
                f"error_rate_threshold must be a proportion between 0.0 and 1.0, got {error_rate_threshold}"
            )

        self.latency_threshold_ms = latency_threshold_ms
        self.error_rate_threshold = error_rate_threshold
        self.name = name
        self.version = version

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

    def _extract_metric_fields(self, sample: Union[MetricSample, Any, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Normalize and strictly validate sample input from Pydantic model, SQLAlchemy ORM model, or dictionary.
        Rejects missing required metrics and non-finite values (NaN, infinity).
        """
        required_fields = ("latency_ms", "error_rate", "request_count", "cpu_usage_pct", "memory_usage_pct")
        if isinstance(sample, dict):
            for field in required_fields:
                if field not in sample:
                    raise ValueError(f"Missing required numerical metric field: '{field}'")
            return {
                "service": sample.get("service", "unknown"),
                "timestamp": sample.get("timestamp"),
                "id": sample.get("id"),
                "latency_ms": self._validate_finite_number("latency_ms", sample["latency_ms"]),
                "error_rate": self._validate_finite_number("error_rate", sample["error_rate"]),
                "request_count": int(self._validate_finite_number("request_count", sample["request_count"])),
                "cpu_usage_pct": self._validate_finite_number("cpu_usage_pct", sample["cpu_usage_pct"]),
                "memory_usage_pct": self._validate_finite_number("memory_usage_pct", sample["memory_usage_pct"]),
            }
        else:
            for field in required_fields:
                if not hasattr(sample, field):
                    raise ValueError(f"Missing required numerical metric field: '{field}'")
            return {
                "service": getattr(sample, "service", "unknown"),
                "timestamp": getattr(sample, "timestamp", None),
                "id": getattr(sample, "id", None),
                "latency_ms": self._validate_finite_number("latency_ms", getattr(sample, "latency_ms")),
                "error_rate": self._validate_finite_number("error_rate", getattr(sample, "error_rate")),
                "request_count": int(self._validate_finite_number("request_count", getattr(sample, "request_count"))),
                "cpu_usage_pct": self._validate_finite_number("cpu_usage_pct", getattr(sample, "cpu_usage_pct")),
                "memory_usage_pct": self._validate_finite_number("memory_usage_pct", getattr(sample, "memory_usage_pct")),
            }

    def detect_sample(
        self,
        sample: Union[MetricSample, Any, Dict[str, Any]],
    ) -> Optional[ThresholdFinding]:
        """
        Evaluate a single telemetry sample against configured threshold boundaries.
        
        Returns:
            ThresholdFinding if one or more thresholds are strictly breached (>).
            None if all metrics are within configured thresholds.
            
        Duplicate Prevention Rule:
            If a single sample breaches both latency and error rate thresholds,
            a single consolidated finding is produced listing all triggered conditions,
            preventing duplicate alerts for the same timestamp.
        """
        fields = self._extract_metric_fields(sample)

        latency = fields["latency_ms"]
        error_rate = fields["error_rate"]

        is_latency_breach = latency > self.latency_threshold_ms
        is_error_breach = error_rate > self.error_rate_threshold

        if not is_latency_breach and not is_error_breach:
            return None

        triggered_conditions: List[str] = []
        explanation_parts: List[str] = []
        evidence: Dict[str, Any] = {
            "comparisons": {},
        }

        # 1. Evaluate Latency Breach
        if is_latency_breach:
            triggered_conditions.append("latency_ms_exceeded")
            excess_latency = round(latency - self.latency_threshold_ms, 2)
            evidence["comparisons"]["latency_ms"] = {
                "observed": latency,
                "threshold": self.latency_threshold_ms,
                "excess": excess_latency,
                "unit": "ms",
                "condition": "observed > threshold",
            }
            explanation_parts.append(
                f"Observed latency of {latency:.2f} ms exceeded the configured threshold of "
                f"{self.latency_threshold_ms:.1f} ms (+{excess_latency:.2f} ms excess)"
            )

        # 2. Evaluate Error Rate Breach
        if is_error_breach:
            triggered_conditions.append("error_rate_exceeded")
            excess_error_pct = round((error_rate - self.error_rate_threshold) * 100, 2)
            evidence["comparisons"]["error_rate"] = {
                "observed": error_rate,
                "threshold": self.error_rate_threshold,
                "excess_proportion": round(error_rate - self.error_rate_threshold, 4),
                "excess_percentage": f"+{excess_error_pct:.2f}%",
                "condition": "observed > threshold",
            }
            explanation_parts.append(
                f"Observed error rate of {error_rate * 100:.2f}% ({error_rate:.4f}) exceeded the "
                f"configured threshold of {self.error_rate_threshold * 100:.1f}% ({self.error_rate_threshold:.4f})"
            )

        # 3. Formulate Consolidated Summary and Severity
        if is_latency_breach and is_error_breach:
            severity = "critical"
            summary = f"Multiple Threshold Breaches on {fields['service']}"
            explanation = "Multiple thresholds breached: " + "; ".join(explanation_parts) + "."
        elif is_error_breach:
            severity = "critical"
            summary = f"High Error Rate on {fields['service']} ({error_rate * 100:.1f}%)"
            explanation = explanation_parts[0] + "."
        else:
            severity = "warning"
            summary = f"Elevated Latency on {fields['service']} ({latency:.1f} ms)"
            explanation = explanation_parts[0] + "."

        observed_values = {
            "latency_ms": latency,
            "error_rate": error_rate,
            "request_count": fields["request_count"],
            "cpu_usage_pct": fields["cpu_usage_pct"],
            "memory_usage_pct": fields["memory_usage_pct"],
        }
        threshold_values = {
            "latency_ms": self.latency_threshold_ms,
            "error_rate": self.error_rate_threshold,
        }

        obs_timestamp = _normalize_utc_timestamp(fields.get("timestamp"))

        return ThresholdFinding(
            service=fields["service"],
            timestamp=obs_timestamp,
            metric_id=fields["id"],
            detector_name=self.name,
            detector_version=self.version,
            severity=severity,
            summary=summary,
            triggered_conditions=triggered_conditions,
            observed_metric_values=observed_values,
            threshold_values=threshold_values,
            evidence=evidence,
            explanation=explanation,
        )

    def detect(
        self,
        samples: List[Union[MetricSample, Any, Dict[str, Any]]],
    ) -> List[ThresholdFinding]:
        """
        Evaluate a sequence of metric samples and return all detected findings.
        
        Preserves the chronological order of the input observations.
        """
        findings: List[ThresholdFinding] = []
        for sample in samples:
            finding = self.detect_sample(sample)
            if finding is not None:
                findings.append(finding)
        return findings
