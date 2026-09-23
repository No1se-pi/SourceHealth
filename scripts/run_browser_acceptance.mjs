import http from 'http';
import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';

const outDir = path.resolve('docs/screenshots');
if (!fs.existsSync(outDir)) {
  fs.mkdirSync(outDir, { recursive: true });
}

const MOCK_PORT = 8005;

// ============================================================================
// DTO Builders adhering strictly to OpenAPI schema
// ============================================================================
function makeRepositorySummary(overrides = {}) {
  return {
    id: 'a0000001-0000-0000-0000-000000000001',
    organization_slug: 'demo-org',
    repository_slug: 'fast-service',
    canonical_url: 'https://sourcecraft.dev/demo-org/fast-service',
    visibility: 'public',
    health_score: 70.5,
    language: 'TypeScript',
    likes: 42,
    last_activity_at: '2026-09-20T14:30:00Z',
    latest_analysis_id: 'b0000001-0000-0000-0000-000000000001',
    score_preview: null,
    ...overrides
  };
}

function makeRepositoryDetails(overrides = {}) {
  return {
    id: 'a0000001-0000-0000-0000-000000000001',
    organization_slug: 'demo-org',
    repository_slug: 'fast-service',
    canonical_url: 'https://sourcecraft.dev/demo-org/fast-service',
    visibility: 'public',
    health_score: 70.5,
    language: 'TypeScript',
    likes: 42,
    last_activity_at: '2026-09-20T14:30:00Z',
    latest_analysis_id: 'b0000001-0000-0000-0000-000000000001',
    sourcecraft_id: 'sc-987654',
    default_branch: 'main',
    head_sha: 'e7e88ab123456789abcdef0123456789abcdef01',
    score_preview: null,
    ...overrides
  };
}

function makeAnalysisSummary(overrides = {}) {
  return {
    id: 'b0000001-0000-0000-0000-000000000001',
    repository_id: 'a0000001-0000-0000-0000-000000000001',
    profile: 'mvp-v1',
    status: 'completed',
    trigger: 'manual',
    queued_at: '2026-09-20T14:35:00Z',
    started_at: '2026-09-20T14:35:02Z',
    completed_at: '2026-09-20T14:36:12Z',
    head_sha: 'e7e88ab123456789abcdef0123456789abcdef01',
    health_score: 70.5,
    scoring_policy_version: 'mvp-score-v1.2',
    analyzer_contract_version: 'v1',
    error_code: null,
    ...overrides
  };
}

function makeCategoryScore(category, overrides = {}) {
  return {
    category,
    score: 80,
    availability: 'available',
    explanation: 'Анализ категории завершён успешно.',
    evidence_refs: [],
    ...overrides
  };
}

function makeEvidence(overrides = {}) {
  return {
    id: 'ev-default-1',
    source: 'analyzer_source',
    type: 'inspection_fact',
    reference: 'ref-1',
    summary: 'Описание подтверждающего факта',
    url: null,
    location: null,
    timestamp: null,
    ...overrides
  };
}

function makeRecommendation(overrides = {}) {
  return {
    id: 'rec-default-1',
    category: 'code_health',
    title: 'Рекомендация по улучшению качества кода',
    description: 'Описание проблемы и контекста.',
    priority: 2,
    evidence_refs: [],
    suggested_action: 'Рекомендуемое действие разработчику.',
    expected_impact: null,
    ...overrides
  };
}

function makeAnalyzerResult(analyzer, overrides = {}) {
  return {
    analyzer,
    status: 'ok',
    availability: 'available',
    source: analyzer,
    category: null,
    analyzer_version: '1.0.0',
    contract_version: 'v1',
    metrics: {},
    findings: [],
    metadata: {},
    error: null,
    evidence: [],
    ...overrides
  };
}

function makeScoreCoverage(overrides = {}) {
  return {
    nominal_weight_percent: 100,
    scored_categories: 6,
    unscored_categories: [],
    partial_categories: [],
    ...overrides
  };
}

function makeAnalysisDetails(overrides = {}) {
  return {
    id: 'b0000001-0000-0000-0000-000000000001',
    repository_id: 'a0000001-0000-0000-0000-000000000001',
    profile: 'mvp-v1',
    status: 'completed',
    trigger: 'manual',
    queued_at: '2026-09-20T14:35:00Z',
    started_at: '2026-09-20T14:35:02Z',
    completed_at: '2026-09-20T14:36:12Z',
    head_sha: 'e7e88ab123456789abcdef0123456789abcdef01',
    health_score: 70.5,
    scoring_policy_version: 'mvp-score-v1.2',
    analyzer_contract_version: 'v1',
    error_code: null,
    category_scores: {},
    data_coverage: {},
    recommendations: [],
    checks: {},
    score_coverage: null,
    score_preview: null,
    ...overrides
  };
}

// ============================================================================
// Fixture Contract Drift Guard & Assertions
// ============================================================================
function assert(condition, message) {
  if (!condition) {
    throw new Error(`[CONTRACT DRIFT ERROR] ${message}`);
  }
}

function assertNoKeys(obj, forbiddenKeys, context) {
  for (const key of forbiddenKeys) {
    assert(!(key in obj), `${context} must not contain forbidden/legacy key '${key}'`);
  }
}

function assertRequiredKeys(obj, requiredKeys, context) {
  for (const key of requiredKeys) {
    assert(key in obj, `${context} is missing required OpenAPI key '${key}'`);
  }
}

function validateEvidence(ev, context) {
  assertRequiredKeys(ev, ['id', 'source', 'type', 'reference', 'summary'], context);
  assertNoKeys(ev, ['category', 'description'], context);
  if (ev.url) {
    assert(!ev.url.includes('sourcecraft.tech'), `${context} URL must not use sourcecraft.tech (use sourcecraft.dev)`);
  }
}

function validateCategoryScore(cs, key, context) {
  assertRequiredKeys(cs, ['category', 'availability', 'explanation', 'evidence_refs'], `${context}.category_scores[${key}]`);
  assertNoKeys(cs, ['weight'], `${context}.category_scores[${key}]`);
  assert(Array.isArray(cs.evidence_refs), `${context}.category_scores[${key}].evidence_refs must be an array`);
}

function validateRecommendation(rec, context) {
  assertRequiredKeys(rec, ['id', 'category', 'title', 'description', 'priority', 'evidence_refs', 'suggested_action', 'expected_impact'], context);
  assertNoKeys(rec, ['effort', 'action'], context);
  assert(typeof rec.priority === 'number', `${context}.priority must be a number (not string)`);
  assert(Array.isArray(rec.evidence_refs), `${context}.evidence_refs must be an array`);
}

