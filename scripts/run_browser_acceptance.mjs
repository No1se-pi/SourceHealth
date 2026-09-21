import http from 'http';
import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';

const outDir = path.resolve('docs/screenshots');
if (!fs.existsSync(outDir)) {
  fs.mkdirSync(outDir, { recursive: true });
}

// 1. Start mock server on port 8000
const mockServer = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://127.0.0.1:8000');
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Access-Control-Allow-Origin', '*');

  if (url.pathname === '/api/v1/me') {
    res.writeHead(200);
    return res.end(JSON.stringify({ id: 'sc-user-demo-42', email: 'developer@yandex.ru' }));
  }

  if (url.pathname === '/api/v1/repositories') {
    res.writeHead(200);
    return res.end(JSON.stringify({
      items: [
        {
          id: 'a0000001-0000-0000-0000-000000000001',
          organization_slug: 'demo-org',
          repository_slug: 'fast-service',
          canonical_url: 'https://sourcecraft.tech/demo-org/fast-service',
          visibility: 'public',
          health_score: 88,
          language: 'TypeScript',
          likes: 42,
          last_activity_at: '2026-09-20T14:30:00Z',
          latest_analysis_id: 'b0000001-0000-0000-0000-000000000001'
        },
        {
          id: 'a0000002-0000-0000-0000-000000000002',
          organization_slug: 'newbie-corp',
          repository_slug: 'empty-starter',
          canonical_url: 'https://sourcecraft.tech/newbie-corp/empty-starter',
          visibility: 'public',
          health_score: null, // NO_DATA fixture in leaderboard
          language: 'Python',
          likes: null,
          last_activity_at: null,
          latest_analysis_id: 'b0000006-0000-0000-0000-000000000006'
        },
        {
          id: 'a0000003-0000-0000-0000-000000000003',
          organization_slug: 'yandex-cloud',
          repository_slug: 'serverless-gate',
          canonical_url: 'https://sourcecraft.tech/yandex-cloud/serverless-gate',
          visibility: 'public',
          health_score: 94,
          language: 'Go',
          likes: 87,
          last_activity_at: '2026-09-19T18:00:00Z',
          latest_analysis_id: 'b0000001-0000-0000-0000-000000000001'
        },
        {
          id: 'a0000004-0000-0000-0000-000000000004',
          organization_slug: 'infra-tools',
          repository_slug: 'k8s-operator',
          canonical_url: 'https://sourcecraft.tech/infra-tools/k8s-operator',
          visibility: 'public',
          health_score: 62,
          language: 'Rust',
          likes: 19,
          last_activity_at: '2026-09-15T11:20:00Z',
          latest_analysis_id: 'b0000001-0000-0000-0000-000000000001'
        },
        {
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
        }
      ],
      limit: 20,
      offset: 0,
      has_more: false
    }));
  }

  // Repository details: healthy
  if (url.pathname === '/api/v1/repositories/a0000001-0000-0000-0000-000000000001') {
    res.writeHead(200);
    return res.end(JSON.stringify({
      id: 'a0000001-0000-0000-0000-000000000001',
      organization_slug: 'demo-org',
      repository_slug: 'fast-service',
      canonical_url: 'https://sourcecraft.tech/demo-org/fast-service',
      visibility: 'public',
      health_score: 88,
      language: 'TypeScript',
      likes: 42,
      last_activity_at: '2026-09-20T14:30:00Z',
      latest_analysis_id: 'b0000001-0000-0000-0000-000000000001',
      sourcecraft_id: 'sc-987654',
      default_branch: 'main',
      head_sha: 'e7e88ab123456789abcdef0123456789abcdef01'
    }));
  }

  // Repository details: NO_DATA
  if (url.pathname === '/api/v1/repositories/a0000002-0000-0000-0000-000000000002') {
    res.writeHead(200);
    return res.end(JSON.stringify({
      id: 'a0000002-0000-0000-0000-000000000002',
      organization_slug: 'newbie-corp',
      repository_slug: 'empty-starter',
      canonical_url: 'https://sourcecraft.tech/newbie-corp/empty-starter',
      visibility: 'public',
      health_score: null,
      language: 'Python',
      likes: null,
      last_activity_at: null,
      latest_analysis_id: 'b0000006-0000-0000-0000-000000000006',
      sourcecraft_id: 'sc-112233',
      default_branch: 'main',
      head_sha: 'abcdef1234567890abcdef1234567890abcdef12'
    }));
  }

  if (url.pathname.startsWith('/api/v1/repositories/a0000001-0000-0000-0000-000000000001/analyses')) {
    res.writeHead(200);
    return res.end(JSON.stringify({
      items: [
        {
          id: 'b0000001-0000-0000-0000-000000000001',
          repository_id: 'a0000001-0000-0000-0000-000000000001',
          profile: 'mvp-v1',
          status: 'completed',
          trigger: 'manual',
          queued_at: '2026-09-20T14:28:00Z',
          completed_at: '2026-09-20T14:28:45Z',
          health_score: 88
        }
      ],
      limit: 10,
      offset: 0,
      has_more: false
    }));
  }

  if (url.pathname.startsWith('/api/v1/repositories/a0000002-0000-0000-0000-000000000002/analyses')) {
    res.writeHead(200);
    return res.end(JSON.stringify({
      items: [
        {
          id: 'b0000006-0000-0000-0000-000000000006',
          repository_id: 'a0000002-0000-0000-0000-000000000002',
          profile: 'unconfigured-v1',
          status: 'completed',
          trigger: 'manual',
          queued_at: '2026-09-20T16:10:00Z',
          completed_at: '2026-09-20T16:10:15Z',
          health_score: null
        }
      ],
      limit: 10,
      offset: 0,
      has_more: false
    }));
  }

  // Analysis b0000001: Completed full healthy analysis (88/100)
  if (url.pathname === '/api/v1/analyses/b0000001-0000-0000-0000-000000000001') {
    res.writeHead(200);
    return res.end(JSON.stringify({
      id: 'b0000001-0000-0000-0000-000000000001',
      repository_id: 'a0000001-0000-0000-0000-000000000001',
      profile: 'mvp-v1',
      status: 'completed',
      trigger: 'manual',
      queued_at: '2026-09-20T14:28:00Z',
      started_at: '2026-09-20T14:28:02Z',
      completed_at: '2026-09-20T14:28:45Z',
      head_sha: 'e7e88ab123456789abcdef0123456789abcdef01',
      health_score: 88,
      scoring_policy_version: 'v1',
      analyzer_contract_version: 'v1',
      error_code: null,
      score_coverage: {
        nominal_weight_percent: 100,
        scored_categories: 6,
        unscored_categories: [],
        partial_categories: []
      },
      category_scores: {
        documentation: {
          category: 'documentation',
          score: 85,
          availability: 'available',
          explanation: 'Наличие полного README, документации API и руководства по развёртыванию.',
          evidence_refs: ['ev-doc-1']
        },
        cicd: {
          category: 'cicd',
          score: 92,
          availability: 'available',
          explanation: 'CI пайплайн настроен и успешно проходит в основной ветке (120/120 тестов).',
          evidence_refs: ['ev-ci-1']
        },
        security: {
          category: 'security',
          score: 80,
          availability: 'available',
          explanation: 'AppSec сканирование SourceCraft завершено: обнаружено 1 предупреждение средней важности.',
          evidence_refs: ['ev-sec-1']
        },
        activity: {
          category: 'activity',
          score: 90,
          availability: 'available',
          explanation: 'Регулярные коммиты и активность команды: 38 коммитов за последние 30 дней.',
          evidence_refs: ['ev-act-1']
        },
        issues: {
          category: 'issues',
          score: 88,
          availability: 'available',
          explanation: 'Низкое время отклика на тикеты (медиана 18 ч), 14 закрытых задач за месяц.',
          evidence_refs: ['ev-iss-1']
        },
        code_health: {
          category: 'code_health',
          score: 91,
          availability: 'available',
          explanation: 'Отсутствие грубых запахов кода и дублирования по результатам локального SAST анализа.',
          evidence_refs: ['ev-ch-1']
        }
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
        {
          id: 'rec-1',
          category: 'security',
          title: 'Устранить риск SQL-инъекции в поисковом запросе',
          description: 'SourceCraft AppSec выявил риск SQL-инъекции (CWE-89) при обработке параметра search.',
          priority: 1,
          evidence_refs: ['ev-sec-1'],
          suggested_action: 'Использовать параметризованный SQL-запрос в src/api/search.py',
          expected_impact: '+5 Health Score'
        },
        {
          id: 'rec-2',
          category: 'documentation',
          title: 'Добавить диаграмму архитектуры компонентов',
          description: 'В README рекомендуется включить краткую схему взаимодействия микросервисов.',
          priority: 2,
          evidence_refs: ['ev-doc-1'],
          suggested_action: 'Создать docs/architecture.md и добавить ссылку в основной README',
          expected_impact: '+2 Health Score'
        }
      ],
      checks: {
        documentation: {
          analyzer: 'docs_analyzer',
          status: 'ok',
          availability: 'available',
          source: 'repository_tree',
          category: 'documentation',
          analyzer_version: '1.0.0',
          contract_version: '1.0.0',
          metrics: { readme_words: 1200 },
          findings: [],
          metadata: {},
          error: null,
          evidence: [
            {
              id: 'ev-doc-1',
              source: 'docs_analyzer',
              type: 'file_presence',
              reference: 'README.md',
              summary: 'README.md найден в корне (1200 слов, разделы Quickstart и API)',
              url: 'https://sourcecraft.tech/demo-org/fast-service/src/branch/main/README.md',
              location: 'README.md:1',
              timestamp: '2026-09-20T14:28:10Z'
            }
          ]
        },
        security: {
          analyzer: 'sourcecraft_appsec',
          status: 'ok',
          availability: 'available',
          source: 'sourcecraft_appsec',
          category: 'security',
          analyzer_version: '1.0.0',
          contract_version: '1.0.0',
          metrics: { vulnerabilities_found: 1, severity_critical: 0, severity_high: 0, severity_medium: 1, severity_low: 0 },
          findings: [
            { finding_id: 'SCS-ADV-2026-01', rule_id: 'CWE-89', severity: 'medium', title: 'SQL injection risk in search query' }
          ],
          metadata: {},
          error: null,
          evidence: [
            {
              id: 'ev-sec-1',
              source: 'sourcecraft_appsec',
              type: 'vulnerability',
              reference: 'finding/sc-appsec-9042',
              summary: 'SourceCraft AppSec: обнаружено предупреждение средней критичности (CWE-89, SQL injection risk)',
              url: 'https://sourcecraft.tech/demo-org/fast-service/security/findings/9042',
              location: 'src/api/search.py:42',
              timestamp: '2026-09-20T14:28:15Z'
            }
          ]
        },
        cicd: {
          analyzer: 'cicd_analyzer',
          status: 'ok',
          availability: 'available',
          source: 'sourcecraft_ci',
          category: 'cicd',
          analyzer_version: '1.0.0',
          contract_version: '1.0.0',
          metrics: { builds_total: 45, success_rate: 0.98 },
          findings: [],
          metadata: {},
          error: null,
          evidence: [
            {
              id: 'ev-ci-1',
              source: 'sourcecraft_ci',
              type: 'pipeline_run',
              reference: 'pipeline/build-and-test',
              summary: 'CI пайплайн успешно завершён на ветке main (120/120 тестов)',
              url: 'https://sourcecraft.tech/demo-org/fast-service/pipelines/42',
              location: '.sourcecraft/workflows/ci.yml:1',
              timestamp: '2026-09-20T14:28:12Z'
            }
          ]
        },
        activity: {
          analyzer: 'git_activity',
          status: 'ok',
          availability: 'available',
          source: 'git_log',
          category: 'activity',
          analyzer_version: '1.0.0',
          contract_version: '1.0.0',
          metrics: { commits_30d: 38, active_contributors: 4 },
          findings: [],
          metadata: {},
          error: null,
          evidence: [
            {
              id: 'ev-act-1',
              source: 'git_log',
              type: 'commit_frequency',
              reference: 'commits/recent',
              summary: '38 коммитов от 4 разработчиков за последние 30 дней',
              url: 'https://sourcecraft.tech/demo-org/fast-service/commits',
              location: null,
              timestamp: '2026-09-20T14:28:18Z'
            }
          ]
        },
        issues: {
          analyzer: 'issue_tracker',
          status: 'ok',
          availability: 'available',
          source: 'sourcecraft_issues',
          category: 'issues',
          analyzer_version: '1.0.0',
          contract_version: '1.0.0',
          metrics: { open_issues: 3, closed_issues_30d: 14, median_close_hours: 18 },
          findings: [],
          metadata: {},
          error: null,
          evidence: [
            {
              id: 'ev-iss-1',
              source: 'sourcecraft_issues',
              type: 'issue_metrics',
              reference: 'issues/stats',
              summary: 'Медианное время закрытия 18 часов, 14 закрытых тикетов',
              url: 'https://sourcecraft.tech/demo-org/fast-service/issues',
              location: null,
              timestamp: '2026-09-20T14:28:19Z'
            }
          ]
        },
        code_health: {
          analyzer: 'sast',
          status: 'ok',
          availability: 'available',
          source: 'sourcehealth_local',
          category: 'code_health',
          analyzer_version: '1.0.0',
          contract_version: '1.0.0',
          metrics: { rules_checked: 24, issues_found: 0 },
          findings: [],
          metadata: {},
          error: null,
          evidence: [
            {
              id: 'ev-ch-1',
              source: 'sourcehealth_local',
              type: 'code_smell',
              reference: 'src/core/engine.py',
              summary: 'Локальный SAST SourceHealth: критических дефектов и запахов кода не обнаружено',
              url: null,
              location: 'src/core/engine.py:1',
              timestamp: '2026-09-20T14:28:20Z'
            }
          ]
        }
      }
    }));
  }

  // Analysis b0000002: Partial analysis state
  if (url.pathname === '/api/v1/analyses/b0000002-0000-0000-0000-000000000002') {
    res.writeHead(200);
    return res.end(JSON.stringify({
      id: 'b0000002-0000-0000-0000-000000000002',
      repository_id: 'a0000001-0000-0000-0000-000000000001',
      profile: 'mvp-v1',
      status: 'partial',
      trigger: 'manual',
      queued_at: '2026-09-20T15:00:00Z',
      started_at: '2026-09-20T15:00:02Z',
      completed_at: '2026-09-20T15:00:30Z',
      head_sha: 'abcdef1234567890abcdef1234567890abcdef12',
      health_score: null,
      scoring_policy_version: 'v1',
      analyzer_contract_version: 'v1',
      error_code: null,
      category_scores: {
        documentation: {
          category: 'documentation',
          score: 50,
          availability: 'partial',
          explanation: 'Обнаружен только краткий README.',
          evidence_refs: []
        },
        security: {
          category: 'security',
          score: null,
          availability: 'not_configured',
          explanation: 'SourceCraft AppSec сканер не подключён для данного проекта.',
          evidence_refs: []
        }
      },
      data_coverage: {
        documentation: 'partial',
        security: 'not_configured'
      },
      recommendations: [],
      checks: {},
      score_coverage: {
        nominal_weight_percent: 25,
        scored_categories: 1,
        unscored_categories: ['security'],
        partial_categories: ['documentation']
      }
    }));
  }

  // Analysis b0000005: Failed state
  if (url.pathname === '/api/v1/analyses/b0000005-0000-0000-0000-000000000005') {
    res.writeHead(200);
    return res.end(JSON.stringify({
      id: 'b0000005-0000-0000-0000-000000000005',
      repository_id: 'a0000001-0000-0000-0000-000000000001',
      profile: 'mvp-v1',
      status: 'failed',
      trigger: 'manual',
      queued_at: '2026-09-20T16:05:00Z',
      started_at: '2026-09-20T16:05:02Z',
      completed_at: '2026-09-20T16:05:15Z',
      head_sha: 'e7e88ab123456789abcdef0123456789abcdef01',
      health_score: null,
      scoring_policy_version: 'v1',
      analyzer_contract_version: 'v1',
      error_code: 'SOURCE_CRAFT_TIMEOUT',
      category_scores: {},
      data_coverage: {},
      recommendations: [],
      checks: {},
      score_coverage: {
        nominal_weight_percent: 0,
        scored_categories: 0,
        unscored_categories: [],
        partial_categories: []
      }
    }));
  }

  // Analysis b0000006: NO_DATA state with Security NO_DATA
  if (url.pathname === '/api/v1/analyses/b0000006-0000-0000-0000-000000000006') {
    res.writeHead(200);
    return res.end(JSON.stringify({
      id: 'b0000006-0000-0000-0000-000000000006',
      repository_id: 'a0000002-0000-0000-0000-000000000002',
      profile: 'unconfigured-v1',
      status: 'completed',
      trigger: 'manual',
      queued_at: '2026-09-20T16:10:00Z',
      started_at: '2026-09-20T16:10:02Z',
      completed_at: '2026-09-20T16:10:15Z',
      head_sha: 'abcdef1234567890abcdef1234567890abcdef12',
      health_score: null, // NO_DATA != 0
      scoring_policy_version: 'v1',
      analyzer_contract_version: 'v1',
      error_code: null,
      category_scores: {
        documentation: {
          category: 'documentation',
          score: null,
          availability: 'no_data',
          explanation: 'Файлы документации не найдены в репозитории.',
          evidence_refs: []
        },
        cicd: {
          category: 'cicd',
          score: null,
          availability: 'not_configured',
          explanation: 'Конфигурации CI/CD пайплайнов не обнаружены.',
          evidence_refs: []
        },
        security: {
          category: 'security',
          score: null,
          availability: 'not_configured',
          explanation: 'SourceCraft AppSec проверки не настроены в данном проекте.',
          evidence_refs: []
        },
        activity: {
          category: 'activity',
          score: null,
          availability: 'no_data',
          explanation: 'Недостаточно данных об активности за период анализа.',
          evidence_refs: []
        },
        issues: {
          category: 'issues',
          score: null,
          availability: 'not_configured',
          explanation: 'Трекер задач не подключён.',
          evidence_refs: []
        },
        code_health: {
          category: 'code_health',
          score: null,
          availability: 'no_data',
          explanation: 'Метрики исходного кода не рассчитаны.',
          evidence_refs: []
        }
      },
      data_coverage: {
        documentation: 'no_data',
        cicd: 'not_configured',
        security: 'not_configured',
        activity: 'no_data',
        issues: 'not_configured',
        code_health: 'no_data'
      },
      recommendations: [],
      checks: {},
      score_coverage: {
        nominal_weight_percent: 0,
        scored_categories: 0,
        unscored_categories: ['documentation', 'cicd', 'security', 'activity', 'issues', 'code_health'],
        partial_categories: []
      }
    }));
  }

  if (url.pathname.endsWith('/report.md')) {
    res.setHeader('Content-Type', 'text/markdown; charset=utf-8');
    res.writeHead(200);
    return res.end('# Отчёт о здоровье репозитория demo-org/fast-service\n\nHealth Score: 88/100\n');
  }

  // SourceCraft Connection status: check referer for disconnected state
  if (url.pathname === '/api/v1/sourcecraft/connection') {
    const referer = req.headers.referer || '';
    if (referer.includes('disconnected=1')) {
      res.writeHead(200);
      return res.end(JSON.stringify({ connected: false, expires_in: 0 }));
    }
    res.writeHead(200);
    return res.end(JSON.stringify({ connected: true, expires_in: 1800 }));
  }

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

