import type { components } from './generated';

export type Repository = components['schemas']['RepositorySummary'];
export type RepositoryDetails = components['schemas']['RepositoryDetails'];
export type RepositoryPage = components['schemas']['RepositoryPage'];
export type Analysis = components['schemas']['AnalysisDetails'];
export type AnalysisSummary = components['schemas']['AnalysisSummary'];
export type CategoryScore = components['schemas']['CategoryScoreDTO'];
export type DataAvailability = components['schemas']['DataAvailability'];
export type RunStatus = components['schemas']['RunStatus'];
export type Category = components['schemas']['Category'];
export type Recommendation = components['schemas']['RecommendationDTO'];
export type User = components['schemas']['UserDTO'];
export type ErrorResponse = components['schemas']['ErrorResponse'];

export class ApiError extends Error {
  constructor(
    public code: string,
    public status: number,
    public requestId: string,
  ) {
    super(code);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    credentials: 'same-origin',
    ...options,
  });
  if (!response.ok) {
    const error = (await response.json().catch(() => ({}))) as Partial<ErrorResponse>;
    throw new ApiError(
      error.code ?? 'request_failed',
      response.status,
      error.request_id ?? '',
    );
  }
  return response.json() as Promise<T>;
}

export const api = {
  repositories: (offset = 0, sort = 'health_score', language = '') =>
    request<RepositoryPage>(
      `/repositories?${new URLSearchParams({
        offset: String(offset),
        sort,
        ...(language ? { language } : {}),
      })}`,
    ),
  repository: (id: string) =>
    request<RepositoryDetails>(`/repositories/${encodeURIComponent(id)}`),
  analysis: (id: string) =>
    request<Analysis>(`/analyses/${encodeURIComponent(id)}`),
  start: (id: string) =>
    request<AnalysisSummary>(`/repositories/${encodeURIComponent(id)}/analyses`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ force_refresh: false }),
    }),
  me: () => request<User>('/me'),
};