function validateAnalyzerResult(ar, key, context) {
  assertRequiredKeys(ar, ['analyzer', 'status', 'availability', 'source', 'category', 'analyzer_version', 'contract_version', 'metrics', 'findings', 'metadata', 'error', 'evidence'], `${context}.checks[${key}]`);
  assert(['ok', 'partial', 'error'].includes(ar.status), `${context}.checks[${key}].status must be ok|partial|error`);
  assert(Array.isArray(ar.evidence), `${context}.checks[${key}].evidence must be an array`);
  ar.evidence.forEach((ev, idx) => validateEvidence(ev, `${context}.checks[${key}].evidence[${idx}]`));
}

function validateScoreCoverage(sc, context) {
  assertRequiredKeys(sc, ['nominal_weight_percent', 'scored_categories', 'unscored_categories', 'partial_categories'], context);
  assert(typeof sc.nominal_weight_percent === 'number', `${context}.nominal_weight_percent must be a number`);
  assert(typeof sc.scored_categories === 'number', `${context}.scored_categories must be a number`);
  assert(Array.isArray(sc.unscored_categories), `${context}.unscored_categories must be an array`);
  assert(Array.isArray(sc.partial_categories), `${context}.partial_categories must be an array`);
}

function validateScorePreview(preview, context) {
  assertRequiredKeys(preview, ['score', 'nominal_weight_percent', 'scored_categories', 'numeric'], context);
  assert(typeof preview.numeric === 'boolean', `${context}.numeric must be a boolean`);
}

function validateRepositorySummary(repo, context) {
  assertRequiredKeys(repo, ['id', 'organization_slug', 'repository_slug', 'canonical_url', 'visibility', 'health_score', 'language', 'likes', 'last_activity_at', 'latest_analysis_id', 'score_preview'], context);
  assertNoKeys(repo, ['created_at', 'updated_at', 'score', 'default_branch', 'head_sha'], context);
  assert(!repo.canonical_url.includes('sourcecraft.tech'), `${context}.canonical_url must not use sourcecraft.tech (use sourcecraft.dev)`);
  if (repo.score_preview != null) validateScorePreview(repo.score_preview, `${context}.score_preview`);
}

function validateRepositoryDetails(repo, context) {
  assertRequiredKeys(repo, ['id', 'organization_slug', 'repository_slug', 'canonical_url', 'visibility', 'health_score', 'language', 'likes', 'last_activity_at', 'latest_analysis_id', 'sourcecraft_id', 'default_branch', 'head_sha', 'score_preview'], context);
  assertNoKeys(repo, ['created_at', 'updated_at', 'score'], context);
  assert(!repo.canonical_url.includes('sourcecraft.tech'), `${context}.canonical_url must not use sourcecraft.tech (use sourcecraft.dev)`);
  if (repo.score_preview != null) validateScorePreview(repo.score_preview, `${context}.score_preview`);
}

function validateAnalysisSummary(as, context) {
  assertRequiredKeys(as, ['id', 'repository_id', 'profile', 'status', 'trigger', 'queued_at', 'started_at', 'completed_at', 'head_sha', 'health_score', 'scoring_policy_version', 'analyzer_contract_version', 'error_code'], context);
  assertNoKeys(as, ['score', 'created_at', 'evidence', 'category_scores', 'checks', 'recommendations'], context);
}

function validateAnalysisDetails(ad, context) {
  assertRequiredKeys(ad, ['id', 'repository_id', 'profile', 'status', 'trigger', 'queued_at', 'started_at', 'completed_at', 'head_sha', 'health_score', 'scoring_policy_version', 'analyzer_contract_version', 'error_code', 'category_scores', 'data_coverage', 'recommendations', 'checks', 'score_preview'], context);
  assertNoKeys(ad, ['score', 'created_at', 'evidence'], context);
  assert(!Array.isArray(ad.checks), `${context}.checks must be Record<string, AnalyzerResultDTO>, not an Array`);
  assert(typeof ad.checks === 'object' && ad.checks !== null, `${context}.checks must be an object`);
  assert(typeof ad.category_scores === 'object' && ad.category_scores !== null, `${context}.category_scores must be an object`);
  assert(Array.isArray(ad.recommendations), `${context}.recommendations must be an array`);

  for (const [key, cs] of Object.entries(ad.category_scores)) {
    validateCategoryScore(cs, key, context);
  }
  for (const [key, ar] of Object.entries(ad.checks)) {
    validateAnalyzerResult(ar, key, context);
  }
  ad.recommendations.forEach((rec, idx) => validateRecommendation(rec, `${context}.recommendations[${idx}]`));
  if (ad.score_coverage != null) {
    validateScoreCoverage(ad.score_coverage, `${context}.score_coverage`);
  }
  if (ad.score_preview != null) validateScorePreview(ad.score_preview, `${context}.score_preview`);
}

// ============================================================================
// Canonical Mock Fixtures
// ============================================================================
const fixtureLeaderboardItems = [
  makeRepositorySummary({
    id: 'a0000001-0000-0000-0000-000000000001',
    organization_slug: 'demo-org',
    repository_slug: 'fast-service',
    canonical_url: 'https://sourcecraft.dev/demo-org/fast-service',
    visibility: 'public',
    health_score: 88,
    language: 'TypeScript',
    likes: 42,
    last_activity_at: '2026-09-20T14:30:00Z',
    latest_analysis_id: 'b0000001-0000-0000-0000-000000000001'
  }),
  makeRepositorySummary({
    id: 'a0000007-0000-0000-0000-000000000007',
    organization_slug: 'very-long-enterprise-organization-holding-corp',
    repository_slug: 'mission-critical-microservice-super-extended-repository-slug-v2',
    canonical_url: 'https://sourcecraft.dev/very-long-enterprise-organization-holding-corp/mission-critical-microservice-super-extended-repository-slug-v2',
    visibility: 'public',
    health_score: 85,
    language: 'TypeScript',
    likes: 512,
    last_activity_at: '2026-09-21T10:00:00Z',
    latest_analysis_id: 'b0000007-0000-0000-0000-000000000007'
  }),
  makeRepositorySummary({
    id: 'a0000002-0000-0000-0000-000000000002',
    organization_slug: 'newbie-corp',
    repository_slug: 'empty-starter',
    canonical_url: 'https://sourcecraft.dev/newbie-corp/empty-starter',
    visibility: 'public',
    health_score: null, // NO_DATA fixture in leaderboard
    language: 'Python',
    likes: null,
    last_activity_at: null,
    latest_analysis_id: 'b0000002-0000-0000-0000-000000000002',
    score_preview: { score: 43.81, nominal_weight_percent: 30, scored_categories: 2, numeric: true }
  }),
  makeRepositorySummary({
    id: 'a0000003-0000-0000-0000-000000000003',
    organization_slug: 'yandex-cloud',
    repository_slug: 'serverless-gate',
    canonical_url: 'https://sourcecraft.dev/yandex-cloud/serverless-gate',
    visibility: 'public',
    health_score: 94,
    language: 'Go',
    likes: 87,
    last_activity_at: '2026-09-19T18:00:00Z',
    latest_analysis_id: 'b0000001-0000-0000-0000-000000000001'
  }),
  makeRepositorySummary({
    id: 'a0000004-0000-0000-0000-000000000004',
    organization_slug: 'infra-tools',
    repository_slug: 'k8s-operator',
    canonical_url: 'https://sourcecraft.dev/infra-tools/k8s-operator',
    visibility: 'public',
    health_score: 62,
    language: 'Rust',
    likes: 19,
    last_activity_at: '2026-09-15T11:20:00Z',
    latest_analysis_id: 'b0000001-0000-0000-0000-000000000001'
  }),
  makeRepositorySummary({
    id: 'a0000005-0000-0000-0000-000000000005',
    organization_slug: 'lct-hackaton-2026',
    repository_slug: 'case-18-repo-health-score-team-41',
    canonical_url: 'https://sourcecraft.dev/lct-hackaton-2026/case-18-repo-health-score-team-41',
    visibility: 'public',
    health_score: 78,
    language: 'Python',
    likes: 128,
    last_activity_at: '2026-09-21T09:15:00Z',
    latest_analysis_id: 'b0000001-0000-0000-0000-000000000001'
  })
];

