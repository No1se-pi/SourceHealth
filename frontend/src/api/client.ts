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
export type CatalogStats = components['schemas']['CatalogStatsDTO'];
export type CategoryScoreMini = components['schemas']['CategoryScoreMiniDTO'];
export type HealthHistogramBucket = components['schemas']['HealthHistogramBucket'];
export type CompareResponse = components['schemas']['CompareResponse'];
export type Achievement = components['schemas']['AchievementDTO'];
export type ProfileSummary = components['schemas']['ProfileSummaryDTO'];
export type ShareInfo = components['schemas']['ShareInfo'];
export type IntegrityResponse = components['schemas']['IntegrityResponse'];
export type AISummaryMode = 'flash' | 'lite' | 'pro';
export type AISummaryDetail = 'brief' | 'detailed' | 'expert';
export interface GroundedStatement { text: string; evidence_refs: string[] }
export interface AISummaryResult {
  schema_version: 'ai-report-v2'; executive_summary: string;
  category_analysis: Array<{ category: string; score: number | null; availability: string;
    assessment: string; positive_findings: string[]; problems: string[];
    evidence_refs: string[] }>;
  strengths: GroundedStatement[];
  risks: GroundedStatement[];
  actions: Array<{ id: string; title: string; priority: number; why: string; action: string;
    implementation_steps: string[]; expected_result: string;
    recommendation_ids: string[]; evidence_refs: string[] }>;
  roadmap: { immediate: string[]; short_term: string[]; later: string[] };
  limitations: GroundedStatement[];
}
export interface AISummaryResponse {
  provider: 'yandex-ai-studio'; mode: AISummaryMode; detail: AISummaryDetail; model_name: string;
  grounding_validated: true; cached: boolean; summary: AISummaryResult;
}

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
  repositories: (
    paramsOrOffset: Record<string, string | number | boolean | undefined | null> | number = 0,
    options?: RequestInit,
  ) => {
    let qs = '';
    if (typeof paramsOrOffset === 'object' && paramsOrOffset !== null) {
      const cleanParams = Object.entries(paramsOrOffset).reduce<Record<string, string>>((acc, [k, v]) => {
        if (v !== undefined && v !== null && v !== '') {
          acc[k] = String(v);
        }
        return acc;
      }, {});
      qs = new URLSearchParams(cleanParams).toString();
    } else {
      qs = new URLSearchParams({
        offset: String(paramsOrOffset),
      }).toString();
    }
    return request<RepositoryPage>(`/repositories${qs ? `?${qs}` : ''}`, options);
  },
  catalogStats: (params: Record<string, string | number | boolean | undefined | null> = {}) => {
    const cleanParams = Object.entries(params).reduce<Record<string, string>>((acc, [k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        acc[k] = String(v);
      }
      return acc;
    }, {});
    const qs = new URLSearchParams(cleanParams).toString();
    return request<CatalogStats>(`/catalog/stats${qs ? `?${qs}` : ''}`);
  },
  compare: (repositoryIds: string[]) => {
    const params = new URLSearchParams();
    repositoryIds.forEach((id) => params.append('repository_id', id));
    return request<CompareResponse>(`/compare?${params.toString()}`);
  },
  repository: (id: string) =>
    request<RepositoryDetails>(`/repositories/${encodeURIComponent(id)}`),
  latestAnalysis: (repositoryId: string) =>
    request<AnalysisSummary>(`/repositories/${encodeURIComponent(repositoryId)}/analyses/latest`),
  analysisHistory: (repositoryId: string, limit = 50, offset = 0) =>
    request<AnalysisPage>(`/repositories/${encodeURIComponent(repositoryId)}/analyses?limit=${limit}&offset=${offset}`),
  analysis: (id: string) =>
    request<Analysis>(`/analyses/${encodeURIComponent(id)}`),
  aiSummary: (id: string, model: AISummaryMode, detail: AISummaryDetail = 'brief') =>
    request<AISummaryResponse>(`/analyses/${encodeURIComponent(id)}/ai-summary`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model, detail }),
    }),
  publicity: (repositoryId: string) =>
    request<ShareInfo>(`/publicity/repositories/${encodeURIComponent(repositoryId)}`),
  integrity: (repositoryId: string) =>
    request<IntegrityResponse>(`/repositories/${encodeURIComponent(repositoryId)}/integrity`),
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
