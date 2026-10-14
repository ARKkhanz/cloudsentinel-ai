# CloudSentinel AI — Reproducible Anomaly Detector Evaluation & Benchmark

## 1. Executive Summary

This document reports the reproducible benchmark and empirical evaluation of CloudSentinel AI's two implemented anomaly detection engines:
1. **Threshold Baseline Detector** (`ThresholdDetector`) — A transparent, deterministic rule-based statistical threshold engine.
2. **IsolationForest Multivariate Detector** (`IsolationForestDetector`) — An unsupervised machine learning ensemble utilizing random axis-aligned feature space partitioning.

The evaluation was executed using the repository's standalone reproducible benchmark script ([`evaluate_detectors.py`](file:///C:/Users/USER/.gemini/antigravity-ide/scratch/cloudsentinel-ai/backend/scripts/evaluate_detectors.py)) against held-out synthetic telemetry with mathematically decoupled ground-truth labels.

---

## 2. Reproduction Instructions

To reproduce these exact results in any local environment, run:

```bash
# From repository root with virtual environment active:
python backend/scripts/evaluate_detectors.py

# Or via Python module execution:
python -m backend.scripts.evaluate_detectors
```

Automated verification tests are integrated into the test suite:

```bash
pytest backend/tests/test_evaluation.py -v
```

---

## 3. Dataset & Experimental Methodology

### 3.1 Training and Evaluation Separation Policy
To avoid data snooping, target leakage, and circular evaluation, training and evaluation datasets are generated independently using disjoint random seeds:
- **Clean Training Baseline**: Seed `100`, `total_samples=100`, strictly **0** injected anomalies (`latency_spike_count=0`, `error_spike_count=0`).
- **Held-Out Evaluation Dataset**: Seed `42`, `total_samples=100`, with **5** injected anomalies (`latency_spike_count=3`, `error_spike_count=2`).

### 3.2 Ground-Truth Labeling & Zero-Leakage Architecture
- Ground-truth anomaly metadata is returned in a separate data structure (`GroundTruthAnomaly` dataclass) and mapped to binary labels $y \in \{0, 1\}^{100}$.
- Detectors receive **only** numerical telemetry measurements.
- Feature vectors strictly exclude:
  - Synthetic flags (`is_synthetic`)
  - Ground-truth anomaly labels (`is_anomaly`, `anomaly_type`)
  - Database row IDs (`id`)
  - Timestamps (`timestamp`)

### 3.3 Feature Matrix Definition
The multivariate feature vector $\mathbf{x} \in \mathbb{R}^5$ uses the canonical, immutable feature order defined in [`FEATURE_NAMES`](file:///C:/Users/USER/.gemini/antigravity-ide/scratch/cloudsentinel-ai/backend/app/detection/isolation_forest_detector.py):
1. `latency_ms` (float, ms)
2. `error_rate` (float, proportion [0.0, 1.0])
3. `cpu_usage_pct` (float, [0.0, 100.0])
4. `memory_usage_pct` (float, [0.0, 100.0])
5. `request_count` (float/int, count)

---

## 4. Detector Configurations

### 4.1 Threshold Baseline Detector
- **Latency Threshold**: $150.0\text{ ms}$ (Baseline $\mu = 42.0\text{ ms}, \sigma = 5.0\text{ ms}$; $z > 21.6$).
- **Error Rate Threshold**: $0.05$ (5.0%) (Baseline $\mu = 0.005, \sigma = 0.002$; $z > 22.5$).
- **Decision Rule**: Flag sample if `latency_ms > 150.0` OR `error_rate > 0.05`.

### 4.2 IsolationForest Detector
- **Implementation**: `sklearn.ensemble.IsolationForest`
- **Random Seed**: `random_state = 42`
- **Estimators**: `n_estimators = 100` trees
- **Contamination Prior**: `contamination = 0.05` (assumes top 5% most isolated samples are outliers)
- **Fitting Data**: 100 samples from clean reference baseline (Seed `100`).

---

## 5. Measured Evaluation Results

### 5.1 Comprehensive Metrics Comparison Table

| Metric / Property | Threshold Baseline | IsolationForest |
| :--- | :--- | :--- |
| **Algorithm Type** | Rule-Based Threshold (`statistical_threshold`) | Unsupervised Tree Ensemble (`isolation_forest`) |
| **Total Samples Evaluated ($N$)** | 100 | 100 |
| **Ground-Truth Anomalies ($P$)** | 5 | 5 |
| **Ground-Truth Normal ($N$)** | 95 | 95 |
| **Total Predicted Anomalies** | 5 | 5 |
| **True Positives (TP)** | **5** | **4** |
| **False Positives (FP)** | **0** | **1** |
| **True Negatives (TN)** | **95** | **94** |
| **False Negatives (FN)** | **0** | **1** |
| **Precision** | **1.0000 (100.0%)** | **0.8000 (80.0%)** |
| **Recall** | **1.0000 (100.0%)** | **0.8000 (80.0%)** |
| **F1 Score** | **1.0000** | **0.8000** |
| **False-Positive Rate (FPR)** | **0.0000 (0.00%)** | **0.0105 (1.05%)** |

### 5.2 Mathematical Formulation
- $\text{Precision} = \frac{\text{TP}}{\text{TP} + \text{FP}} = \frac{4}{4 + 1} = 0.8000$ (IsolationForest)
- $\text{Recall} = \frac{\text{TP}}{\text{TP} + \text{FN}} = \frac{4}{4 + 1} = 0.8000$ (IsolationForest)
- $\text{F1} = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}} = 2 \times \frac{0.8 \times 0.8}{1.6} = 0.8000$
- $\text{FPR} = \frac{\text{FP}}{\text{FP} + \text{TN}} = \frac{1}{1 + 94} = \frac{1}{95} \approx 0.0105$
- $\text{Sum Check}: \text{TP} + \text{FP} + \text{TN} + \text{FN} = 4 + 1 + 94 + 1 = 100$