const fixtureRepoHealthy = makeRepositoryDetails({
  id: 'a0000001-0000-0000-0000-000000000001',
  organization_slug: 'demo-org',
  repository_slug: 'fast-service',
  canonical_url: 'https://sourcecraft.dev/demo-org/fast-service',
  visibility: 'public',
  default_branch: 'main',
  head_sha: 'e7e88ab123456789abcdef0123456789abcdef01',
  sourcecraft_id: 'sc-987654',
  health_score: 70.5,
  language: 'TypeScript',
  likes: 42,
  last_activity_at: '2026-09-20T14:30:00Z',
  latest_analysis_id: 'b0000001-0000-0000-0000-000000000001'
});

const fixtureRepoNoData = makeRepositoryDetails({
  id: 'a0000002-0000-0000-0000-000000000002',
  organization_slug: 'newbie-corp',
  repository_slug: 'empty-starter',
  canonical_url: 'https://sourcecraft.dev/newbie-corp/empty-starter',
  visibility: 'public',
  default_branch: 'main',
  head_sha: null,
  sourcecraft_id: null,
  health_score: null,
  language: 'Python',
  likes: null,
  last_activity_at: null,
  latest_analysis_id: 'b0000002-0000-0000-0000-000000000002',
  score_preview: { score: 43.81, nominal_weight_percent: 30, scored_categories: 2, numeric: true }
});

const fixtureRepoLongSlug = makeRepositoryDetails({
  id: 'a0000007-0000-0000-0000-000000000007',
  organization_slug: 'very-long-enterprise-organization-holding-corp',
  repository_slug: 'mission-critical-microservice-super-extended-repository-slug-v2',
  canonical_url: 'https://sourcecraft.dev/very-long-enterprise-organization-holding-corp/mission-critical-microservice-super-extended-repository-slug-v2',
  visibility: 'public',
  default_branch: 'main',
  head_sha: 'a1b2c3d4e5f60718293a4b5c6d7e8f9012345678',
  sourcecraft_id: 'sc-long-777',
  health_score: 85,
  language: 'TypeScript',
  likes: 512,
  last_activity_at: '2026-09-21T10:00:00Z',
  latest_analysis_id: 'b0000007-0000-0000-0000-000000000007'
});

const fixtureAnalysisHistory = [
  makeAnalysisSummary({
    id: 'b0000001-0000-0000-0000-000000000001',
    repository_id: 'a0000001-0000-0000-0000-000000000001',
    status: 'completed',
    health_score: 70.5,
    queued_at: '2026-09-20T14:35:00Z',
    started_at: '2026-09-20T14:35:02Z',
    completed_at: '2026-09-20T14:36:12Z',
    head_sha: 'e7e88ab123456789abcdef0123456789abcdef01',
    profile: 'mvp-v1',
    trigger: 'manual',
    scoring_policy_version: 'mvp-score-v1.2',
    analyzer_contract_version: 'v1',
    error_code: null
  })
];

