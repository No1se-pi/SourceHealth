import http from 'http';
import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';

const outDir = path.resolve('docs/screenshots');
if (!fs.existsSync(outDir)) {
  fs.mkdirSync(outDir, { recursive: true });
}

const MOCK_PORT = 8005;

// 1. Start mock server on port 8005
const mockServer = http.createServer((req, res) => {
  const url = new URL(req.url, `http://127.0.0.1:${MOCK_PORT}`);
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Access-Control-Allow-Origin', '*');

  if (url.pathname === '/api/v1/me') {
    res.writeHead(200);
    return res.end(JSON.stringify({ id: 'sc-user-demo-42' }));
  }

  // 1.1 Leaderboard
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
          id: 'a0000007-0000-0000-0000-000000000007',
          organization_slug: 'very-long-enterprise-organization-holding-corp',
          repository_slug: 'mission-critical-microservice-super-extended-repository-slug-v2',
          canonical_url: 'https://sourcecraft.dev/very-long-enterprise-organization-holding-corp/mission-critical-microservice-super-extended-repository-slug-v2',
          visibility: 'public',
          health_score: 85,
          language: 'TypeScript',
          likes: 512,
          last_activity_at: '2026-09-21T10:00:00Z',
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

  // 1.2 Repository details: healthy
  if (url.pathname === '/api/v1/repositories/a0000001-0000-0000-0000-000000000001') {
    res.writeHead(200);
    return res.end(JSON.stringify({
      id: 'a0000001-0000-0000-0000-000000000001',
      organization_slug: 'demo-org',
      repository_slug: 'fast-service',
      canonical_url: 'https://sourcecraft.tech/demo-org/fast-service',
      visibility: 'public',
      default_branch: 'main',
      health_score: 88,
      language: 'TypeScript',
      likes: 42,
      last_activity_at: '2026-09-20T14:30:00Z',
      latest_analysis_id: 'b0000001-0000-0000-0000-000000000001',
      created_at: '2026-01-10T08:00:00Z',
      updated_at: '2026-09-20T14:30:00Z'
    }));
  }

  // 1.3 Repository details: NO_DATA
  if (url.pathname === '/api/v1/repositories/a0000002-0000-0000-0000-000000000002') {
    res.writeHead(200);
    return res.end(JSON.stringify({
      id: 'a0000002-0000-0000-0000-000000000002',
      organization_slug: 'newbie-corp',
      repository_slug: 'empty-starter',
      canonical_url: 'https://sourcecraft.tech/newbie-corp/empty-starter',
      visibility: 'public',
      default_branch: 'main',
      health_score: null,
      language: 'Python',
      likes: 0,
      last_activity_at: null,
      latest_analysis_id: null,
      created_at: '2026-09-01T12:00:00Z',
      updated_at: '2026-09-01T12:00:00Z'
    }));
  }

  // 1.4 Repository details: long slug
  if (url.pathname === '/api/v1/repositories/a0000007-0000-0000-0000-000000000007') {
    res.writeHead(200);
    return res.end(JSON.stringify({
      id: 'a0000007-0000-0000-0000-000000000007',
      organization_slug: 'very-long-enterprise-organization-holding-corp',
      repository_slug: 'mission-critical-microservice-super-extended-repository-slug-v2',
      canonical_url: 'https://sourcecraft.dev/very-long-enterprise-organization-holding-corp/mission-critical-microservice-super-extended-repository-slug-v2',
      visibility: 'public',
      default_branch: 'main',
      health_score: 85,
      language: 'TypeScript',
      likes: 512,
      last_activity_at: '2026-09-21T10:00:00Z',
      latest_analysis_id: 'b0000001-0000-0000-0000-000000000001',
      created_at: '2026-02-01T08:00:00Z',
      updated_at: '2026-09-21T10:00:00Z'
    }));
  }

  // 1.5 Repository details: loading fixture (never resolves within client timeout)
  if (url.pathname === '/api/v1/repositories/a0000008-0000-0000-0000-000000000008') {
    // Keep connection open without writing response
    return;
  }

  // 1.6 Repository analyses list
  if (url.pathname.endsWith('/analyses') && req.method === 'GET') {
    res.writeHead(200);
    return res.end(JSON.stringify({
      items: [
        {
          id: 'b0000001-0000-0000-0000-000000000001',
          repository_id: 'a0000001-0000-0000-0000-000000000001',
          status: 'completed',
          score: 88,
          created_at: '2026-09-20T14:35:00Z',
          completed_at: '2026-09-20T14:36:12Z'
        }
      ],
      limit: 10,
      offset: 0,
      has_more: false
    }));
  }

  // 1.7 Analysis: completed healthy
  if (url.pathname === '/api/v1/analyses/b0000001-0000-0000-0000-000000000001') {
    res.writeHead(200);
    return res.end(JSON.stringify({
      id: 'b0000001-0000-0000-0000-000000000001',
      repository_id: 'a0000001-0000-0000-0000-000000000001',
      status: 'completed',
      score: 88,
      category_scores: {
        documentation: { score: 92, weight: 15, availability: 'available', evidence_refs: ['ev-doc-1'] },
        cicd: { score: 85, weight: 15, availability: 'available', evidence_refs: ['ev-ci-1'] },
        security: { score: 80, weight: 25, availability: 'available', evidence_refs: ['ev-sec-1'] },
        activity: { score: 95, weight: 15, availability: 'available', evidence_refs: ['ev-act-1'] },
        issues: { score: 78, weight: 15, availability: 'available', evidence_refs: ['ev-iss-1'] },
        code_health: { score: 90, weight: 15, availability: 'available', evidence_refs: ['ev-ch-1'] }
      },
      evidence: [
        { id: 'ev-doc-1', category: 'documentation', source: 'readme_parser', description: 'README.md найден (324 строки, документация API полная)' },
        { id: 'ev-ci-1', category: 'cicd', source: 'sourcecraft_ci', description: 'CI пайплайн настроен и проходит успешно в 98% сборок' },
        { id: 'ev-sec-1', category: 'security', source: 'sourcecraft_appsec', description: 'Уязвимостей высокой и критической степени не обнаружено' },
        { id: 'ev-act-1', category: 'activity', source: 'git_log', description: '34 коммита за последние 30 дней от 4 активных авторов' },
        { id: 'ev-iss-1', category: 'issues', source: 'sourcecraft_issues', description: 'Среднее время закрытия задач составляет 2.4 дня' },
        { id: 'ev-ch-1', category: 'code_health', source: 'sourcehealth_local', description: 'SAST анализ: дефектов и запахов кода не обнаружено' }
      ],
      recommendations: [
        {
          id: 'rec-1',
          title: 'Добавьте тесты для критических модулей',
          description: 'Покрытие тестами в модуле auth составляет 64%. Рекомендуется поднять до 80%.',
          priority: 'P2',
          effort: 'medium',
          action: 'Написать модульные тесты для auth/provider.go',
          evidence_refs: ['ev-ch-1']
        }
      ],
      checks: [
        { analyzer: 'readme_parser', category: 'documentation', status: 'pass', source: 'readme_parser' },
        { analyzer: 'sourcecraft_appsec', category: 'security', status: 'pass', source: 'sourcecraft_appsec' }
      ],
      created_at: '2026-09-20T14:35:00Z',
      completed_at: '2026-09-20T14:36:12Z'
    }));
  }

  // 1.8 Analysis: partial
  if (url.pathname === '/api/v1/analyses/b0000002-0000-0000-0000-000000000002') {
    res.writeHead(200);
    return res.end(JSON.stringify({
      id: 'b0000002-0000-0000-0000-000000000002',
      repository_id: 'a0000001-0000-0000-0000-000000000001',
      status: 'partial',
      score: 72,
      category_scores: {
        documentation: { score: 90, weight: 15, availability: 'available', evidence_refs: [] },
        cicd: { score: 0, weight: 15, availability: 'no_data', evidence_refs: [] },
        security: { score: 85, weight: 25, availability: 'available', evidence_refs: [] },
        activity: { score: 65, weight: 15, availability: 'available', evidence_refs: [] },
        issues: { score: 0, weight: 15, availability: 'no_data', evidence_refs: [] },
        code_health: { score: 75, weight: 15, availability: 'available', evidence_refs: [] }
      },
      evidence: [],
      recommendations: [],
      checks: [],
      created_at: '2026-09-20T12:00:00Z',
      completed_at: '2026-09-20T12:01:00Z'
    }));
  }

  // 1.9 Analysis: failed
  if (url.pathname === '/api/v1/analyses/b0000005-0000-0000-0000-000000000005') {
    res.writeHead(200);
    return res.end(JSON.stringify({
      id: 'b0000005-0000-0000-0000-000000000005',
      repository_id: 'a0000001-0000-0000-0000-000000000001',
      status: 'failed',
      score: null,
      category_scores: {},
      evidence: [],
      recommendations: [],
      checks: [],
      created_at: '2026-09-20T10:00:00Z',
      completed_at: '2026-09-20T10:00:15Z'
    }));
  }

  // 1.10 Analysis: Security NO_DATA
  if (url.pathname === '/api/v1/analyses/b0000006-0000-0000-0000-000000000006') {
    res.writeHead(200);
    return res.end(JSON.stringify({
      id: 'b0000006-0000-0000-0000-000000000006',
      repository_id: 'a0000002-0000-0000-0000-000000000002',
      status: 'completed',
      score: 82,
      category_scores: {
        documentation: { score: 85, weight: 15, availability: 'available', evidence_refs: [] },
        cicd: { score: 80, weight: 15, availability: 'available', evidence_refs: [] },
        security: { score: 0, weight: 25, availability: 'no_data', evidence_refs: [] },
        activity: { score: 80, weight: 15, availability: 'available', evidence_refs: [] },
        issues: { score: 75, weight: 15, availability: 'available', evidence_refs: [] },
        code_health: { score: 88, weight: 15, availability: 'available', evidence_refs: [] }
      },
      evidence: [],
      recommendations: [],
      checks: [],
      created_at: '2026-09-19T08:00:00Z',
      completed_at: '2026-09-19T08:01:00Z'
    }));
  }

  // 1.11 Analysis: Long recommendation
  if (url.pathname === '/api/v1/analyses/b0000007-0000-0000-0000-000000000007') {
    res.writeHead(200);
    return res.end(JSON.stringify({
      id: 'b0000007-0000-0000-0000-000000000007',
      repository_id: 'a0000007-0000-0000-0000-000000000007',
      status: 'completed',
      score: 85,
      category_scores: {
        documentation: { score: 88, weight: 15, availability: 'available', evidence_refs: ['ev-1'] },
        cicd: { score: 82, weight: 15, availability: 'available', evidence_refs: ['ev-2'] },
        security: { score: 75, weight: 25, availability: 'available', evidence_refs: ['ev-3'] },
        activity: { score: 90, weight: 15, availability: 'available', evidence_refs: ['ev-4'] },
        issues: { score: 85, weight: 15, availability: 'available', evidence_refs: ['ev-5'] },
        code_health: { score: 92, weight: 15, availability: 'available', evidence_refs: ['ev-6'] }
      },
      evidence: [
        { id: 'ev-1', category: 'documentation', source: 'readme_parser', description: 'Полная техническая спецификация API с примерами вызовов' }
      ],
      recommendations: [
        {
          id: 'rec-long-1',
          title: 'Комплексная реструктуризация инфраструктурных пайплайнов и политик безопасности контейнерных сред',
          description: 'Данный репозиторий содержит критические точки входа для внешних распределённых микросервисов. Настоятельно рекомендуется полностью переработать конфигурацию CI/CD пайплайнов, внедрить строгие политики сканирования базовых образов OCI на этапе предварительного коммита, настроить автоматическую проверку зависимостей и контроль версий через Dependabot/Snyk, а также активировать сигнатурную верификацию артефактов в защищённом реестре SourceCraft Registry.',
          priority: 'P1',
          effort: 'high',
          action: 'Развернуть расширенный набор анализаторов безопасности SourceCraft AppSec и локальных линтеров',
          evidence_refs: ['ev-1']
        }
      ],
      checks: [],
      created_at: '2026-09-21T09:00:00Z',
      completed_at: '2026-09-21T09:01:30Z'
    }));
  }

  // 1.12 SourceCraft connection
  if (url.pathname === '/api/v1/sourcecraft/connection') {
    if (url.searchParams.get('disconnected') === '1') {
      res.writeHead(200);
      return res.end(JSON.stringify({ connected: false }));
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

mockServer.listen(MOCK_PORT, '127.0.0.1', () => {
  console.log(`Mock API server listening on http://127.0.0.1:${MOCK_PORT}`);
});

// 2. Start Vite preview on port 5173
const vite = spawn('npm.cmd', ['run', 'preview', '--', '--port', '5173'], {
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

const edgePath = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const chromePath = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const browserExe = fs.existsSync(edgePath) ? edgePath : chromePath;

if (!fs.existsSync(browserExe)) {
  console.error('FATAL: Browser executable not found');
  vite.kill();
  mockServer.close();
  process.exit(1);
}

console.log('Starting Edge with CDP remote debugging on port 9222...');
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

// Full Acceptance Matrix: 40 screenshots
const tasks = [
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

let failureCount = 0;

for (const task of tasks) {
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

console.log(`\nAll ${tasks.length} browser acceptance screenshots completed and verified successfully.`);
process.exit(0);
