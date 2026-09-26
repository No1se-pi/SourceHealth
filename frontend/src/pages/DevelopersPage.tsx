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

  const trimmedRepo = repository.trim();
  const parts = trimmedRepo.split('/');
  const isValidRepo = parts.length === 2 && parts.every((p) => /^[A-Za-z0-9_-]{1,128}$/.test(p));

  const origin = typeof window !== 'undefined' ? window.location.origin : 'https://sourcehealth.tech';
  const badgeUrl = isValidRepo ? `${origin}/api/v1/badges/${parts[0]}/${parts[1]}.svg` : '';
  const repoPageUrl = isValidRepo ? `${origin}/repositories/${parts[0]}/${parts[1]}` : '';

  const badgeSnippet = useMemo(() => {
    if (!isValidRepo) return '';
    if (badgeFormat === 'markdown') {
      return `[![SourceHealth](${badgeUrl})](${repoPageUrl})`;
    }
    return `<a href="${repoPageUrl}"><img src="${badgeUrl}" alt="SourceHealth" /></a>`;
  }, [isValidRepo, badgeFormat, badgeUrl, repoPageUrl]);

  const endpoints = [
    {
      method: 'GET',
      path: '/api/v1/repositories',
      description: 'Список публичных репозиториев с пагинацией и сортировкой',
    },
    {
      method: 'GET',
      path: '/api/v1/repositories/{id}',
      description: 'Детальная карточка репозитория и последний Health',
    },
    {
      method: 'GET',
      path: '/api/v1/repositories/{id}/analyses/latest',
      description: 'Сводка последнего завершённого запуска анализа',
    },
    {
      method: 'GET',
      path: '/api/v1/analyses/{id}',
      description: 'Полный отчёт анализа: категории, проверки и факты',
    },
    {
      method: 'GET',
      path: '/api/v1/analyses/{id}/report.md',
      description: 'Экспорт полного отчёта в формате Markdown',
    },
    {
      method: 'GET',
      path: '/api/v1/badges/{organization}/{repository}.svg',
      description: 'Динамический SVG-бейдж официального Health для README',
    },
  ];

  const curlExample = `curl -s "${origin}/api/v1/repositories?sort=health_score"`;

  const exampleResponse = `{
  "id": "c1f7a09d-83b6-4c28-98e6-d98c25781a50",
  "organization_slug": "sourcecraft",
  "repository_slug": "platform",
  "health_score": 82.4,
  "data_coverage": {
    "documentation": "available",
    "testing": "available",
    "security": "available"
  },
  "default_branch": "main",
  "language": "Python"
}`;

  return (
    <PageContainer>
      <div style={{ marginBottom: 'var(--sh-space-4)' }}>
        <h1 style={{ margin: '0 0 var(--sh-space-1) 0' }}>SourceHealth для разработчиков</h1>
        <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--sh-text-secondary)' }}>
          Публичный REST API и Health-бейджи для интеграции в CI/CD и README проектов платформы SourceCraft.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 'var(--sh-space-4)' }}>
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
                Swagger / API Docs ↗
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
            <div
              style={{
                padding: 'var(--sh-space-3) var(--sh-space-4)',
                backgroundColor: 'var(--sh-bg-base)',
                borderRadius: 'var(--sh-radius-sm)',
                border: '1px solid var(--sh-border-subtle)',
                fontSize: '0.86rem',
                color: 'var(--sh-text-secondary)',
                lineHeight: 1.5,
              }}
            >
              <div>
                <strong>Принцип API:</strong> <code>health_score: null</code> означает, что официальный Health пока не рассчитан. Это не ноль и не штраф.
              </div>
              <div style={{ marginTop: '0.35rem', fontSize: '0.82rem', color: 'var(--sh-text-muted)' }}>
                Публичные GET-запросы не запускают анализ автоматически и безопасны для регулярного мониторинга.
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--sh-text-muted)' }}>
                  Пример запроса через curl
                </span>
                <CopyButton value={curlExample} label="Скопировать curl" size="sm" />
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
                <code>{curlExample}</code>
              </pre>
            </div>

            <div>
              <h4 style={{ margin: '0 0 var(--sh-space-2) 0', fontSize: '0.9rem' }}>Эндпоинты</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {endpoints.map((ep) => (
                  <div
                    key={ep.path}
                    style={{
                      padding: '0.6rem 0.85rem',
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
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
                      <Badge variant="success">{ep.method}</Badge>
                      <code style={{ fontSize: '0.85rem', fontWeight: 600, fontFamily: 'var(--sh-font-mono)' }}>
                        {ep.path}
                      </code>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ fontSize: '0.8rem', color: 'var(--sh-text-muted)' }}>
                        {ep.description}
                      </span>
                      <CopyButton value={ep.path} label="" title="Скопировать путь эндпоинта" size="sm" />
                    </div>
                  </div>
                ))}
              </div>
            </div>

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
                onChange={(e) => setRepository(e.target.value)}
                placeholder="organization/repository"
                style={{
                  width: '100%',
                  padding: '0.45rem 0.75rem',
                  fontSize: '0.9rem',
                  borderRadius: 'var(--sh-radius-sm)',
                  border: `1px solid ${!isValidRepo && trimmedRepo ? 'var(--sh-health-danger-border)' : 'var(--sh-border-default)'}`,
                  backgroundColor: 'var(--sh-bg-base)',
                  color: 'var(--sh-text-primary)',
                  boxSizing: 'border-box',
                }}
              />
              {!isValidRepo && trimmedRepo ? (
                <span style={{ fontSize: '0.8rem', color: 'var(--sh-health-danger)', marginTop: '0.25rem', display: 'block' }}>
                  Используйте формат organization/repository (только буквы, цифры, дефис, подчёркивание).
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
                  <img
                    alt="SourceHealth badge preview"
                    src={`/api/v1/badges/${parts[0]}/${parts[1]}.svg`}
                    style={{ maxWidth: '100%', height: '28px' }}
                    onError={(e) => {
                      (e.target as HTMLElement).style.display = 'none';
                    }}
                  />
                ) : (
                  <span style={{ fontSize: '0.82rem', color: 'var(--sh-text-muted)' }}>
                    Введите репозиторий для предпросмотра
                  </span>
                )}
              </div>
            </div>

            <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--sh-text-muted)', lineHeight: 1.4 }}>
              ℹ️ Бейдж отображает только официальный Health score (0–100). Оценка Source Soul в бейдже не публикуется.
            </p>
          </div>
        </Card>
      </div>
    </PageContainer>
  );
};
