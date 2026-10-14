/**
 * TypeScript types matching backend detection and incident schemas.
 */

export interface DemoGenerateRequest {
  service?: string;
  total_samples?: number;
  seed?: number;
  latency_spike_count?: number;
  error_spike_count?: number;
  replace_existing?: boolean;
}

export interface GroundTruthAnomaly {
  sample_index: number;
  timestamp: string;
  anomaly_type: string;
  injected_fields: Record<string, number>;
  description: string;
}

export interface DemoGenerateResponse {
  status: string;
  service: string;
  total_samples: number;
  seed: number;
  is_synthetic: boolean;
  anomalies_injected: number;
  anomaly_types: string[];
  injected_anomalies: GroundTruthAnomaly[];
  generation_policy: string;
  time_range_start: string;
  time_range_end: string;
  created_at: string;
}

export interface DetectionRunRequest {
  service?: string;
  detector: 'threshold_baseline' | 'isolation_forest';
  limit?: number;
}

export interface DetectionRunResponse {
  status: string;
  service: string;
  detector_name: string;
  detector_version: string;
  samples_analyzed: number;
  findings_count: number;
  incidents_created: number;
  incidents_already_existing: number;
  created_incident_ids: string[];
  run_timestamp: string;
  detector_metadata: Record<string, unknown>;
}

export interface MLModelMetadata {
  n_estimators?: number;
  contamination?: number;
  training_sample_count?: number;
  random_state?: number;
  feature_names?: string[];
  [key: string]: unknown;
}

export interface BaselineEvidence {
  anomaly_score?: number;
  prediction_label?: number | string;
  model_metadata?: MLModelMetadata;
  triggered_conditions?: string[];
  thresholds?: Record<string, number>;
  [key: string]: unknown;
}

export interface IncidentResponse {
  id: string;
  service: string;
  created_at: string;
  severity: 'critical' | 'warning' | 'info';
  status: 'open' | 'investigating' | 'resolved';
  detector_name: string;
  detector_version: string;
  summary: string;
  explanation: string;
  observed_metric_evidence: Record<string, number>;
  baseline_evidence: BaselineEvidence;
  window_start: string;
  window_end: string;
  metric_sample_id?: number | null;
  dedup_key?: string | null;
}

export interface IncidentListResponse {
  service?: string | null;
  total: number;
  limit: number;
  data: IncidentResponse[];
}