mockServer.listen(8000, '127.0.0.1', () => {
  console.log('Mock API server listening on http://127.0.0.1:8000');
});

// 2. Start Vite preview on port 5173
const vite = spawn('npm.cmd', ['run', 'preview', '--', '--port', '5173'], {
  cwd: path.resolve('frontend'),
  shell: true,
  stdio: 'pipe'
});

// Wait until Vite preview responds on 5173
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
    // wait and retry
  }
  await new Promise((r) => setTimeout(r, 400));
}

if (!viteReady) {
  console.error('FATAL: Vite preview failed to start within timeout');
  vite.kill();
  mockServer.close();
  process.exit(1);
}

const edgePath = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const chromePath = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const browserExe = fs.existsSync(edgePath) ? edgePath : chromePath;

if (!fs.existsSync(browserExe)) {
  console.error('FATAL: Browser executable not found at Edge or Chrome path');
  vite.kill();
  mockServer.close();
  process.exit(1);
}

console.log('Using browser:', browserExe);

// Full Matrix: 5 viewports (1440, 1024, 768, 390, 375) across key pages + fixture states
const tasks = [
  // 1. Leaderboard across viewports & themes
  { name: '01-leaderboard-light-1440.png', url: 'http://127.0.0.1:5173/?theme=light', width: 1440, height: 900 },
  { name: '02-leaderboard-dark-1440.png', url: 'http://127.0.0.1:5173/?theme=dark', width: 1440, height: 900 },
  { name: '03-leaderboard-1024.png', url: 'http://127.0.0.1:5173/?theme=light', width: 1024, height: 768 },
  { name: '04-leaderboard-768.png', url: 'http://127.0.0.1:5173/?theme=light', width: 768, height: 1024 },
  { name: '05-leaderboard-390.png', url: 'http://127.0.0.1:5173/?theme=light', width: 390, height: 844 },
  { name: '06-leaderboard-375.png', url: 'http://127.0.0.1:5173/?theme=light', width: 375, height: 667 },

  // 2. Repository Details across viewports & themes + NO_DATA state
  { name: '07-repository-light-1440.png', url: 'http://127.0.0.1:5173/repositories/a0000001-0000-0000-0000-000000000001?theme=light', width: 1440, height: 900 },
  { name: '08-repository-dark-1440.png', url: 'http://127.0.0.1:5173/repositories/a0000001-0000-0000-0000-000000000001?theme=dark', width: 1440, height: 900 },
  { name: '09-repository-1024.png', url: 'http://127.0.0.1:5173/repositories/a0000001-0000-0000-0000-000000000001?theme=light', width: 1024, height: 768 },
  { name: '10-repository-768.png', url: 'http://127.0.0.1:5173/repositories/a0000001-0000-0000-0000-000000000001?theme=light', width: 768, height: 1024 },
  { name: '11-repository-390.png', url: 'http://127.0.0.1:5173/repositories/a0000001-0000-0000-0000-000000000001?theme=light', width: 390, height: 844 },
  { name: '12-repository-375.png', url: 'http://127.0.0.1:5173/repositories/a0000001-0000-0000-0000-000000000001?theme=light', width: 375, height: 667 },
  { name: '13-repository-nodata-1440.png', url: 'http://127.0.0.1:5173/repositories/a0000002-0000-0000-0000-000000000002?theme=light', width: 1440, height: 900 },

  // 3. Analysis Details across viewports & states (completed, partial, failed, NO_DATA)
  { name: '14-analysis-light-1440.png', url: 'http://127.0.0.1:5173/analyses/b0000001-0000-0000-0000-000000000001?theme=light', width: 1440, height: 900 },
  { name: '15-analysis-dark-1440.png', url: 'http://127.0.0.1:5173/analyses/b0000001-0000-0000-0000-000000000001?theme=dark', width: 1440, height: 900 },
  { name: '16-analysis-1024.png', url: 'http://127.0.0.1:5173/analyses/b0000001-0000-0000-0000-000000000001?theme=light', width: 1024, height: 768 },
  { name: '17-analysis-768.png', url: 'http://127.0.0.1:5173/analyses/b0000001-0000-0000-0000-000000000001?theme=light', width: 768, height: 1024 },
  { name: '18-analysis-390.png', url: 'http://127.0.0.1:5173/analyses/b0000001-0000-0000-0000-000000000001?theme=light', width: 390, height: 844 },
  { name: '19-analysis-375.png', url: 'http://127.0.0.1:5173/analyses/b0000001-0000-0000-0000-000000000001?theme=light', width: 375, height: 667 },
  { name: '20-analysis-partial-1440.png', url: 'http://127.0.0.1:5173/analyses/b0000002-0000-0000-0000-000000000002?theme=light', width: 1440, height: 900 },
  { name: '21-analysis-failed-1440.png', url: 'http://127.0.0.1:5173/analyses/b0000005-0000-0000-0000-000000000005?theme=light', width: 1440, height: 900 },
  { name: '22-analysis-security-nodata-1440.png', url: 'http://127.0.0.1:5173/analyses/b0000006-0000-0000-0000-000000000006?theme=light', width: 1440, height: 900 },

  // 4. SourceCraft integration across viewports & states
  { name: '23-sourcecraft-connected-light-1440.png', url: 'http://127.0.0.1:5173/sourcecraft?theme=light', width: 1440, height: 900 },
  { name: '24-sourcecraft-connected-dark-1440.png', url: 'http://127.0.0.1:5173/sourcecraft?theme=dark', width: 1440, height: 900 },
  { name: '25-sourcecraft-1024.png', url: 'http://127.0.0.1:5173/sourcecraft?theme=light', width: 1024, height: 768 },
  { name: '26-sourcecraft-768.png', url: 'http://127.0.0.1:5173/sourcecraft?theme=light', width: 768, height: 1024 },
  { name: '27-sourcecraft-390.png', url: 'http://127.0.0.1:5173/sourcecraft?theme=light', width: 390, height: 844 },
  { name: '28-sourcecraft-375.png', url: 'http://127.0.0.1:5173/sourcecraft?theme=light', width: 375, height: 667 },
  { name: '29-sourcecraft-disconnected-1440.png', url: 'http://127.0.0.1:5173/sourcecraft?disconnected=1&theme=light', width: 1440, height: 900 },

  // 5. Auth Callback & 404
  { name: '30-auth-callback-1440.png', url: 'http://127.0.0.1:5173/auth/callback?theme=light', width: 1440, height: 900 },
  { name: '31-auth-callback-390.png', url: 'http://127.0.0.1:5173/auth/callback?theme=light', width: 390, height: 844 },
  { name: '32-notfound-404-1440.png', url: 'http://127.0.0.1:5173/route-does-not-exist?theme=light', width: 1440, height: 900 },
  { name: '33-notfound-404-390.png', url: 'http://127.0.0.1:5173/route-does-not-exist?theme=light', width: 390, height: 844 },

  // 6. Mobile Navigation Open View
  { name: '34-mobile-nav-open-390.png', url: 'http://127.0.0.1:5173/?mobileNav=1&theme=light', width: 390, height: 844 }
];

