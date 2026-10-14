import { HealthResponse, MetricListResponse } from '../types/metrics';
import {
  DemoGenerateRequest,
  DemoGenerateResponse,
  DetectionRunRequest,
  DetectionRunResponse,
  IncidentListResponse,
  IncidentResponse,
} from '../types/incidents';

// Resolves backend API base URL from Vite environment.
// Honors empty string "" for same-origin relative URLs in Docker/Nginx production,
// falling back to local development server "http://localhost:8000" if undefined.
const rawApiBase = import.meta.env.VITE_API_BASE_URL;
const API_BASE_URL =
  typeof rawApiBase === 'string' ? rawApiBase.trim() : 'http://localhost:8000';

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/**
 * Fetch backend health and readiness status.
 * Target: GET /health
 */
export async function fetchHealth(): Promise<HealthResponse> {
  const url = `${API_BASE_URL}/health`;
  try {
    const response = await fetch(url, {
      headers: {
        Accept: 'application/json',
      },
    });

    if (!response.ok) {
      throw new ApiError(
        `Health check failed with HTTP ${response.status}: ${response.statusText}`,
        response.status
      );
    }

    return (await response.json()) as HealthResponse;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new Error(
      `Network error connecting to backend at ${url}. Ensure the FastAPI server is running.`,
      { cause: error }
    );
  }
}

/**
 * Fetch reproducible synthetic telemetry samples.
 * Target: GET /api/metrics?service={service}&limit={limit}
 */
export async function fetchMetrics(
  service: string = 'demo-api',
  limit: number = 50
): Promise<MetricListResponse> {
  const queryParams = new URLSearchParams({
    service,
    limit: limit.toString(),
  });
  const url = `${API_BASE_URL}/api/metrics?${queryParams.toString()}`;

  try {
    const response = await fetch(url, {
      headers: {
        Accept: 'application/json',
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      let detailedMessage = `Metrics request failed with HTTP ${response.status}`;
      try {
        const errorJson = JSON.parse(errorText);
        if (errorJson.detail) {
          detailedMessage += `: ${JSON.stringify(errorJson.detail)}`;
        }
      } catch {
        detailedMessage += `: ${errorText}`;
      }
      throw new ApiError(detailedMessage, response.status);
    }

    return (await response.json()) as MetricListResponse;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new Error(
      `Network error connecting to metrics API at ${url}. Ensure the FastAPI server is running.`,
      { cause: error }
    );
  }
}

/**
 * Trigger synthetic demo telemetry generation.
 * Target: POST /api/demo/generate
 */
export async function generateDemoData(
  request: DemoGenerateRequest = {}
): Promise<DemoGenerateResponse> {
  const url = `${API_BASE_URL}/api/demo/generate`;
  const body = {
    service: request.service || 'demo-api',
    total_samples: request.total_samples ?? 100,
    seed: request.seed ?? 42,
    latency_spike_count: request.latency_spike_count ?? 3,
    error_spike_count: request.error_spike_count ?? 2,
    replace_existing: request.replace_existing ?? true,
  };

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new ApiError(`Demo generation failed with HTTP ${response.status}: ${errorText}`, response.status);
    }

    return (await response.json()) as DemoGenerateResponse;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new Error(
      `Network error calling demo generate at ${url}: ${(error as Error).message}`,
      { cause: error }
    );
  }
}

/**
 * Trigger an anomaly detection run.
 * Target: POST /api/detection/run
 */
export async function runDetection(
  request: DetectionRunRequest
): Promise<DetectionRunResponse> {
  const url = `${API_BASE_URL}/api/detection/run`;
  const body = {
    service: request.service || 'demo-api',
    detector: request.detector,
    limit: request.limit ?? 100,
  };

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new ApiError(`Detection run failed with HTTP ${response.status}: ${errorText}`, response.status);
    }

    return (await response.json()) as DetectionRunResponse;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new Error(
      `Network error calling detection run at ${url}: ${(error as Error).message}`,
      { cause: error }
    );
  }
}

/**
 * Fetch persisted incidents.
 * Target: GET /api/incidents?service={service}&status={status}&detector_name={detector_name}&limit={limit}
 */
export async function fetchIncidents(
  service: string = 'demo-api',
  limit: number = 50,
  status?: string,
  detector_name?: string
): Promise<IncidentListResponse> {
  const queryParams = new URLSearchParams();
  if (service) queryParams.set('service', service);
  queryParams.set('limit', limit.toString());
  if (status) queryParams.set('status', status);
  if (detector_name) queryParams.set('detector_name', detector_name);

  const url = `${API_BASE_URL}/api/incidents?${queryParams.toString()}`;

  try {
    const response = await fetch(url, {
      headers: {
        Accept: 'application/json',
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new ApiError(`Incidents request failed with HTTP ${response.status}: ${errorText}`, response.status);
    }

    return (await response.json()) as IncidentListResponse;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new Error(
      `Network error connecting to incidents API at ${url}: ${(error as Error).message}`,
      { cause: error }
    );
  }
}

/**
 * Fetch complete evidence detail for a single incident by UUID.
 * Target: GET /api/incidents/{id}
 */
export async function fetchIncidentById(id: string): Promise<IncidentResponse> {
  const url = `${API_BASE_URL}/api/incidents/${encodeURIComponent(id)}`;

  try {
    const response = await fetch(url, {
      headers: {
        Accept: 'application/json',
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new ApiError(`Incident lookup failed with HTTP ${response.status}: ${errorText}`, response.status);
    }

    return (await response.json()) as IncidentResponse;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new Error(
      `Network error fetching incident at ${url}: ${(error as Error).message}`,
      { cause: error }
    );
  }
}