const fixtureAnalysisCompleted = makeAnalysisDetails({
  id: 'b0000001-0000-0000-0000-000000000001',
  repository_id: 'a0000001-0000-0000-0000-000000000001',
  status: 'completed',
  health_score: 70.5,
  category_scores: {
    documentation: makeCategoryScore('documentation', {
      score: 92,
      availability: 'available',
      explanation: 'README.md найден (324 строки, документация API полная).',
      evidence_refs: ['ev-doc-1']
    }),
    cicd: makeCategoryScore('cicd', {
      score: 85,
      availability: 'available',
      explanation: 'CI пайплайн настроен и проходит успешно в 98% сборок.',
      evidence_refs: ['ev-ci-1']
    }),
    security: makeCategoryScore('security', {
      score: 0,
      availability: 'available',
      explanation: 'Official AppSec: штрафы снизили численную оценку до минимального значения.',
      evidence_refs: ['ev-sec-1']
    }),
    activity: makeCategoryScore('activity', {
      score: 95,
      availability: 'available',
      explanation: '34 коммита за последние 30 дней от 4 активных авторов.',
      evidence_refs: ['ev-act-1']
    }),
    issues: makeCategoryScore('issues', {
      score: 78,
      availability: 'available',
      explanation: 'Среднее время закрытия задач составляет 2.4 дня.',
      evidence_refs: ['ev-iss-1']
    }),
    code_health: makeCategoryScore('code_health', {
      score: 90,
      availability: 'available',
      explanation: 'SAST анализ: дефектов и запахов кода не обнаружено.',
      evidence_refs: ['ev-ch-1']
    })
  },
  data_coverage: {
    documentation: 'available',
    cicd: 'available',
    security: 'available',
    activity: 'available',
    issues: 'available',
    code_health: 'available'
  },
  recommendations: [
    makeRecommendation({
      id: 'rec-1',
      category: 'code_health',
      title: 'Добавьте тесты для критических модулей',
      description: 'Покрытие тестами в модуле auth составляет 64%. Рекомендуется поднять до 80%.',
      priority: 2,
      evidence_refs: ['ev-ch-1'],
      suggested_action: 'Написать модульные тесты для auth/provider.go',
      expected_impact: '+4 Health Score'
    })
  ],
  checks: {
    readme_parser: makeAnalyzerResult('readme_parser', {
      source: 'readme_parser',
      category: 'documentation',
      evidence: [
        makeEvidence({
          id: 'ev-doc-1',
          source: 'readme_parser',
          type: 'file_presence',
          reference: 'README.md',
          summary: 'README.md найден (324 строки, документация API полная)',
          url: 'https://sourcecraft.dev/demo-org/fast-service/src/branch/main/README.md',
          location: 'README.md:1',
          timestamp: '2026-09-20T14:35:10Z'
        })
      ]
    }),
    sourcecraft_ci: makeAnalyzerResult('sourcecraft_ci', {
      source: 'sourcecraft_ci',
      category: 'cicd',
      evidence: [
        makeEvidence({
          id: 'ev-ci-1',
          source: 'sourcecraft_ci',
          type: 'pipeline_run',
          reference: 'pipeline/main',
          summary: 'CI пайплайн настроен и проходит успешно в 98% сборок',
          url: 'https://sourcecraft.dev/demo-org/fast-service/pipelines/1',
          location: null,
          timestamp: '2026-09-20T14:35:12Z'
        })
      ]
    }),
    sourcecraft_appsec: makeAnalyzerResult('sourcecraft_appsec', {
      source: 'sourcecraft_appsec',
      category: 'security',
      metrics: { complete: true, open_by_severity: { critical: 0, high: 5, medium: 13, low: 5 }, total_open: 23 },
      evidence: [
        makeEvidence({
          id: 'ev-sec-1',
          source: 'sourcecraft_appsec',
          type: 'vulnerability_scan',
          reference: 'appsec/latest',
          summary: 'Official AppSec агрегаты собраны полностью',
          url: 'https://sourcecraft.dev/demo-org/fast-service/security',
          location: null,
          timestamp: '2026-09-20T14:35:15Z'
        })
      ]
    }),
    git_activity: makeAnalyzerResult('git_activity', {
      source: 'git_log',
      category: 'activity',
      evidence: [
        makeEvidence({
          id: 'ev-act-1',
          source: 'git_log',
          type: 'commit_history',
          reference: 'commits',
          summary: '34 коммита за последние 30 дней от 4 активных авторов',
          url: 'https://sourcecraft.dev/demo-org/fast-service/commits',
          location: null,
          timestamp: '2026-09-20T14:35:18Z'
        })
      ]
    }),
    sourcecraft_issues: makeAnalyzerResult('sourcecraft_issues', {
      source: 'sourcecraft_issues',
      category: 'issues',
      evidence: [
        makeEvidence({
          id: 'ev-iss-1',
          source: 'sourcecraft_issues',
          type: 'issue_metrics',
          reference: 'issues',
          summary: 'Среднее время закрытия задач составляет 2.4 дня',
          url: 'https://sourcecraft.dev/demo-org/fast-service/issues',
          location: null,
          timestamp: '2026-09-20T14:35:20Z'
        })
      ]
    }),
    sourcehealth_local: makeAnalyzerResult('sourcehealth_local', {
      source: 'sourcehealth_local',
      category: 'code_health',
      evidence: [
        makeEvidence({
          id: 'ev-ch-1',
          source: 'sourcehealth_local',
          type: 'code_smell',
          reference: 'src/core',
          summary: 'SAST анализ: дефектов и запахов кода не обнаружено',
          url: null,
          location: null,
          timestamp: '2026-09-20T14:35:22Z'
        })
      ]
    })
  },
  score_coverage: makeScoreCoverage({
    nominal_weight_percent: 100,
    scored_categories: 6,
    unscored_categories: [],
    partial_categories: []
  }),
  score_preview: { score: 70.5, nominal_weight_percent: 100, scored_categories: 6, numeric: true }
});

const fixtureAnalysisPartial = makeAnalysisDetails({
  id: 'b0000002-0000-0000-0000-000000000002',
  repository_id: 'a0000002-0000-0000-0000-000000000002',
  status: 'partial',
  health_score: null,
  category_scores: {
    documentation: makeCategoryScore('documentation', { score: null, availability: 'no_data', explanation: 'Недостаточно данных.', evidence_refs: [] }),
    cicd: makeCategoryScore('cicd', { score: null, availability: 'no_data', explanation: 'Данные CI/CD недоступны в SourceCraft.', evidence_refs: [] }),
    security: makeCategoryScore('security', { score: null, availability: 'no_data', explanation: 'Official AppSec пока недоступен.', evidence_refs: [] }),
    activity: makeCategoryScore('activity', { score: 87.61, availability: 'available', explanation: 'Активность рассчитана по Git.', evidence_refs: [] }),
    issues: makeCategoryScore('issues', { score: 0, availability: 'available', explanation: 'Наблюдения есть; итог категории равен нулю.', evidence_refs: [] }),
    code_health: makeCategoryScore('code_health', { score: null, availability: 'no_data', explanation: 'Недостаточно данных.', evidence_refs: [] })
  },
  data_coverage: {
    documentation: 'no_data',
    cicd: 'no_data',
    security: 'no_data',
    activity: 'available',
    issues: 'available',
    code_health: 'no_data'
  },
  score_coverage: makeScoreCoverage({
    nominal_weight_percent: 30,
    scored_categories: 2,
    unscored_categories: ['documentation', 'cicd', 'security', 'code_health'],
    partial_categories: []
  }),
  recommendations: [],
  checks: {},
  score_preview: { score: 43.81, nominal_weight_percent: 30, scored_categories: 2, numeric: true }
});

const fixtureAnalysisFailed = makeAnalysisDetails({
  id: 'b0000005-0000-0000-0000-000000000005',
  repository_id: 'a0000001-0000-0000-0000-000000000001',
  status: 'failed',
  health_score: null,
  error_code: 'source_unavailable',
  category_scores: {},
  data_coverage: {},
  recommendations: [],
  checks: {},
  score_coverage: null
});

