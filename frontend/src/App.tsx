import React, { useState, useEffect, useCallback } from 'react';
import { fetchHealth, fetchMetrics } from './api/client';
import { HealthResponse, MetricListResponse } from './types/metrics';

export const App: React.FC = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [metricsData, setMetricsData] = useState<MetricListResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastFetched, setLastFetched] = useState<Date | null>(null);

  // Central data loader fetching health status and recent synthetic metrics
  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const [healthRes, metricsRes] = await Promise.all([
        fetchHealth(),
        fetchMetrics('demo-api', 50),
      ]);
      setHealth(healthRes);
      setMetricsData(metricsRes);
      setLastFetched(new Date());
    } catch (err: unknown) {
      const errorMessage =
        err instanceof Error ? err.message : 'Unknown error connecting to backend.';
      setError(errorMessage);
      setHealth(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Fetch on initial mount
  useEffect(() => {
    loadData();
  }, [loadData]);

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
          <div className="badge badge-synthetic" title="All telemetry data is deterministically simulated">
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
            disabled={isLoading}
            aria-label="Refresh telemetry data"
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

      {/* Error State Banner */}
      {error && (
        <div className="error-banner" role="alert">
          <div>
            <div className="error-title">Backend Connection Error</div>
            <div className="error-message">{error}</div>
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
          <span className="card-value">{metricsData?.service || 'demo-api'}</span>
          <span className="card-footer">
            {sampleCount > 0 ? `${sampleCount} samples (${metricsData?.order})` : 'Awaiting data'}
          </span>
        </div>

        <div className="metric-card">
          <span className="card-title">Average Latency</span>
          <span className="card-value">{avgLatency} ms</span>
          <span className="card-footer">Baseline round-trip response</span>
        </div>

        <div className="metric-card">
          <span className="card-title">Average Error Rate</span>
          <span className="card-value">{avgErrorRate}%</span>
          <span className="card-footer">Proportion of failed requests</span>
        </div>

        <div className="metric-card">
          <span className="card-title">Total Requests</span>
          <span className="card-value">{totalRequests}</span>
          <span className="card-footer">Observed window volume</span>
        </div>

        <div className="metric-card">
          <span className="card-title">Avg CPU / Memory</span>
          <span className="card-value">
            {avgCpu}% / {avgMemory}%
          </span>
          <span className="card-footer">Synthetic resource load</span>
        </div>
      </section>

      {/* Recent Observations Table Panel */}
      <section className="section-panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Recent Telemetry Observations</h2>
            {lastFetched && (
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Last fetched: {lastFetched.toLocaleTimeString()}
              </span>
            )}
          </div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            Order: Descending (Newest First)
          </span>
        </div>

        <div className="table-responsive">
          <table className="data-table">
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
                    Loading real-time telemetry from FastAPI backend...
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
                    No telemetry observations returned for this service.
                  </td>
                </tr>
              )}

              {/* Populated State */}
              {samples.map((sample, idx) => (
                <tr key={`${sample.timestamp}-${idx}`}>
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
    </div>
  );
};

export default App;
