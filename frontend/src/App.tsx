import React from 'react';

export const App: React.FC = () => {
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
          <div className="badge badge-synthetic">
            <span className="badge-dot"></span>
            Synthetic Demo Telemetry
          </div>
          <div className="badge badge-health healthy">
            <span className="badge-dot"></span>
            Backend: Ready (Skeleton)
          </div>
        </div>
      </header>

      {/* Milestone 3 Skeleton Notice */}
      <div className="skeleton-notice">
        <strong>Milestone 3 Active:</strong> Frontend skeleton initialized. HTTP client and schema types are verified. Full live state hooks and auto-refresh will connect in Milestone 4.
      </div>

      {/* Metric KPI Overview Cards Placeholder */}
      <section className="cards-grid">
        <div className="metric-card">
          <span className="card-title">Monitored Service</span>
          <span className="card-value">demo-api</span>
          <span className="card-footer">Target service workload</span>
        </div>

        <div className="metric-card">
          <span className="card-title">Average Latency</span>
          <span className="card-value">-- ms</span>
          <span className="card-footer">Pending Milestone 4 telemetry hook</span>
        </div>

        <div className="metric-card">
          <span className="card-title">Error Rate</span>
          <span className="card-value">-- %</span>
          <span className="card-footer">Pending Milestone 4 telemetry hook</span>
        </div>

        <div className="metric-card">
          <span className="card-title">Total Requests</span>
          <span className="card-value">--</span>
          <span className="card-footer">Pending Milestone 4 telemetry hook</span>
        </div>
      </section>

      {/* Recent Observations Table Placeholder */}
      <section className="section-panel">
        <div className="panel-header">
          <h2 className="panel-title">Recent Telemetry Observations</h2>
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
                <th>Latency (ms)</th>
                <th>Error Rate</th>
                <th>Requests</th>
                <th>CPU %</th>
                <th>Memory %</th>
                <th>Data Source</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td colSpan={8} className="state-box">
                  Telemetry observations table skeleton initialized. Connect live data in Milestone 4.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};

export default App;
