import React, { useMemo, useState } from 'react';
import { Card } from '../components/common/Card';
import { PageContainer } from '../components/common/PageContainer';
import { Badge } from '../components/common/Badge';
import { CopyButton } from '../components/common/CopyButton';
import { usePageTitle } from '../utils/usePageTitle';

export const DevelopersPage: React.FC = () => {
  usePageTitle('Для разработчиков');
  const [repository, setRepository] = useState('organization/repository');
  const [badgeFormat, setBadgeFormat] = useState<'markdown' | 'html'>('markdown');
  const [codeTab, setCodeTab] = useState<'curl' | 'js' | 'python'>('curl');
  const [badgePreviewError, setBadgePreviewError] = useState(false);

  const trimmedRepo = repository.trim();
  const parts = trimmedRepo.split('/');
  const isValidRepo = parts.length === 2 && parts.every((p) => /^[A-Za-z0-9_-]{1,128}$/.test(p));

  const origin = typeof window !== 'undefined' ? window.location.origin : 'https://sourcehealth.tech';
  const badgeUrl = isValidRepo ? `${origin}/api/v1/badges/${parts[0]}/${parts[1]}.svg` : '';

  const badgeSnippet = useMemo(() => {
    if (!isValidRepo) return '';
    if (badgeFormat === 'markdown') {
      return `![SourceHealth](${badgeUrl})`;
    }
    return `<a href="${origin}/repositories"><img src="${badgeUrl}" alt="SourceHealth" /></a>`;
  }, [isValidRepo, badgeFormat, badgeUrl, origin]);

  const endpoints = [
    {
      method: 'GET',
      path: '/api/v1/repositories',
      description: 'Каталог и поиск репозиториев (фильтры, сортировка, пагинация)',
    },
    {
      method: 'GET',
      path: '/api/v1/catalog/stats',
      description: 'Агрегированная статистика каталога (распределение, средний Health)',
    },
    {
      method: 'GET',
      path: '/api/v1/repositories/{id}',
      description: 'Детальная карточка репозитория и последний официальный Health',
    },
    {
      method: 'GET',
      path: '/api/v1/repositories/{id}/integrity',
      description: 'Сигналы проверки устойчивости рейтинга и аудит аномалий',
    },
    {
      method: 'GET',
      path: '/api/v1/publicity/repositories/{id}',
      description: 'Метаданные для шеринга, ссылки на отчет и бейджи',
    },
    {
      method: 'GET',
      path: '/api/v1/compare?repository_id={id1}&repository_id={id2}',
      description: 'Сравнение от 2 до 4 проектов по категориям и метрикам',
    },
    {
      method: 'GET',
      path: '/api/v1/repositories/{id}/analyses',
      description: 'История запусков анализа (до 100 записей)',
    },
    {
      method: 'GET',
      path: '/api/v1/repositories/{id}/analyses/latest',
      description: 'Сводка последнего завершённого запуска анализа',
    },
    {
      method: 'GET',
      path: '/api/v1/analyses/{id}',
      description: 'Полный отчёт анализа: категории, проверки и доказательства',
    },
    {
      method: 'GET',
      path: '/api/v1/analyses/{id}/report.md',
      description: 'Экспорт полного отчёта в формате Markdown',
    },
    {
      method: 'GET',
      path: '/api/v1/badges/{org}/{repo}.svg',
      description: 'Динамический SVG-бейдж официального Health для README',
    },
  ];

  const codeSnippets = {
    curl: `curl -s "${origin}/api/v1/repositories?sort=health_score&order=desc"`,
    js: `// JavaScript (fetch)
const response = await fetch("${origin}/api/v1/repositories?sort=health_score&order=desc");
if (!response.ok) {
  throw new Error(\`HTTP \${response.status}\`);
}
const data = await response.json();
console.log("Каталог:", data.items);`,
    python: `# Python (requests)
import requests

url = "${origin}/api/v1/repositories"
params = {"sort": "health_score", "order": "desc"}

response = requests.get(url, params=params, timeout=10)
response.raise_for_status()
data = response.json()

print(f"Загружено {len(data['items'])} репозиториев")`,
  };

  const exampleResponse = `{
  "id": "c1f7a09d-83b6-4c28-98e6-d98c25781a50",
  "organization_slug": "sourcecraft",
  "repository_slug": "platform",
  "canonical_url": "https://sourcecraft.dev/sourcecraft/platform",
  "visibility": "public",
  "health_score": 82.4,
  "language": "Python",
  "likes": 42,
  "last_activity_at": "2026-09-20T14:30:00Z",
  "latest_analysis_id": "b0000001-0000-0000-0000-000000000001",
  "score_preview": null,
  "default_branch": "main",
  "head_sha": "a1b2c3d4e5f67890abcdef1234567890abcdef12"
}`;

  return (
    <PageContainer>
      <div style={{ marginBottom: 'var(--sh-space-4)' }}>
        <h1 style={{ margin: '0 0 var(--sh-space-1) 0' }}>SourceHealth для разработчиков</h1>
        <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--sh-text-secondary)' }}>
          Публичный REST API, документация и Health-бейджи для интеграции в CI/CD и README проектов платформы SourceCraft.
        </p>
      </div>

      {/* API Semantics Callout */}
      <div
        style={{
          marginBottom: 'var(--sh-space-4)',
          padding: 'var(--sh-space-4)',
          backgroundColor: 'var(--sh-bg-surface)',
          borderRadius: 'var(--sh-radius-sm)',
          border: '1px solid var(--sh-border-subtle)',
        }}
      >
        <div style={{ fontWeight: 600, fontSize: '0.95rem', marginBottom: 'var(--sh-space-2)' }}>
          Семантика и принципы REST API SourceHealth
        </div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: 'var(--sh-space-3)',
            fontSize: '0.84rem',
            color: 'var(--sh-text-secondary)',
            lineHeight: 1.5,
          }}
        >
          <div>
            <strong>• NO_DATA ≠ 0:</strong>{' '}
            <code>health_score: null</code> означает, что официальный Health не рассчитан из-за нехватки данных. Это не штрафной ноль.
          </div>
          <div>
            <strong>• Source Soul ≠ Health:</strong>{' '}
            Эвристическая оценка активности Source Soul не является официальным Health и никогда не выводится в бейджах.
          </div>
          <div>
            <strong>• GET не запускает анализ:</strong>{' '}
            Все GET-запросы строго read-only и безопасны для регулярного мониторинга без создания фоновых задач.
          </div>
          <div>
            <strong>• Безопасность из AppSec:</strong>{' '}
            Баллы по Security подтверждаются исключительно официальным модулем SourceCraft AppSec.
          </div>
          <div>
            <strong>• Сравнение 2–4 проектов:</strong>{' '}
            Эндпоинт <code>/api/v1/compare</code> принимает от 2 до 4 ID проектов для сопоставления.
          </div>
          <div>
            <strong>• Фильтры через Query URL:</strong>{' '}
            Параметры каталога и поиска полностью детерминированы и передаются через стандартные HTTP query string.
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 'var(--sh-space-4)' }}>
        {/* Public REST API Card */}
        <Card
          title="Публичный REST API"
          headerAction={
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              <a
                href="/api/docs"
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  padding: '0.3rem 0.65rem',
                  borderRadius: 'var(--sh-radius-sm)',
                  backgroundColor: 'var(--sh-brand-subtle)',
                  color: 'var(--sh-brand)',
                  border: '1px solid var(--sh-brand-border)',
                  textDecoration: 'none',
                }}
              >
                Swagger / Docs ↗
              </a>
              <a
                href="/api/openapi.json"
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  fontSize: '0.82rem',
                  fontWeight: 500,
                  padding: '0.3rem 0.65rem',
                  borderRadius: 'var(--sh-radius-sm)',
                  backgroundColor: 'var(--sh-bg-base)',
                  color: 'var(--sh-text-secondary)',
                  border: '1px solid var(--sh-border-default)',
                  textDecoration: 'none',
                }}
              >
                OpenAPI JSON ↗
              </a>
            </div>
          }
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-4)' }}>
            {/* Code Examples with Tabs */}
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                <div style={{ display: 'flex', gap: '0.35rem' }}>
                  <button
                    type="button"
                    onClick={() => setCodeTab('curl')}
                    style={{
                      padding: '0.25rem 0.6rem',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      borderRadius: 'var(--sh-radius-sm)',
                      border: '1px solid var(--sh-border-default)',
                      backgroundColor: codeTab === 'curl' ? 'var(--sh-brand-subtle)' : 'var(--sh-bg-base)',
                      color: codeTab === 'curl' ? 'var(--sh-brand)' : 'var(--sh-text-secondary)',
                      cursor: 'pointer',
                    }}
                  >
                    cURL
                  </button>
                  <button
                    type="button"
                    onClick={() => setCodeTab('js')}
                    style={{
                      padding: '0.25rem 0.6rem',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      borderRadius: 'var(--sh-radius-sm)',
                      border: '1px solid var(--sh-border-default)',
                      backgroundColor: codeTab === 'js' ? 'var(--sh-brand-subtle)' : 'var(--sh-bg-base)',
                      color: codeTab === 'js' ? 'var(--sh-brand)' : 'var(--sh-text-secondary)',
                      cursor: 'pointer',
                    }}
                  >
                    JavaScript
                  </button>
                  <button
                    type="button"
                    onClick={() => setCodeTab('python')}
                    style={{
                      padding: '0.25rem 0.6rem',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      borderRadius: 'var(--sh-radius-sm)',
                      border: '1px solid var(--sh-border-default)',
                      backgroundColor: codeTab === 'python' ? 'var(--sh-brand-subtle)' : 'var(--sh-bg-base)',
                      color: codeTab === 'python' ? 'var(--sh-brand)' : 'var(--sh-text-secondary)',
                      cursor: 'pointer',
                    }}
                  >
                    Python
                  </button>
                </div>
                <CopyButton
                  value={codeSnippets[codeTab]}
                  label="Скопировать пример"
                  copiedLabel="Пример скопирован!"
                  size="sm"
                />
              </div>

              <pre
                style={{
                  margin: 0,
                  padding: 'var(--sh-space-3)',
                  backgroundColor: 'var(--sh-bg-base)',
                  borderRadius: 'var(--sh-radius-sm)',
                  border: '1px solid var(--sh-border-subtle)',
                  overflowX: 'auto',
                  fontFamily: 'var(--sh-font-mono)',
                  fontSize: '0.82rem',
                  lineHeight: 1.45,
                }}
              >
                <code>{codeSnippets[codeTab]}</code>
              </pre>
            </div>

            {/* Endpoints List */}
            <div>
              <h4 style={{ margin: '0 0 var(--sh-space-2) 0', fontSize: '0.9rem' }}>
                Публичные эндпоинты
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {endpoints.map((ep) => (
                  <div
                    key={ep.path}
                    style={{
                      padding: '0.55rem 0.8rem',
                      backgroundColor: 'var(--sh-bg-base)',
                      borderRadius: 'var(--sh-radius-sm)',
                      border: '1px solid var(--sh-border-subtle)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      flexWrap: 'wrap',
                      gap: '0.5rem',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                      <Badge variant="success">{ep.method}</Badge>
                      <code style={{ fontSize: '0.82rem', fontWeight: 600, fontFamily: 'var(--sh-font-mono)' }}>
                        {ep.path}
                      </code>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ fontSize: '0.78rem', color: 'var(--sh-text-muted)' }}>
                        {ep.description}
                      </span>
                      <CopyButton value={ep.path} label="" title="Скопировать путь эндпоинта" size="sm" />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Example JSON response */}
            <details
              style={{
                backgroundColor: 'var(--sh-bg-base)',
                borderRadius: 'var(--sh-radius-sm)',
                border: '1px solid var(--sh-border-subtle)',
                padding: 'var(--sh-space-3)',
              }}
            >
              <summary style={{ cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem' }}>
                Пример ответа репозитория (JSON)
              </summary>
              <pre
                style={{
                  margin: 'var(--sh-space-2) 0 0 0',
                  padding: 'var(--sh-space-2)',
                  fontSize: '0.78rem',
                  fontFamily: 'var(--sh-font-mono)',
                  overflowX: 'auto',
                }}
              >
                <code>{exampleResponse}</code>
              </pre>
            </details>
          </div>
        </Card>

        {/* README Badge Card */}
        <Card title="README бейдж">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-4)' }}>
            <div>
              <label
                htmlFor="badge-repo-input"
                style={{ display: 'block', fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.35rem' }}
              >
                Репозиторий (organization/repository)
              </label>
              <input
                id="badge-repo-input"
                type="text"
                value={repository}
                onChange={(e) => {
                  setRepository(e.target.value);
                  setBadgePreviewError(false);
                }}
                placeholder="organization/repository"
                style={{
                  width: '100%',
                  padding: '0.45rem 0.75rem',
                  fontSize: '0.9rem',
                  borderRadius: 'var(--sh-radius-sm)',
                  border: `1px solid ${!isValidRepo && trimmedRepo ? 'var(--sh-health-danger-border, #ef4444)' : 'var(--sh-border-default)'}`,
                  backgroundColor: 'var(--sh-bg-base)',
                  color: 'var(--sh-text-primary)',
                  boxSizing: 'border-box',
                }}
              />
              {!isValidRepo && trimmedRepo ? (
                <span style={{ fontSize: '0.8rem', color: 'var(--sh-health-danger, #ef4444)', marginTop: '0.25rem', display: 'block' }}>
                  Используйте формат organization/repository (буквы, цифры, дефис, подчёркивание).
                </span>
              ) : null}
            </div>

            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                type="button"
                onClick={() => setBadgeFormat('markdown')}
                style={{
                  padding: '0.35rem 0.75rem',
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  borderRadius: 'var(--sh-radius-sm)',
                  border: '1px solid var(--sh-border-default)',
                  backgroundColor: badgeFormat === 'markdown' ? 'var(--sh-brand-subtle)' : 'var(--sh-bg-base)',
                  color: badgeFormat === 'markdown' ? 'var(--sh-brand)' : 'var(--sh-text-secondary)',
                  cursor: 'pointer',
                }}
              >
                Markdown
              </button>
              <button
                type="button"
                onClick={() => setBadgeFormat('html')}
                style={{
                  padding: '0.35rem 0.75rem',
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  borderRadius: 'var(--sh-radius-sm)',
                  border: '1px solid var(--sh-border-default)',
                  backgroundColor: badgeFormat === 'html' ? 'var(--sh-brand-subtle)' : 'var(--sh-bg-base)',
                  color: badgeFormat === 'html' ? 'var(--sh-brand)' : 'var(--sh-text-secondary)',
                  cursor: 'pointer',
                }}
              >
                HTML
              </button>
            </div>

            {/* Direct Badge URL */}
            {isValidRepo && (
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.3rem' }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--sh-text-muted)' }}>
                    Прямая ссылка на SVG-бейдж
                  </span>
                  <CopyButton value={badgeUrl} label="Скопировать URL" size="sm" />
                </div>
                <input
                  type="text"
                  readOnly
                  value={badgeUrl}
                  style={{
                    width: '100%',
                    fontSize: '0.8rem',
                    fontFamily: 'var(--sh-font-mono)',
                    padding: '0.35rem 0.6rem',
                    borderRadius: 'var(--sh-radius-sm)',
                    border: '1px solid var(--sh-border-default)',
                    backgroundColor: 'var(--sh-bg-base)',
                    color: 'var(--sh-text-primary)',
                    boxSizing: 'border-box',
                  }}
                />
              </div>
            )}

            {/* Snippet */}
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--sh-text-muted)' }}>
                  Код для вставки в {badgeFormat === 'markdown' ? 'README.md' : 'HTML'}
                </span>
                {isValidRepo && (
                  <CopyButton
                    value={badgeSnippet}
                    label="Скопировать код"
                    copiedLabel="Код скопирован!"
                    size="sm"
                  />
                )}
              </div>
              <pre
                style={{
                  margin: 0,
                  padding: 'var(--sh-space-3)',
                  backgroundColor: 'var(--sh-bg-base)',
                  borderRadius: 'var(--sh-radius-sm)',
                  border: '1px solid var(--sh-border-subtle)',
                  overflowX: 'auto',
                  fontFamily: 'var(--sh-font-mono)',
                  fontSize: '0.82rem',
                }}
              >
                <code>{isValidRepo ? badgeSnippet : 'Введите корректный путь репозитория'}</code>
              </pre>
            </div>

            {/* Preview */}
            <div>
              <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--sh-text-muted)', display: 'block', marginBottom: '0.4rem' }}>
                Предпросмотр бейджа
              </span>
              <div
                style={{
                  padding: 'var(--sh-space-4)',
                  backgroundColor: 'var(--sh-bg-base)',
                  borderRadius: 'var(--sh-radius-sm)',
                  border: '1px solid var(--sh-border-subtle)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '1rem',
                }}
              >
                {isValidRepo ? (
                  !badgePreviewError ? (
                    <img
                      alt="SourceHealth badge preview"
                      src={`/api/v1/badges/${parts[0]}/${parts[1]}.svg`}
                      style={{ maxWidth: '100%', height: '28px' }}
                      onError={() => setBadgePreviewError(true)}
                    />
                  ) : (
                    <div style={{ fontSize: '0.82rem', color: 'var(--sh-health-warning, #f59e0b)' }}>
                      ⚠ Бейдж пока недоступен или проект ещё не анализировался в системе.
                    </div>
                  )
                ) : (
                  <span style={{ fontSize: '0.82rem', color: 'var(--sh-text-muted)' }}>
                    Введите репозиторий для предпросмотра
                  </span>
                )}
              </div>
            </div>

            <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--sh-text-muted)', lineHeight: 1.45 }}>
              ℹ️ <strong>Важно:</strong> Бейдж отображает исключительно официальный Health score (0–100). Оценка Source Soul и предварительные результаты в бейдже никогда не публикуются.
            </p>
          </div>
        </Card>
      </div>
    </PageContainer>
  );
};