const fixtureAnalysisSecurityNoData = makeAnalysisDetails({
  id: 'b0000006-0000-0000-0000-000000000006',
  repository_id: 'a0000002-0000-0000-0000-000000000002',
  status: 'completed',
  health_score: 82,
  category_scores: {
    documentation: makeCategoryScore('documentation', { score: 85, availability: 'available', explanation: 'README и руководства доступны.', evidence_refs: [] }),
    cicd: makeCategoryScore('cicd', { score: 80, availability: 'available', explanation: 'Пайплайны отрабатывают штатно.', evidence_refs: [] }),
    security: makeCategoryScore('security', { score: null, availability: 'no_data', explanation: 'SourceCraft AppSec data unavailable.', evidence_refs: [] }),
    activity: makeCategoryScore('activity', { score: 80, availability: 'available', explanation: 'Регулярные коммиты в main ветку.', evidence_refs: [] }),
    issues: makeCategoryScore('issues', { score: 75, availability: 'available', explanation: 'Задачи закрываются в штатном темпе.', evidence_refs: [] }),
    code_health: makeCategoryScore('code_health', { score: 88, availability: 'available', explanation: 'SAST дефектов не выявил.', evidence_refs: [] })
  },
  data_coverage: {
    documentation: 'available',
    cicd: 'available',
    security: 'no_data',
    activity: 'available',
    issues: 'available',
    code_health: 'available'
  },
  score_coverage: makeScoreCoverage({
    nominal_weight_percent: 75,
    scored_categories: 5,
    unscored_categories: ['security'],
    partial_categories: []
  }),
  recommendations: [],
  checks: {}
});

const fixtureAnalysisLongRecommendation = makeAnalysisDetails({
  id: 'b0000007-0000-0000-0000-000000000007',
  repository_id: 'a0000007-0000-0000-0000-000000000007',
  status: 'completed',
  health_score: 85,
  category_scores: {
    documentation: makeCategoryScore('documentation', { score: 88, availability: 'available', explanation: 'Полная техническая спецификация API с примерами вызовов.', evidence_refs: ['ev-1'] }),
    cicd: makeCategoryScore('cicd', { score: 82, availability: 'available', explanation: 'CI/CD пайплайны развёрнуты.', evidence_refs: [] }),
    security: makeCategoryScore('security', { score: 75, availability: 'available', explanation: 'Базовая защита включена.', evidence_refs: [] }),
    activity: makeCategoryScore('activity', { score: 90, availability: 'available', explanation: 'Высокая активность контрибьюторов.', evidence_refs: [] }),
    issues: makeCategoryScore('issues', { score: 85, availability: 'available', explanation: 'Активное ведение задач.', evidence_refs: [] }),
    code_health: makeCategoryScore('code_health', { score: 92, availability: 'available', explanation: 'Высокое качество исходного кода.', evidence_refs: [] })
  },
  data_coverage: {
    documentation: 'available',
    cicd: 'available',
    security: 'available',
    activity: 'available',
    issues: 'available',
    code_health: 'available'
  },
  score_coverage: makeScoreCoverage({
    nominal_weight_percent: 100,
    scored_categories: 6,
    unscored_categories: [],
    partial_categories: []
  }),
  recommendations: [
    makeRecommendation({
      id: 'rec-long-1',
      category: 'security',
      title: 'Комплексная реструктуризация инфраструктурных пайплайнов и политик безопасности контейнерных сред',
      description: 'Данный репозиторий содержит критические точки входа для внешних распределённых микросервисов. Настоятельно рекомендуется полностью переработать конфигурацию CI/CD пайплайнов, внедрить строгие политики сканирования базовых образов OCI на этапе предварительного коммита, настроить автоматическую проверку зависимостей и контроль версий через Dependabot/Snyk, а также активировать сигнатурную верификацию артефактов в защищённом реестре SourceCraft Registry.',
      priority: 1,
      evidence_refs: ['ev-1'],
      suggested_action: 'Развернуть расширенный набор анализаторов безопасности SourceCraft AppSec и локальных линтеров',
      expected_impact: '+10 к уровню защищенности сервиса'
    })
  ],
  checks: {
    readme_parser: makeAnalyzerResult('readme_parser', {
      source: 'readme_parser',
      category: 'documentation',
      evidence: [
        makeEvidence({
          id: 'ev-1',
          source: 'readme_parser',
          type: 'file_presence',
          reference: 'README.md',
          summary: 'Полная техническая спецификация API с примерами вызовов',
          url: 'https://sourcecraft.dev/very-long-enterprise-organization-holding-corp/mission-critical-microservice-super-extended-repository-slug-v2/src/branch/main/README.md',
          location: 'README.md:1',
          timestamp: '2026-09-21T09:00:10Z'
        })
      ]
    })
  }
});

// ============================================================================
// Run Pre-Flight Drift Guard Validations
// ============================================================================
console.log('Validating acceptance mock fixtures against OpenAPI schema...');
fixtureLeaderboardItems.forEach((repo, idx) => validateRepositorySummary(repo, `fixtureLeaderboardItems[${idx}]`));
validateRepositoryDetails(fixtureRepoHealthy, 'fixtureRepoHealthy');
validateRepositoryDetails(fixtureRepoNoData, 'fixtureRepoNoData');
validateRepositoryDetails(fixtureRepoLongSlug, 'fixtureRepoLongSlug');
fixtureAnalysisHistory.forEach((as, idx) => validateAnalysisSummary(as, `fixtureAnalysisHistory[${idx}]`));
validateAnalysisDetails(fixtureAnalysisCompleted, 'fixtureAnalysisCompleted');
validateAnalysisDetails(fixtureAnalysisPartial, 'fixtureAnalysisPartial');
validateAnalysisDetails(fixtureAnalysisFailed, 'fixtureAnalysisFailed');
validateAnalysisDetails(fixtureAnalysisSecurityNoData, 'fixtureAnalysisSecurityNoData');
validateAnalysisDetails(fixtureAnalysisLongRecommendation, 'fixtureAnalysisLongRecommendation');
console.log('✓ All acceptance mock fixtures strictly adhere to OpenAPI contract (no legacy fields detected).');