### 5.3 Confusion Matrices

#### Threshold Baseline
$$\begin{pmatrix} \text{TN}=95 & \text{FP}=0 \\ \text{FN}=0 & \text{TP}=5 \end{pmatrix}$$

#### IsolationForest Detector
$$\begin{pmatrix} \text{TN}=94 & \text{FP}=1 \\ \text{FN}=1 & \text{TP}=4 \end{pmatrix}$$

---

## 6. Qualitative Anomaly Analysis

### 6.1 Ground-Truth Anomaly Instances
| Index | UTC Timestamp | Anomaly Type | Injected Value | Baseline Mean | Detected By Threshold? | Detected By IsolationForest? |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: |
| **13** | 2026-10-14 11:47:00 | `latency_spike` | 333.24 ms | 42.0 ms | **YES (TP)** | **YES (TP)** (score: -0.0364) |
| **24** | 2026-10-14 11:36:00 | `latency_spike` | 503.70 ms | 42.0 ms | **YES (TP)** | **YES (TP)** (score: -0.0445) |
| **40** | 2026-10-14 11:20:00 | `error_rate_spike` | 24.63% | 0.5% | **YES (TP)** | **YES (TP)** (score: -0.0373) |
| **43** | 2026-10-14 11:17:00 | `error_rate_spike` | 16.17% | 0.5% | **YES (TP)** | **YES (TP)** (score: -0.0011) |
| **45** | 2026-10-14 11:15:00 | `latency_spike` | 421.57 ms | 42.0 ms | **YES (TP)** | **NO (FN)** (ranked 6th) |

### 6.2 Analysis of IsolationForest False Positive (Index 28)
- **Observed Metrics**:
  - `latency_ms`: 31.88 ms (baseline $\mu=42.0\text{ ms}$)
  - `error_rate`: 0.0018 (0.18%, baseline $\mu=0.5\%$)
  - `request_count`: 152.0 (baseline $\mu=130.0$)
  - `cpu_usage_pct`: 25.46% (baseline $\mu=28.0\%$)
  - `memory_usage_pct`: 42.83% (baseline $\mu=44.0\%$)
- **Anomaly Score**: `-0.0054`
- **Root Rationale**:
  In single-metric domain logic, Sample 28 represents healthy performance (exceptionally low latency and minimal error rate). However, IsolationForest does not evaluate operational semantics; it evaluates geometric isolation density in 5-dimensional space. The co-occurrence of unusually low latency (31.88ms) with elevated request volume (152) placed Sample 28 in a sparsely populated subspace, causing trees to isolate it quickly. Because `contamination=0.05` forces the model to flag the top 5% outliers, Sample 28 was classified as an anomaly.

