import { HealthResponse, MetricListResponse } from '../types/metrics';

// Resolves backend API base URL from Vite environment with local fallback
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.trim() || 'http://localhost:8000';

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
      `Network error connecting to backend at ${url}. Ensure the FastAPI server is running.`
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
      `Network error connecting to metrics API at ${url}. Ensure the FastAPI server is running.`
    );
  }
}