// ============================================================================
// Start Mock HTTP API Server
// ============================================================================
const mockServer = http.createServer((req, res) => {
  const url = new URL(req.url, `http://127.0.0.1:${MOCK_PORT}`);
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Access-Control-Allow-Origin', '*');

  if (url.pathname === '/api/v1/me') {
    res.writeHead(200);
    return res.end(JSON.stringify({ id: 'sc-user-demo-42' }));
  }

  // 1. Leaderboard
  if (url.pathname === '/api/v1/repositories') {
    if (url.searchParams.get('language') === 'EmptyLang') {
      res.writeHead(200);
      return res.end(JSON.stringify({ items: [], limit: 20, offset: 0, has_more: false }));
    }
    if (url.searchParams.get('sort') === 'error_trigger') {
      res.writeHead(500);
      return res.end(JSON.stringify({ code: 'service_unavailable', request_id: 'req-lb-err-500' }));
    }

    res.writeHead(200);
    return res.end(JSON.stringify({
      items: fixtureLeaderboardItems,
      limit: 20,
      offset: 0,
      has_more: false
    }));
  }

  // 2. Repository details: healthy
  if (url.pathname === '/api/v1/repositories/a0000001-0000-0000-0000-000000000001') {
    res.writeHead(200);
    return res.end(JSON.stringify(fixtureRepoHealthy));
  }

  // 3. Repository details: NO_DATA
  if (url.pathname === '/api/v1/repositories/a0000002-0000-0000-0000-000000000002') {
    res.writeHead(200);
    return res.end(JSON.stringify(fixtureRepoNoData));
  }

  // 4. Repository details: long slug
  if (url.pathname === '/api/v1/repositories/a0000007-0000-0000-0000-000000000007') {
    res.writeHead(200);
    return res.end(JSON.stringify(fixtureRepoLongSlug));
  }

  // 5. Repository details: loading fixture (never resolves within client timeout)
  if (url.pathname === '/api/v1/repositories/a0000008-0000-0000-0000-000000000008') {
    return;
  }

  // 6. Repository analyses history
  if (url.pathname.endsWith('/analyses') && req.method === 'GET') {
    res.writeHead(200);
    return res.end(JSON.stringify({
      items: fixtureAnalysisHistory,
      limit: 10,
      offset: 0,
      has_more: false
    }));
  }

  // 7. Analysis: completed healthy
  if (url.pathname === '/api/v1/analyses/b0000001-0000-0000-0000-000000000001') {
    res.writeHead(200);
    return res.end(JSON.stringify(fixtureAnalysisCompleted));
  }

  // 8. Analysis: partial
  if (url.pathname === '/api/v1/analyses/b0000002-0000-0000-0000-000000000002') {
    res.writeHead(200);
    return res.end(JSON.stringify(fixtureAnalysisPartial));
  }

  // 9. Analysis: failed
  if (url.pathname === '/api/v1/analyses/b0000005-0000-0000-0000-000000000005') {
    res.writeHead(200);
    return res.end(JSON.stringify(fixtureAnalysisFailed));
  }

  // 10. Analysis: Security NO_DATA
  if (url.pathname === '/api/v1/analyses/b0000006-0000-0000-0000-000000000006') {
    res.writeHead(200);
    return res.end(JSON.stringify(fixtureAnalysisSecurityNoData));
  }

  // 11. Analysis: Long recommendation
  if (url.pathname === '/api/v1/analyses/b0000007-0000-0000-0000-000000000007') {
    res.writeHead(200);
    return res.end(JSON.stringify(fixtureAnalysisLongRecommendation));
  }

  // 12. SourceCraft connection
  if (url.pathname === '/api/v1/sourcecraft/connection') {
    if (url.searchParams.get('disconnected') === '1' || req.headers.referer?.includes('disconnected=1')) {
      res.writeHead(200);
      return res.end(JSON.stringify({ connected: false }));
    }
    res.writeHead(200);
    return res.end(JSON.stringify({ connected: true, expires_in: 1800 }));
  }

  // 13. SourceCraft repositories
  if (url.pathname === '/api/v1/sourcecraft/repositories') {
    res.writeHead(200);
    return res.end(JSON.stringify({
      items: [
        { url: 'https://sourcecraft.dev/lct-hackaton-2026/case-18-repo-health-score-team-41', visibility: 'public', can_analyze: true },
        { url: 'https://sourcecraft.dev/lct-hackaton-2026/secret-core-module', visibility: 'private', can_analyze: false }
      ],
      has_more: false
    }));
  }

  res.writeHead(404);
  res.end(JSON.stringify({ error: 'not_found' }));
});

mockServer.listen(MOCK_PORT, '127.0.0.1', () => {
  console.log(`Mock API server listening on http://127.0.0.1:${MOCK_PORT}`);
});

// ============================================================================
// Start Vite Preview Server
// ============================================================================
const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm';
const vite = spawn(npmCmd, ['run', 'preview', '--', '--port', '5173'], {
  cwd: path.resolve('frontend'),
  shell: true,
  stdio: 'pipe',
  env: { ...process.env, VITE_BACKEND_PORT: String(MOCK_PORT) }
});

console.log('Waiting for Vite preview on http://127.0.0.1:5173 ...');
let viteReady = false;
for (let i = 0; i < 25; i++) {
  try {
    const res = await fetch('http://127.0.0.1:5173/');
    if (res.ok) {
      viteReady = true;
      console.log('Vite preview is ready!');
      break;
    }
  } catch {
    // retry
  }
  await new Promise((r) => setTimeout(r, 400));
}

if (!viteReady) {
  console.error('FATAL: Vite preview failed to start');
  vite.kill();
  mockServer.close();
  process.exit(1);
}

// ============================================================================
// Launch Browser with CDP
// ============================================================================
function findBrowserExecutable() {
  if (process.platform === 'win32') {
    const candidates = [
      'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
      'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
      'C:/Program Files/Google/Chrome/Application/chrome.exe',
      'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
      process.env.LOCALAPPDATA ? path.join(process.env.LOCALAPPDATA, 'Google/Chrome/Application/chrome.exe') : null,
      process.env.LOCALAPPDATA ? path.join(process.env.LOCALAPPDATA, 'Microsoft/Edge/Application/msedge.exe') : null,
    ].filter(Boolean);
    return candidates.find((p) => fs.existsSync(p)) || null;
  } else if (process.platform === 'darwin') {
    const candidates = [
      '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
      '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
      '/Applications/Chromium.app/Contents/MacOS/Chromium'
    ];
    return candidates.find((p) => fs.existsSync(p)) || null;
  } else {
    // Linux
    const candidates = [
      '/usr/bin/google-chrome',
      '/usr/bin/google-chrome-stable',
      '/usr/bin/chromium',
      '/usr/bin/chromium-browser',
      '/usr/bin/microsoft-edge',
      '/usr/bin/microsoft-edge-stable'
    ];
    return candidates.find((p) => fs.existsSync(p)) || null;
  }
}

const browserExe = findBrowserExecutable();
if (!browserExe) {
  console.error('FATAL: Browser executable not found on host machine');
  vite.kill();
  mockServer.close();
  process.exit(1);
}

console.log(`Starting headless browser (${browserExe}) with CDP remote debugging on port 9222...`);
const browserProc = spawn(browserExe, [
  '--headless=new',
  '--remote-debugging-port=9222',
  '--disable-gpu',
  '--hide-scrollbars',
  'about:blank'
]);

await new Promise((r) => setTimeout(r, 1500));