### 6.3 Analysis of IsolationForest False Negative (Index 45)
- **Observed Metrics**:
  - `latency_ms`: 421.57 ms (severe latency surge)
  - `error_rate`: 0.0049 (normal baseline)
  - `request_count`: 133.0 (normal baseline)
  - `cpu_usage_pct`: 71.50% (elevated)
  - `memory_usage_pct`: 43.39% (normal baseline)
- **Root Rationale**:
  With `contamination=0.05` on a 100-sample dataset, IsolationForest has an exact budget of $\lfloor 100 \times 0.05 \rfloor = 5$ predicted anomalies. Because Sample 28 occupied one of the five anomaly slots with score `-0.0054`, Sample 45 missed the cutoff and was classified as an inlier ($+1$).

---

## 7. Technical Interpretation & Academic Discussion

### 7.1 Why the Threshold Baseline Outperformed ML on this Benchmark
The threshold baseline achieved perfect Precision (1.0) and Recall (1.0). This is not evidence that threshold rules are universally superior to machine learning. Rather:
1. **Targeted Spike Injection**: The synthetic anomaly generator specifically injects massive univariate spikes (latency $320\text{–}520\text{ ms}$ vs $42\text{ ms}$ normal, error rate $15\text{–}35\%$ vs $0.5\%$ normal). These values lie $>20$ standard deviations above the baseline distribution.
2. **Explicit Prior Alignment**: The configured threshold boundaries ($150\text{ ms}$ and $5.0\%$) were intentionally engineered to lie far above normal variance and far below the injected surge magnitudes. A threshold rule will always excel when anomalies are large univariate shifts along the monitored dimensions.

### 7.2 Why IsolationForest Behaves Differently
1. **Multivariate Geometry vs Business Rules**: IsolationForest evaluates high-dimensional feature combinations without knowing what a metric "means." It treats a healthy-but-rare combination identically to a degraded-and-rare combination.
2. **Contamination is a Hyperparameter, Not Ground Truth**: Setting `contamination=0.05` asserts a modeling assumption that $5\%$ of points are outliers. It does not measure the actual ground-truth anomaly rate of the environment. If the true anomaly rate is $1\%$, `contamination=0.05` will inevitably produce false alarms; if the true rate is $15\%$, it will guarantee false negatives.
3. **Anomaly Score is NOT Outage Probability**: An anomaly score (e.g. $-0.0373$) represents path length in a random partitioning tree. It is not a calibrated posterior probability of service downtime, failure, or outage.
4. **Anomaly Detection is NOT Root Cause Diagnosis**: Neither detector proves root cause. A detector notes that an observed measurement or feature vector deviated from an expectation; it does not diagnose database deadlocks, network interface discards, GC pauses, or bad deployments.

---

## 8. Limitations & Scope Constraints

1. **Synthetic Telemetry**: Telemetry is generated deterministically from parameterized Gaussian and uniform distributions. It does not reproduce complex real-world production phenomena such as seasonal diurnal traffic patterns, multi-service cascade degradation, or bursty micro-outages.
2. **Sample Size**: 100 evaluation samples provides a clear pedagogical demonstration but has high sample variance ($1\text{ sample} = 1.0\%\text{ of total}$).
3. **Axis-Aligned Splits**: Standard IsolationForest uses axis-aligned orthogonal splits. Oblique hyperplanes or extended Isolation Forests would behave differently on rotated correlated subspaces.
4. **Static Thresholds**: Static threshold rules suffer from drift in production as service traffic patterns grow or change, requiring continuous retuning.

---

## 9. Environment & Dependencies

| Component | Version / Specification |
| :--- | :--- |
| **Python** | 3.11.9 (64-bit) |
| **Scikit-Learn** | 1.4.1+ |
| **NumPy** | 1.26.4+ |
| **Pydantic** | 2.6.4+ |
| **FastAPI** | 0.110.0+ |
| **SQLAlchemy** | 2.0.28+ |
| **Operating System** | Windows 11 Pro |
