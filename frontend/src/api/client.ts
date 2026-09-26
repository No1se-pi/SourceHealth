import type { components } from './generated';

export type Repository = components['schemas']['RepositorySummary'];
export type RepositoryDetails = components['schemas']['RepositoryDetails'];
export type RepositoryPage = components['schemas']['RepositoryPage'];
export type Analysis = components['schemas']['AnalysisDetails'];
export type AnalysisSummary = components['schemas']['AnalysisSummary'];
export type AnalysisPage = components['schemas']['AnalysisPage'];
export type CategoryScore = components['schemas']['CategoryScoreDTO'];
export type DataAvailability = components['schemas']['DataAvailability'];
export type RunStatus = components['schemas']['RunStatus'];
export type Category = components['schemas']['Category'];
export type Recommendation = components['schemas']['RecommendationDTO'];
export type AnalyzerResult = components['schemas']['AnalyzerResultDTO'];
export type Evidence = components['schemas']['EvidenceDTO'];
export type User = components['schemas']['UserDTO'];
export type ErrorResponse = components['schemas']['ErrorResponse'];
export type Profile = components['schemas']['ProfileDTO'];
export type ProfileRepository = components['schemas']['ProfileRepositoryDTO'];
export type ConnectedRepositories = components['schemas']['ConnectedRepositoriesDTO'];

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
  if (response.status === 204 || response.headers.get('content-length') === '0') {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  sourcecraftStatus: () => request<components['schemas']['SourceCraftConnectionDTO']>('/sourcecraft/connection'),
  connectSourcecraft: (pat: string, retentionSeconds = 1800) => request<components['schemas']['SourceCraftConnectionDTO']>('/sourcecraft/connection', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pat, retention_seconds: retentionSeconds }),
  }),
  disconnectSourcecraft: () => request<void>('/sourcecraft/connection', { method: 'DELETE' }),
  updateSourcecraftRetention: (retentionSeconds: number) => request<components['schemas']['SourceCraftConnectionDTO']>('/sourcecraft/connection', {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ retention_seconds: retentionSeconds }),
  }),
  connectedRepositories: (organization: string) => request<components['schemas']['ConnectedRepositoriesDTO']>(
    `/sourcecraft/repositories?${new URLSearchParams({ organization })}`),
  mySourcecraftRepositories: (pageToken = '') => request<ConnectedRepositories>(
    `/sourcecraft/me/repositories?${new URLSearchParams(pageToken ? { page_token: pageToken } : {})}`),
  profile: () => request<Profile>('/profile'),
  trackRepository: (repositoryId: string) => request<ProfileRepository>('/profile/repositories', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ repository_id: repositoryId }),
  }),
  updateTrackedRepository: (repositoryId: string, refreshPreference: string, usePat: boolean) =>
    request<ProfileRepository>(`/profile/repositories/${encodeURIComponent(repositoryId)}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_preference: refreshPreference, use_pat_for_scheduled_analysis: usePat }),
    }),
  untrackRepository: (repositoryId: string) => request<void>(
    `/profile/repositories/${encodeURIComponent(repositoryId)}`, { method: 'DELETE' }),
  importRepository: (url: string) => request<RepositoryDetails>('/repositories', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }),
  }),
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
  latestAnalysis: (repositoryId: string) =>
    request<AnalysisSummary>(`/repositories/${encodeURIComponent(repositoryId)}/analyses/latest`),
  analysisHistory: (repositoryId: string) =>
    request<AnalysisPage>(`/repositories/${encodeURIComponent(repositoryId)}/analyses?limit=10&offset=0`),
  analysis: (id: string) =>
    request<Analysis>(`/analyses/${encodeURIComponent(id)}`),
  start: (id: string) =>
    request<AnalysisSummary>(`/repositories/${encodeURIComponent(id)}/analyses`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ force_refresh: false }),
    }),
  logout: () =>
    request<void>('/auth/logout', {
      method: 'POST',
    }),
  me: () => request<User>('/me'),
};
