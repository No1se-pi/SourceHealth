import type {
  Repository,
  RepositoryDetails,
  Analysis,
} from '../api/client';

/**
 * Typed sample fixtures for development and UI component testing.
 * Uses OpenAPI schema types directly via TypeScript satisfies.
 *
 * NOTE: Production API client never falls back to these mocks.
 */

export const mockHealthyRepo = {
  id: 'a0000001-0000-0000-0000-000000000001',
  organization_slug: 'demo-org',
  repository_slug: 'fast-service',
  canonical_url: 'https://sourcecraft.tech/demo-org/fast-service',
  visibility: 'public',
  health_score: 88,
  language: 'TypeScript',
  likes: 42,
  last_activity_at: '2026-09-16T14:30:00Z',
  latest_analysis_id: 'b0000001-0000-0000-0000-000000000001',
} satisfies Repository;

export const mockNoDataRepo = {
  id: 'a0000002-0000-0000-0000-000000000002',
  organization_slug: 'newbie-corp',
  repository_slug: 'empty-starter',
  canonical_url: 'https://sourcecraft.tech/newbie-corp/empty-starter',
  visibility: 'public',
  health_score: null, // NO_DATA: not calculated yet, NOT zero!
  language: 'Python',
  likes: 0,
  last_activity_at: '2026-09-10T11:00:00Z',
  latest_analysis_id: null,
} satisfies Repository;

export const mockRepoDetails = {
  id: 'a0000001-0000-0000-0000-000000000001',
  organization_slug: 'demo-org',
  repository_slug: 'fast-service',
  canonical_url: 'https://sourcecraft.tech/demo-org/fast-service',
  visibility: 'public',
  health_score: 88,
  language: 'TypeScript',
  likes: 42,
  last_activity_at: '2026-09-16T14:30:00Z',
  latest_analysis_id: 'b0000001-0000-0000-0000-000000000001',
  sourcecraft_id: 'sc-987654',
  default_branch: 'main',
  head_sha: 'e7e88ab123456789abcdef0123456789abcdef01',
} satisfies RepositoryDetails;

export const mockCompletedAnalysis = {
  id: 'b0000001-0000-0000-0000-000000000001',
  repository_id: 'a0000001-0000-0000-0000-000000000001',
  status: 'completed',
  trigger: 'manual',
  queued_at: '2026-09-16T14:28:00Z',
  started_at: '2026-09-16T14:28:02Z',
  completed_at: '2026-09-16T14:28:45Z',
  head_sha: 'e7e88ab123456789abcdef0123456789abcdef01',
  health_score: 88,
  scoring_policy_version: 'v1',
  analyzer_contract_version: 'v1',
  error_code: null,
  category_scores: {
    documentation: {
      category: 'documentation',
      score: 85,
      availability: 'available',
      explanation: 'Наличие полного README, документации API и руководства по развёртыванию.',
      evidence_refs: ['ev-doc-1'],
    },
    cicd: {
      category: 'cicd',
      score: 92,
      availability: 'available',
      explanation: 'Пайплайн настроен и успешно проходит в основной ветке.',
      evidence_refs: ['ev-ci-1'],
    },
    security: {
      category: 'security',
      score: 80,
      availability: 'available',
      explanation: 'AppSec сканирование SourceCraft завершено без критических уязвимостей.',
      evidence_refs: ['ev-sec-1'],
    },
    activity: {
      category: 'activity',
      score: 90,
      availability: 'available',
      explanation: 'Регулярные коммиты и активность команды за последние 30 дней.',
      evidence_refs: ['ev-act-1'],
    },
    issues: {
      category: 'issues',
      score: 88,
      availability: 'available',
      explanation: 'Хорошее время ответа на открытые задачи, низкий уровень зависших тикетов.',
      evidence_refs: ['ev-iss-1'],
    },
    code_health: {
      category: 'code_health',
      score: 91,
      availability: 'available',
      explanation: 'Отсутствие грубых запахов кода и дублирования по результатам анализа.',
      evidence_refs: ['ev-ch-1'],
    },
  },
  data_coverage: {
    documentation: 'available',
    cicd: 'available',
    security: 'available',
    activity: 'available',
    issues: 'available',
    code_health: 'available',
  },
  recommendations: [
    {
      id: 'rec-1',
      category: 'documentation',
      title: 'Добавить описание схемы архитектуры',
      description: 'В README рекомендуется включить краткую схему связей модулей.',
      priority: 3,
      evidence_refs: ['ev-doc-1'],
      suggested_action: 'Создать diagrams/architecture.md',
      expected_impact: '+2 Health Score',
    },
  ],
  checks: {},
} satisfies Analysis;

export const mockPartialAnalysis = {
  id: 'b0000002-0000-0000-0000-000000000002',
  repository_id: 'a0000002-0000-0000-0000-000000000002',
  status: 'partial',
  trigger: 'manual',
  queued_at: '2026-09-16T15:00:00Z',
  started_at: '2026-09-16T15:00:02Z',
  completed_at: '2026-09-16T15:00:30Z',
  head_sha: 'abcdef1234567890abcdef1234567890abcdef12',
  health_score: null, // Partial with no final score yet
  scoring_policy_version: 'v1',
  analyzer_contract_version: 'v1',
  error_code: null,
  category_scores: {
    security: {
      category: 'security',
      score: null,
      availability: 'not_configured',
      explanation: 'SourceCraft AppSec не подключён для данного репозитория.',
      evidence_refs: [],
    },
    documentation: {
      category: 'documentation',
      score: 50,
      availability: 'partial',
      explanation: 'Найден только краткий README.',
      evidence_refs: [],
    },
  },
  data_coverage: {
    security: 'not_configured',
    documentation: 'partial',
  },
  recommendations: [],
  checks: {},
} satisfies Analysis;