// Connect to CDP page target
let wsUrl = null;
for (let i = 0; i < 10; i++) {
  try {
    const res = await fetch('http://127.0.0.1:9222/json/list');
    const list = await res.json();
    const page = list.find((t) => t.type === 'page');
    if (page && page.webSocketDebuggerUrl) {
      wsUrl = page.webSocketDebuggerUrl;
      break;
    }
  } catch {
    // retry
  }
  await new Promise((r) => setTimeout(r, 500));
}

if (!wsUrl) {
  console.error('FATAL: Could not obtain CDP WebSocketDebuggerUrl');
  browserProc.kill();
  vite.kill();
  mockServer.close();
  process.exit(1);
}

console.log('CDP WebSocket connected to:', wsUrl);
const ws = new WebSocket(wsUrl);

await new Promise((resolve, reject) => {
  ws.onopen = resolve;
  ws.onerror = reject;
});

let msgId = 1;
function sendCdp(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++msgId;
    const handler = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.id === id) {
          ws.removeEventListener('message', handler);
          if (data.error) reject(new Error(data.error.message));
          else resolve(data.result);
        }
      } catch (err) {
        reject(err);
      }
    };
    ws.addEventListener('message', handler);
    ws.send(JSON.stringify({ id, method, params }));
  });
}

// Enable Page and Runtime domains
await sendCdp('Page.enable');
await sendCdp('Runtime.enable');

// ============================================================================
// Full Acceptance Matrix: 40 screenshots
// ============================================================================
const tasks = [
  // Product explainability / Source Soul focused acceptance
  { name: ['41', 'explainability', 'leaderboard', 'source', 'soul', 'desktop.png'].join('-'), url: 'http://127.0.0.1:5173/?theme=dark', width: 1440, height: 900 },
  { name: ['42', 'explainability', 'leaderboard', 'source', 'soul', 'mobile.png'].join('-'), url: 'http://127.0.0.1:5173/?theme=dark', width: 390, height: 844 },
  { name: ['43', 'explainability', 'analysis', 'appsec', 'zero.png'].join('-'), url: 'http://127.0.0.1:5173/analyses/b0000001-0000-0000-0000-000000000001?theme=dark', width: 1440, height: 1100, action: 'open-appsec-explanation' },
  { name: ['44', 'explainability', 'repository', 'source', 'soul.png'].join('-'), url: 'http://127.0.0.1:5173/repositories/a0000002-0000-0000-0000-000000000002?theme=dark', width: 1440, height: 1000 },
  { name: ['45', 'explainability', 'sourcecraft', 'connected.png'].join('-'), url: 'http://127.0.0.1:5173/sourcecraft?theme=dark', width: 1440, height: 900 },
  { name: ['46', 'explainability', 'sourcecraft', 'pat', 'form.png'].join('-'), url: 'http://127.0.0.1:5173/sourcecraft?disconnected=1&theme=dark', width: 1440, height: 900 },

  // 1. Leaderboard across viewports & themes
  { name: '01-leaderboard-light-1440.png', url: 'http://127.0.0.1:5173/?theme=light', width: 1440, height: 900 },
  { name: '02-leaderboard-dark-1440.png', url: 'http://127.0.0.1:5173/?theme=dark', width: 1440, height: 900 },
  { name: '03-leaderboard-1024.png', url: 'http://127.0.0.1:5173/?theme=dark', width: 1024, height: 768 },
  { name: '04-leaderboard-768.png', url: 'http://127.0.0.1:5173/?theme=dark', width: 768, height: 1024 },
  { name: '05-leaderboard-390.png', url: 'http://127.0.0.1:5173/?theme=dark', width: 390, height: 844 },
  { name: '06-leaderboard-375.png', url: 'http://127.0.0.1:5173/?theme=dark', width: 375, height: 667 },

  // 2. Repository Details across viewports & states
  { name: '07-repository-light-1440.png', url: 'http://127.0.0.1:5173/repositories/a0000001-0000-0000-0000-000000000001?theme=light', width: 1440, height: 900 },
  { name: '08-repository-dark-1440.png', url: 'http://127.0.0.1:5173/repositories/a0000001-0000-0000-0000-000000000001?theme=dark', width: 1440, height: 900 },
  { name: '09-repository-1024.png', url: 'http://127.0.0.1:5173/repositories/a0000001-0000-0000-0000-000000000001?theme=dark', width: 1024, height: 768 },
  { name: '10-repository-768.png', url: 'http://127.0.0.1:5173/repositories/a0000001-0000-0000-0000-000000000001?theme=dark', width: 768, height: 1024 },
  { name: '11-repository-390.png', url: 'http://127.0.0.1:5173/repositories/a0000001-0000-0000-0000-000000000001?theme=dark', width: 390, height: 844 },
  { name: '12-repository-375.png', url: 'http://127.0.0.1:5173/repositories/a0000001-0000-0000-0000-000000000001?theme=dark', width: 375, height: 667 },
  { name: '13-repository-nodata-1440.png', url: 'http://127.0.0.1:5173/repositories/a0000002-0000-0000-0000-000000000002?theme=dark', width: 1440, height: 900 },

  // 3. Analysis Details across viewports & states
  { name: '14-analysis-light-1440.png', url: 'http://127.0.0.1:5173/analyses/b0000001-0000-0000-0000-000000000001?theme=light', width: 1440, height: 900 },
  { name: '15-analysis-dark-1440.png', url: 'http://127.0.0.1:5173/analyses/b0000001-0000-0000-0000-000000000001?theme=dark', width: 1440, height: 900 },
  { name: '16-analysis-1024.png', url: 'http://127.0.0.1:5173/analyses/b0000001-0000-0000-0000-000000000001?theme=dark', width: 1024, height: 768 },
  { name: '17-analysis-768.png', url: 'http://127.0.0.1:5173/analyses/b0000001-0000-0000-0000-000000000001?theme=dark', width: 768, height: 1024 },
  { name: '18-analysis-390.png', url: 'http://127.0.0.1:5173/analyses/b0000001-0000-0000-0000-000000000001?theme=dark', width: 390, height: 844 },
  { name: '19-analysis-375.png', url: 'http://127.0.0.1:5173/analyses/b0000001-0000-0000-0000-000000000001?theme=dark', width: 375, height: 667 },
  { name: '20-analysis-partial-1440.png', url: 'http://127.0.0.1:5173/analyses/b0000002-0000-0000-0000-000000000002?theme=dark', width: 1440, height: 900 },
  { name: '21-analysis-failed-1440.png', url: 'http://127.0.0.1:5173/analyses/b0000005-0000-0000-0000-000000000005?theme=dark', width: 1440, height: 900 },
  { name: '22-analysis-security-nodata-1440.png', url: 'http://127.0.0.1:5173/analyses/b0000006-0000-0000-0000-000000000006?theme=dark', width: 1440, height: 900 },

  // 4. SourceCraft integration
  { name: '23-sourcecraft-connected-light-1440.png', url: 'http://127.0.0.1:5173/sourcecraft?theme=light', width: 1440, height: 900 },
  { name: '24-sourcecraft-connected-dark-1440.png', url: 'http://127.0.0.1:5173/sourcecraft?theme=dark', width: 1440, height: 900 },
  { name: '25-sourcecraft-1024.png', url: 'http://127.0.0.1:5173/sourcecraft?theme=dark', width: 1024, height: 768 },
  { name: '26-sourcecraft-768.png', url: 'http://127.0.0.1:5173/sourcecraft?theme=dark', width: 768, height: 1024 },
  { name: '27-sourcecraft-390.png', url: 'http://127.0.0.1:5173/sourcecraft?theme=dark', width: 390, height: 844 },
  { name: '28-sourcecraft-375.png', url: 'http://127.0.0.1:5173/sourcecraft?theme=dark', width: 375, height: 667 },
  { name: '29-sourcecraft-disconnected-1440.png', url: 'http://127.0.0.1:5173/sourcecraft?disconnected=1&theme=dark', width: 1440, height: 900 },

  // 5. Auth Callback & 404
  { name: '30-auth-callback-1440.png', url: 'http://127.0.0.1:5173/auth/callback?theme=dark', width: 1440, height: 900 },
  { name: '31-auth-callback-390.png', url: 'http://127.0.0.1:5173/auth/callback?theme=dark', width: 390, height: 844 },
  { name: '32-notfound-404-1440.png', url: 'http://127.0.0.1:5173/route-does-not-exist?theme=dark', width: 1440, height: 900 },
  { name: '33-notfound-404-390.png', url: 'http://127.0.0.1:5173/route-does-not-exist?theme=dark', width: 390, height: 844 },

  // 6. REAL Mobile Menu Click (Sections 15 & 19)
  {
    name: '34-mobile-nav-open-390.png',
    url: 'http://127.0.0.1:5173/?theme=dark',
    width: 390,
    height: 844,
    action: 'click-mobile-nav'
  },

  // 7. Additional Acceptance States (Section 18)
  {
    name: '35-leaderboard-empty-1440.png',
    url: 'http://127.0.0.1:5173/?language=EmptyLang&theme=dark',
    width: 1440,
    height: 900
  },
  {
    name: '36-leaderboard-error-1440.png',
    url: 'http://127.0.0.1:5173/?sort=error_trigger&theme=dark',
    width: 1440,
    height: 900
  },
  {
    name: '37-repository-loading-1440.png',
    url: 'http://127.0.0.1:5173/repositories/a0000008-0000-0000-0000-000000000008?theme=dark',
    width: 1440,
    height: 900
  },
  {
    name: '38-repository-long-slug-1440.png',
    url: 'http://127.0.0.1:5173/repositories/a0000007-0000-0000-0000-000000000007?theme=dark',
    width: 1440,
    height: 900
  },
  {
    name: '39-analysis-long-recommendation-1440.png',
    url: 'http://127.0.0.1:5173/analyses/b0000007-0000-0000-0000-000000000007?theme=dark',
    width: 1440,
    height: 900
  },
  {
    name: '40-appearance-modal-open-1440.png',
    url: 'http://127.0.0.1:5173/?theme=dark',
    width: 1440,
    height: 900,
    action: 'click-appearance'
  }
];

