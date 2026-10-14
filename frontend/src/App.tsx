import React, { useState, useEffect, useCallback } from 'react';
import {
  fetchHealth,
  fetchMetrics,
  generateDemoData,
  runDetection,
  fetchIncidents,
} from './api/client';
import { HealthResponse, MetricListResponse } from './types/metrics';
import { IncidentListResponse, IncidentResponse } from './types/incidents';

export const App: React.FC = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [metricsData, setMetricsData] = useState<MetricListResponse | null>(null);
  const [incidentsData, setIncidentsData] = useState<IncidentListResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isStale, setIsStale] = useState<boolean>(false);
  const [lastFetched, setLastFetched] = useState<Date | null>(null);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);
  const [selectedIncident, setSelectedIncident] = useState<IncidentResponse | null>(null);

  const selectedService = 'demo-api';

  // Central data loader fetching health status, metrics, and persisted incidents
  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const [healthRes, metricsRes, incidentsRes] = await Promise.all([
        fetchHealth(),
        fetchMetrics(selectedService, 50),
        fetchIncidents(selectedService, 50),
      ]);
      setHealth(healthRes);
      setMetricsData(metricsRes);
      setIncidentsData(incidentsRes);
      setIsStale(false);
      setLastFetched(new Date());
    } catch (err: unknown) {
      const errorMessage =
        err instanceof Error ? err.message : 'Unknown error connecting to backend.';
      setError(errorMessage);
      setHealth(null);
      // Mark existing data as stale so it is never presented as current
      setIsStale(true);
    } finally {
      setIsLoading(false);
    }
  }, [selectedService]);

  // Fetch on initial mount
  useEffect(() => {
    let ignore = false;
    Promise.resolve().then(() => {
      if (!ignore) {
        void loadData();
      }
    });
    return () => {
      ignore = true;
    };
  }, [loadData]);

  // 1. Generate Synthetic Demo Data
  const handleGenerateData = async () => {
    if (actionLoading) return;
    setActionLoading('generate');
    setError(null);
    try {
      const res = await generateDemoData({
        service: selectedService,
        total_samples: 100,
        seed: 42,
        latency_spike_count: 3,
        error_spike_count: 2,
        replace_existing: true,
      });
      setFeedbackMessage(
        `Successfully generated and persisted ${res.total_samples} observations with ` +
        `${res.anomalies_injected} injected anomalies for '${res.service}'.`
      );
      await loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to generate demo telemetry.');
    } finally {
      setActionLoading(null);
    }
  };

  // 2. Run Threshold Detection
  const handleRunThreshold = async () => {
    if (actionLoading) return;
    setActionLoading('threshold');
    setError(null);
    try {
      const res = await runDetection({
        service: selectedService,
        detector: 'threshold_baseline',
        limit: 100,
      });
      setFeedbackMessage(
        `Threshold Detection completed on ${res.samples_analyzed} samples: ` +
        `${res.findings_count} findings, ${res.incidents_created} new incidents created ` +
        `(${res.incidents_already_existing} deduplicated).`
      );
      await loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to run threshold detection.');
    } finally {
      setActionLoading(null);
    }
  };

  // 3. Run IsolationForest Detection
  const handleRunIsolationForest = async () => {
    if (actionLoading) return;
    setActionLoading('isolation_forest');
    setError(null);
    try {
      const res = await runDetection({
        service: selectedService,
        detector: 'isolation_forest',
        limit: 100,
      });
      setFeedbackMessage(
        `IsolationForest Detection completed on ${res.samples_analyzed} samples: ` +
        `${res.findings_count} findings, ${res.incidents_created} new incidents created ` +
        `(${res.incidents_already_existing} deduplicated).`
      );
      await loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to run IsolationForest detection.');
    } finally {
      setActionLoading(null);
    }
  };

  // Telemetry summary computations
  const samples = metricsData?.data || [];
  const sampleCount = samples.length;

  const avgLatency =
    sampleCount > 0
      ? (samples.reduce((acc, s) => acc + s.latency_ms, 0) / sampleCount).toFixed(2)
      : '--';

  const avgErrorRate =
    sampleCount > 0
      ? (
          (samples.reduce((acc, s) => acc + s.error_rate, 0) / sampleCount) *
          100
        ).toFixed(2)
      : '--';

  const totalRequests =
    sampleCount > 0
      ? samples.reduce((acc, s) => acc + s.request_count, 0).toLocaleString()
      : '--';

  const avgCpu =
    sampleCount > 0
      ? (samples.reduce((acc, s) => acc + s.cpu_usage_pct, 0) / sampleCount).toFixed(1)
      : '--';

  const avgMemory =
    sampleCount > 0
      ? (samples.reduce((acc, s) => acc + s.memory_usage_pct, 0) / sampleCount).toFixed(1)
      : '--';

  // Incidents
  const incidents = incidentsData?.data || [];

  // Format ISO timestamp to explicit UTC string
  const formatUtcTimestamp = (isoString: string): string => {
    try {
      const dt = new Date(isoString);
      return dt.toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
    } catch {
      return isoString;
    }
  };

  return (
    <div className="dashboard-container">
      {/* Header & Navigation */}
      <header className="dashboard-header">
        <div className="brand-section">
          <div className="brand-logo">CS</div>
          <div>
            <h1 className="brand-title">CloudSentinel AI</h1>
            <p className="brand-subtitle">AI-Assisted Cloud Reliability Prototype</p>
          </div>
        </div>

        <div className="header-badges">
          {/* Prominent Synthetic Data Label */}
          <div
            className="badge badge-synthetic"
            title="All telemetry data is deterministically simulated"
          >
            <span className="badge-dot"></span>
            Synthetic Demo Telemetry
          </div>

          {/* Backend Connection Health Badge */}
          {isLoading && !health && !error ? (
            <div className="badge badge-health loading">
              <span className="badge-dot pulse"></span>
              Checking Backend...
            </div>
          ) : health ? (
            <div
              className="badge badge-health healthy"
              title={`Server Time: ${health.timestamp}`}
            >
              <span className="badge-dot"></span>
              Backend: Online ({health.service} v{health.version})
            </div>
          ) : (
            <div className="badge badge-health offline">
              <span className="badge-dot"></span>
              Backend: Offline
            </div>
          )}

          {/* Refresh / Retry Control */}
          <button
            className="btn btn-primary"
            onClick={loadData}
            disabled={isLoading || !!actionLoading}
            aria-label="Refresh telemetry and incident data"
          >
            {isLoading ? (
              <>
                <span className="spinner"></span>
                Loading...
              </>
            ) : (
              '↻ Refresh'
            )}
          </button>
        </div>
      </header>

      {/* Action Controls Toolbar */}
      <section className="controls-panel">
        <div className="controls-header">
          <div>
            <h2 className="controls-title">Anomaly Detection & Simulation Controls</h2>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
              Service: <strong>{selectedService}</strong>
            </span>
          </div>

          <div className="controls-actions">
            {/* Generate Synthetic Demo Data */}
            <button
              id="btn-generate-demo"
              className="btn btn-generate"
              onClick={handleGenerateData}
              disabled={isLoading || !!actionLoading}
              title="Generate 100 deterministic observations with 3 latency spikes and 2 error surges"
            >
              {actionLoading === 'generate' ? (
                <>
                  <span className="spinner"></span>
                  Generating...
                </>
              ) : (
                '⚡ Generate Synthetic Data'
              )}
            </button>

            {/* Run Threshold Detection */}
            <button
              id="btn-run-threshold"
              className="btn btn-threshold"
              onClick={handleRunThreshold}
              disabled={isLoading || !!actionLoading}
              title="Evaluate persisted metrics against latency (>150ms) and error rate (>5%) boundaries"
            >
              {actionLoading === 'threshold' ? (
                <>
                  <span className="spinner"></span>
                  Detecting...
                </>
              ) : (
                '📊 Run Threshold Detection'
              )}
            </button>

            {/* Run IsolationForest Detection */}
            <button
              id="btn-run-ml"
              className="btn btn-ml"
              onClick={handleRunIsolationForest}
              disabled={isLoading || !!actionLoading}
              title="Evaluate persisted metrics using multivariate IsolationForest fitted on clean reference baseline"
            >
              {actionLoading === 'isolation_forest' ? (
                <>
                  <span className="spinner"></span>
                  Analyzing...
                </>
              ) : (
                '🌲 Run IsolationForest Detection'
              )}
            </button>
          </div>
        </div>

        {/* Feedback Banner */}
        {feedbackMessage && (
          <div className="feedback-banner" role="status">
            <span>{feedbackMessage}</span>
            <button
              style={{
                background: 'none',
                border: 'none',
                color: '#a7f3d0',
                cursor: 'pointer',
                fontWeight: 700,
                fontSize: '1rem',
                marginLeft: '1rem',
              }}
              onClick={() => setFeedbackMessage(null)}
              aria-label="Dismiss message"
            >
              ✕
            </button>
          </div>
        )}
      </section>

      {/* Error State Banner / Stale Notice */}
      {error && (
        <div className="error-banner" role="alert">
          <div>
            <div className="error-title">
              {isStale && sampleCount > 0
                ? 'Backend Connection Lost — Displaying Stale Cached Telemetry'
                : 'Backend Connection Error'}
            </div>
            <div className="error-message">
              {error}
              {isStale && sampleCount > 0 && lastFetched && (
                <> (Cached data from {lastFetched.toLocaleTimeString()} is retained for reference, but is stale.)</>
              )}
            </div>
          </div>
          <button className="btn btn-retry" onClick={loadData}>
            Retry Connection
          </button>
        </div>
      )}

      {/* Metric KPI Overview Cards */}
      <section className="cards-grid">
        <div className="metric-card">
          <span className="card-title">Monitored Service</span>
          <span className="card-value">{metricsData?.service || selectedService}</span>
          <span className="card-footer">
            {sampleCount > 0
              ? `${sampleCount} samples (${metricsData?.order})${isStale ? ' [STALE]' : ''}`
              : 'Awaiting data'}
          </span>
        </div>

        <div className="metric-card">
          <span className="card-title">Average Latency</span>
          <span className="card-value">{avgLatency} ms</span>
          <span className="card-footer">
            {isStale ? 'Stale cached response' : 'Baseline round-trip response'}
          </span>
        </div>

        <div className="metric-card">
          <span className="card-title">Average Error Rate</span>
          <span className="card-value">{avgErrorRate}%</span>
          <span className="card-footer">
            {isStale ? 'Stale cached error proportion' : 'Proportion of failed requests'}
          </span>
        </div>

        <div className="metric-card">
          <span className="card-title">Total Requests</span>
          <span className="card-value">{totalRequests}</span>
          <span className="card-footer">
            {isStale ? 'Stale window volume' : 'Observed window volume'}
          </span>
        </div>

        <div className="metric-card">
          <span className="card-title">Avg CPU / Memory</span>
          <span className="card-value">
            {avgCpu !== '--' ? `${avgCpu}% / ${avgMemory}%` : '--'}
          </span>
          <span className="card-footer">
            {isStale ? 'Stale resource load' : 'Synthetic resource load'}
          </span>
        </div>
      </section>

      {/* Detected Incidents Section */}
      <section className="section-panel" id="incidents-panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">
              Detected Incidents & Anomaly Investigation
              <span
                style={{
                  fontSize: '0.8rem',
                  marginLeft: '0.75rem',
                  color: 'var(--text-secondary)',
                  fontWeight: 400,
                }}
              >
                ({incidents.length} recorded in SQLite)
              </span>
            </h2>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Factual anomaly findings generated by active detectors. Deduplicated per observation and detector.
            </span>
          </div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            Order: Newest First
          </span>
        </div>

        <div className="table-responsive">
          <table className="data-table" id="incidents-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Observation Time (UTC)</th>
                <th>Severity</th>
                <th>Detector</th>
                <th>Status</th>
                <th>Summary Headline</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {/* Empty State */}
              {incidents.length === 0 ? (
                <tr>
                  <td colSpan={7} className="state-box" id="incidents-empty-state">
                    No incidents recorded for this service. Click <strong>Run Threshold Detection</strong> or <strong>Run IsolationForest Detection</strong> above to evaluate persisted telemetry.
                  </td>
                </tr>
              ) : (
                /* Populated State */
                incidents.map((inc) => (
                  <tr key={inc.id} id={`incident-row-${inc.id}`}>
                    <td style={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>
                      {inc.id.substring(0, 8)}...
                    </td>
                    <td>{formatUtcTimestamp(inc.window_start)}</td>
                    <td>
                      <span
                        className={`badge badge-${
                          inc.severity === 'critical'
                            ? 'critical'
                            : inc.severity === 'warning'
                            ? 'warning'
                            : 'info'
                        }`}
                      >
                        {inc.severity.toUpperCase()}
                      </span>
                    </td>
                    <td>
                      <span className="badge badge-detector">
                        {inc.detector_name}
                      </span>
                    </td>
                    <td>
                      <span
                        className="badge badge-info"
                        style={{ textTransform: 'capitalize' }}
                      >
                        {inc.status}
                      </span>
                    </td>
                    <td>{inc.summary}</td>
                    <td>
                      <button
                        className="btn-evidence"
                        id={`btn-evidence-${inc.id}`}
                        onClick={() => setSelectedIncident(inc)}
                        aria-label={`View evidence for incident ${inc.id}`}
                      >
                        View Evidence
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Recent Observations Table Panel */}
      <section className="section-panel" id="observations-panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">
              Recent Telemetry Observations
              {isStale && sampleCount > 0 && (
                <span
                  className="badge badge-synthetic"
                  style={{
                    backgroundColor: '#7f1d1d',
                    borderColor: '#ef4444',
                    color: '#fecaca',
                    marginLeft: '0.75rem',
                  }}
                >
                  STALE CACHED DATA
                </span>
              )}
            </h2>
            {lastFetched && (
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Last fetched: {lastFetched.toLocaleTimeString()}{' '}
                {isStale ? '(backend disconnected)' : ''}
              </span>
            )}
          </div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            Order: Descending (Newest First)
          </span>
        </div>

        <div className="table-responsive">
          <table className="data-table" id="observations-table">
            <thead>
              <tr>
                <th>Timestamp (UTC)</th>
                <th>Service</th>
                <th>Latency</th>
                <th>Error Rate</th>
                <th>Requests</th>
                <th>CPU</th>
                <th>Memory</th>
                <th>Data Source</th>
              </tr>
            </thead>
            <tbody>
              {/* Loading State */}
              {isLoading && sampleCount === 0 && (
                <tr>
                  <td colSpan={8} className="state-box">
                    <span className="spinner" style={{ marginRight: '0.5rem' }}></span>
                    Loading synthetic telemetry from FastAPI backend...
                  </td>
                </tr>
              )}

              {/* Error State with no cached data */}
              {!isLoading && error && sampleCount === 0 && (
                <tr>
                  <td colSpan={8} className="state-box error">
                    Unable to display telemetry. Ensure FastAPI backend is running on port 8000.
                  </td>
                </tr>
              )}

              {/* Empty State */}
              {!isLoading && !error && sampleCount === 0 && (
                <tr>
                  <td colSpan={8} className="state-box">
                    No telemetry observations persisted for this service yet. Click &quot;Generate Synthetic Data&quot; to seed the database.
                  </td>
                </tr>
              )}

              {/* Populated State */}
              {samples.map((sample, idx) => (
                <tr key={sample.id ? `metric-${sample.id}` : `${sample.timestamp}-${idx}`}>
                  <td>{formatUtcTimestamp(sample.timestamp)}</td>
                  <td><strong>{sample.service}</strong></td>
                  <td>{sample.latency_ms.toFixed(2)} ms</td>
                  <td>{(sample.error_rate * 100).toFixed(2)}%</td>
                  <td>{sample.request_count}</td>
                  <td>{sample.cpu_usage_pct.toFixed(1)}%</td>
                  <td>{sample.memory_usage_pct.toFixed(1)}%</td>
                  <td>
                    <span className="tag-synthetic">SYNTHETIC</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Incident Detail & Numerical Evidence Modal */}
      {selectedIncident && (
        <div
          className="modal-backdrop"
          onClick={() => setSelectedIncident(null)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-incident-title"
        >
          <div
            className="modal-content"
            onClick={(e) => e.stopPropagation()}
            id="evidence-modal"
          >
            <div className="modal-header">
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                  <span
                    className={`badge badge-${
                      selectedIncident.severity === 'critical'
                        ? 'critical'
                        : selectedIncident.severity === 'warning'
                        ? 'warning'
                        : 'info'
                    }`}
                  >
                    {selectedIncident.severity.toUpperCase()}
                  </span>
                  <span className="badge badge-detector">
                    {selectedIncident.detector_name} v{selectedIncident.detector_version}
                  </span>
                </div>
                <h3 className="modal-title" id="modal-incident-title">
                  {selectedIncident.summary}
                </h3>
              </div>
              <button
                className="modal-close"
                id="modal-close-btn"
                onClick={() => setSelectedIncident(null)}
                aria-label="Close modal"
              >
                ✕
              </button>
            </div>

            {/* Metadata Section */}
            <div className="modal-section">
              <div className="modal-section-title">Incident Metadata</div>
              <div className="evidence-grid">
                <div className="evidence-card">
                  <span className="evidence-card-label">Incident UUID</span>
                  <span className="evidence-card-value" style={{ fontSize: '0.8rem', fontFamily: 'monospace' }}>
                    {selectedIncident.id}
                  </span>
                </div>
                <div className="evidence-card">
                  <span className="evidence-card-label">Service</span>
                  <span className="evidence-card-value">{selectedIncident.service}</span>
                </div>
                <div className="evidence-card">
                  <span className="evidence-card-label">Observation Time</span>
                  <span className="evidence-card-value" style={{ fontSize: '0.8rem' }}>
                    {formatUtcTimestamp(selectedIncident.window_start)}
                  </span>
                </div>
                <div className="evidence-card">
                  <span className="evidence-card-label">Status</span>
                  <span className="evidence-card-value" style={{ textTransform: 'capitalize' }}>
                    {selectedIncident.status}
                  </span>
                </div>
              </div>
            </div>

            {/* Factual Explanation */}
            <div className="modal-section">
              <div className="modal-section-title">Factual Finding Explanation</div>
              <div className="explanation-card" id="incident-explanation">
                {selectedIncident.explanation}
              </div>
            </div>

            {/* Observed Numerical Measurements */}
            <div className="modal-section">
              <div className="modal-section-title">Observed Numerical Metric Measurements</div>
              <div className="evidence-grid" id="observed-measurements-grid">
                <div className="evidence-card">
                  <span className="evidence-card-label">Latency</span>
                  <span className="evidence-card-value">
                    {selectedIncident.observed_metric_evidence.latency_ms?.toFixed(2)} ms
                  </span>
                </div>
                <div className="evidence-card">
                  <span className="evidence-card-label">Error Rate</span>
                  <span className="evidence-card-value">
                    {((selectedIncident.observed_metric_evidence.error_rate || 0) * 100).toFixed(2)}%
                  </span>
                </div>
                <div className="evidence-card">
                  <span className="evidence-card-label">Request Count</span>
                  <span className="evidence-card-value">
                    {selectedIncident.observed_metric_evidence.request_count}
                  </span>
                </div>
                <div className="evidence-card">
                  <span className="evidence-card-label">CPU Usage</span>
                  <span className="evidence-card-value">
                    {selectedIncident.observed_metric_evidence.cpu_usage_pct?.toFixed(1)}%
                  </span>
                </div>
                <div className="evidence-card">
                  <span className="evidence-card-label">Memory Usage</span>
                  <span className="evidence-card-value">
                    {selectedIncident.observed_metric_evidence.memory_usage_pct?.toFixed(1)}%
                  </span>
                </div>
              </div>
            </div>

            {/* Baseline / Detector Evidence */}
            <div className="modal-section">
              <div className="modal-section-title">Detector & Baseline Evidence</div>
              {selectedIncident.detector_name === 'threshold_baseline' && (
                <div className="evidence-card" style={{ padding: '0.85rem' }}>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                    Configured Rule Boundaries:
                  </div>
                  <pre style={{ fontSize: '0.78rem', color: '#93c5fd', overflowX: 'auto', margin: 0 }}>
                    {JSON.stringify(selectedIncident.baseline_evidence, null, 2)}
                  </pre>
                </div>
              )}

              {selectedIncident.detector_name === 'isolation_forest' && (
                <div className="evidence-grid">
                  <div className="evidence-card">
                    <span className="evidence-card-label">Decision Score</span>
                    <span className="evidence-card-value" style={{ color: '#f87171' }}>
                      {selectedIncident.baseline_evidence.anomaly_score?.toFixed(4)}
                    </span>
                    <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                      Negative score indicates anomalous subspace isolation
                    </span>
                  </div>
                  <div className="evidence-card">
                    <span className="evidence-card-label">Classification Label</span>
                    <span className="evidence-card-value">
                      {String(selectedIncident.baseline_evidence.prediction_label ?? -1)} (Outlier)
                    </span>
                  </div>
                  <div className="evidence-card">
                    <span className="evidence-card-label">Trees / Contamination</span>
                    <span className="evidence-card-value">
                      {selectedIncident.baseline_evidence.model_metadata?.n_estimators || 100} /{' '}
                      {selectedIncident.baseline_evidence.model_metadata?.contamination || 0.05}
                    </span>
                  </div>
                  <div className="evidence-card">
                    <span className="evidence-card-label">Reference Training Size</span>
                    <span className="evidence-card-value">
                      {selectedIncident.baseline_evidence.model_metadata?.training_sample_count || 100} normal samples
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Evidence Integrity & Anti-Speculation Disclaimer */}
            <div className="disclaimer-card">
              <strong>Evidence Integrity & Scientific Transparency:</strong> This incident record stores an immutable factual snapshot of observed telemetry measurements and detector parameters. Anomaly detection identifies statistical outlier conditions and does NOT constitute a diagnosed root cause.
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default App;