let failureCount = 0;

for (const task of tasks) {
  const filePath = path.join(outDir, task.name);
  console.log(`Capturing ${task.name} (${task.width}x${task.height}) from ${task.url}...`);
  await new Promise((resolve) => {
    const proc = spawn(browserExe, [
      '--headless=new',
      '--disable-gpu',
      '--hide-scrollbars',
      `--window-size=${task.width},${task.height}`,
      '--virtual-time-budget=3000',
      `--screenshot=${filePath}`,
      task.url
    ]);
    proc.on('close', (code) => {
      if (code !== 0) {
        console.error(`Process exited with non-zero code ${code} for ${task.name}`);
        failureCount++;
      }
      resolve();
    });
  });

  if (fs.existsSync(filePath)) {
    const stats = fs.statSync(filePath);
    if (stats.size === 0) {
      console.error(`✗ FAILED: ${task.name} has 0 bytes file size`);
      failureCount++;
    } else {
      console.log(`✓ ${task.name} created (${stats.size} bytes)`);
    }
  } else {
    console.error(`✗ FAILED to create ${task.name}`);
    failureCount++;
  }
}

vite.kill();
mockServer.close();

if (failureCount > 0) {
  console.error(`\nFATAL: Browser acceptance failed with ${failureCount} error(s).`);
  process.exit(1);
}

console.log(`\nAll ${tasks.length} browser acceptance screenshots completed and verified successfully.`);
process.exit(0);