const acceptanceFilter = process.env.ACCEPTANCE_FILTER;
const selectedTasks = acceptanceFilter ? tasks.filter((task) => task.name.includes(acceptanceFilter)) : tasks;

let failureCount = 0;

for (const task of selectedTasks) {
  const filePath = path.join(outDir, task.name);
  console.log(`Processing ${task.name} (${task.width}x${task.height}) on ${task.url}...`);

  try {
    // 1. Set viewport metrics
    await sendCdp('Emulation.setDeviceMetricsOverride', {
      width: task.width,
      height: task.height,
      deviceScaleFactor: 1,
      mobile: task.width < 768
    });

    // 2. Navigate
    await sendCdp('Page.navigate', { url: task.url });
    await new Promise((r) => setTimeout(r, 600));

    // 3. Optional interactive action via CDP
    if (task.action === 'click-mobile-nav') {
      console.log('  -> Executing real click on .mobile-menu-btn...');
      await sendCdp('Runtime.evaluate', {
        expression: `(function() {
          const btn = document.querySelector('.mobile-menu-btn');
          if (btn) btn.click();
          return !!btn;
        })()`
      });
      await new Promise((r) => setTimeout(r, 350));
    } else if (task.action === 'click-appearance') {
      console.log('  -> Executing real click on .sc-topbar-icon-btn...');
      await sendCdp('Runtime.evaluate', {
        expression: `(function() {
          const btn = document.querySelector('.sc-topbar-icon-btn');
          if (btn) btn.click();
          return !!btn;
        })()`
      });
      await new Promise((r) => setTimeout(r, 350));
    } else if (task.action === 'open-appsec-explanation') {
      console.log('  -> Opening AppSec score explanation...');
      await sendCdp('Runtime.evaluate', {
        expression: `(function() {
          const details = [...document.querySelectorAll('details.score-explanation')]
            .find((node) => node.textContent.includes('Official SourceCraft AppSec'));
          if (details) details.open = true;
          return !!details;
        })()`
      });
      await new Promise((r) => setTimeout(r, 350));
    }

    // 4. Capture screenshot
    const shot = await sendCdp('Page.captureScreenshot', { format: 'png' });
    const buffer = Buffer.from(shot.data, 'base64');
    fs.writeFileSync(filePath, buffer);

    if (buffer.length === 0) {
      console.error(`✗ FAILED: ${task.name} has 0 bytes`);
      failureCount++;
    } else {
      console.log(`✓ ${task.name} created (${buffer.length} bytes)`);
    }
  } catch (err) {
    console.error(`✗ FAILED to capture ${task.name}:`, err.message);
    failureCount++;
  }
}

ws.close();
browserProc.kill();
vite.kill();
mockServer.close();

if (failureCount > 0) {
  console.error(`\nFATAL: Browser acceptance failed with ${failureCount} error(s).`);
  process.exit(1);
}

console.log(`\nAll ${selectedTasks.length} browser acceptance screenshots completed and verified successfully.`);
process.exit(0);
