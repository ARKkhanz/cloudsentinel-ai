/**
 * Type definitions matching backend FastAPI / Pydantic schemas.
 */

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  timestamp: string;
}

export interface MetricSample {
  service: string;
  timestamp: string;
  latency_ms: number;
  error_rate: number;
  request_count: number;
  cpu_usage_pct: number;
  memory_usage_pct: number;
  is_synthetic: boolean;
}

export interface MetricListResponse {
  service: string;
  total_samples: number;
  order: string;
  is_synthetic: boolean;
  data: MetricSample[];
}
