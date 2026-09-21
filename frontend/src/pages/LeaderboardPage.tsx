import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import { api, type RepositoryPage } from '../api/client';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { ScoreDisplay } from '../components/common/ScoreDisplay';
import { LoadingState } from '../components/common/LoadingState';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { RepositoryImport } from '../components/common/RepositoryImport';

const POPULAR_LANGUAGES = [
  'TypeScript',
  'JavaScript',
  'Python',
  'Go',
  'Rust',
  'Java',
  'C++',
  'C#',
  'PHP',
  'Ruby',
  'Kotlin',
  'Swift',
];

function formatLastActivity(timestamp: string | null | undefined): string {
  if (!timestamp) return '—';
  const date = new Date(timestamp);
  if (isNaN(date.getTime())) return '—';

  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return 'Сегодня';
  if (diffDays === 1) return 'Вчера';
  if (diffDays > 1 && diffDays < 7) return `${diffDays} дн. назад`;

  return date.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

export const LeaderboardPage: React.FC = () => {
  const [page, setPage] = useState<RepositoryPage>();
  const [error, setError] = useState<unknown>();
  const [offset, setOffset] = useState(0);
  const [sort, setSort] = useState('health_score');
  const [language, setLanguage] = useState('');
  const [loading, setLoading] = useState(true);

  const requestGenRef = useRef(0);

  const fetchRepositories = useCallback(() => {
    const currentGen = ++requestGenRef.current;
    setLoading(true);
    setError(undefined);

    api
      .repositories(offset, sort, language)
      .then((value) => {
        if (requestGenRef.current === currentGen) {
          setPage(value);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (requestGenRef.current === currentGen) {
          setError(err);
          setLoading(false);
        }
      });
  }, [offset, sort, language]);

  useEffect(() => {
    fetchRepositories();
    return () => {
      // Invalidate in-flight requests on unmount or filter/sort/offset change
      requestGenRef.current++;
    };
  }, [fetchRepositories]);

  const handleSortChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSort(e.target.value);
    setOffset(0);
  };

  const handleLanguageChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setLanguage(e.target.value);
    setOffset(0);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-6)' }}>
      <div>
        <h1 style={{ marginBottom: 'var(--sh-space-2)' }}>
          Здоровье открытых репозиториев
        </h1>
        <p style={{ maxWidth: '780px', margin: 0 }}>
          Оценки основаны на проверяемых объективных фактах и метриках экосистемы SourceCraft.
          Принцип: отсутствие внешних данных («Нет данных») не приравнивается к плохому проекту.
        </p>
      </div>

      <RepositoryImport />

      <Card
        title="Лидерборд проектов"
        subtitle="Сравнение показателей качества, покрытия тестами, документации и безопасности"
        headerAction={
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '1rem',
              flexWrap: 'wrap',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <label
                htmlFor="language-filter"
                style={{
                  fontSize: '0.85rem',
                  color: 'var(--sh-text-secondary)',
                  fontWeight: 500,
                }}
              >
                Язык:
              </label>
              <select
                id="language-filter"
                value={language}
                onChange={handleLanguageChange}
                aria-label="Фильтр по языку программирования"
              >
                <option value="">Все языки</option>
                {POPULAR_LANGUAGES.map((lang) => (
                  <option key={lang} value={lang}>
                    {lang}
                  </option>
                ))}
              </select>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <label
                htmlFor="sort-select"
                style={{
                  fontSize: '0.85rem',
                  color: 'var(--sh-text-secondary)',
                  fontWeight: 500,
                }}
              >
                Сортировка:
              </label>
              <select
                id="sort-select"
                value={sort}
                onChange={handleSortChange}
                aria-label="Сортировка репозиториев"
              >
                <option value="health_score">По здоровью проекта</option>
                <option value="likes">По лайкам</option>
                <option value="last_activity">По последней активности</option>
              </select>
            </div>
          </div>
        }
        footer={
          page && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                width: '100%',
                flexWrap: 'wrap',
                gap: '1rem',
              }}
            >
              <span style={{ fontSize: '0.82rem', color: 'var(--sh-text-muted)' }}>
                Показано {page.items.length} репозиториев (смещение: {offset})
              </span>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={offset === 0 || loading}
                  onClick={() => setOffset(Math.max(0, offset - page.limit))}
                >
                  ← Назад
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!page.has_more || loading}
                  onClick={() => setOffset(offset + page.limit)}
                >
                  Далее →
                </Button>
              </div>
            </div>
          )
        }
      >
        {error ? (
          <ErrorState
            error={error}
            title="Не удалось загрузить лидерборд"
            onRetry={fetchRepositories}
          />
        ) : loading && !page ? (
          <LoadingState message="Загрузка открытых репозиториев…" />
        ) : !page || page.items.length === 0 ? (
          <EmptyState
            title="Репозитории не найдены"
            description="По выбранным фильтрам в системе не найдено репозиториев."
          />
        ) : (
          <div>
            {/* Desktop Table View */}
            <div className="table-responsive-wrapper leaderboard-desktop">
              <table className="leaderboard-table">
                <thead>
                  <tr>
                    <th scope="col" style={{ width: '3.5rem', textAlign: 'center' }}>
                      #
                    </th>
                    <th scope="col">Репозиторий SourceCraft</th>
                    <th scope="col">Язык</th>
                    <th scope="col">Лайки</th>
                    <th scope="col">Активность</th>
                    <th scope="col" style={{ textAlign: 'right' }}>
                      Health Score
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {page.items.map((repo, index) => {
                    const position = offset + index + 1;
                    return (
                      <tr key={repo.id}>
                        <td
                          style={{
                            textAlign: 'center',
                            fontFamily: 'var(--sh-font-mono)',
                            color: 'var(--sh-text-muted)',
                            fontWeight: 600,
                            fontSize: '0.88rem',
                          }}
                        >
                          {position}
                        </td>
                        <td>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                            <Link
                              to={`/repositories/${repo.id}`}
                              style={{
                                fontWeight: 600,
                                fontSize: '0.92rem',
                                color: 'var(--sh-text-primary)',
                              }}
                            >
                              {repo.organization_slug}/{repo.repository_slug}
                            </Link>
                            <span style={{ fontSize: '0.78rem', color: 'var(--sh-text-muted)', fontFamily: 'var(--sh-font-mono)' }}>
                              {repo.canonical_url}
                            </span>
                          </div>
                        </td>
                        <td style={{ color: 'var(--sh-text-secondary)', fontSize: '0.88rem' }}>
                          {repo.language ? (
                            <span
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                padding: '0.15rem 0.5rem',
                                backgroundColor: 'var(--sh-bg-surface-elevated)',
                                border: '1px solid var(--sh-border-default)',
                                borderRadius: 'var(--sh-radius-sm)',
                                fontSize: '0.8rem',
                                fontWeight: 500,
                              }}
                            >
                              {repo.language}
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td style={{ color: 'var(--sh-text-secondary)', fontSize: '0.88rem' }}>
                          {repo.likes !== null && repo.likes !== undefined ? (
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                              <span>★</span>
                              <span>{repo.likes}</span>
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td style={{ color: 'var(--sh-text-secondary)', fontSize: '0.85rem' }}>
                          {formatLastActivity(repo.last_activity_at)}
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <ScoreDisplay score={repo.health_score} size="md" />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Mobile Card List View */}
            <div className="leaderboard-mobile">
              {page.items.map((repo, index) => {
                const position = offset + index + 1;
                return (
                  <div
                    key={repo.id}
                    style={{
                      padding: 'var(--sh-space-4)',
                      backgroundColor: 'var(--sh-bg-base)',
                      borderRadius: 'var(--sh-radius-sm)',
                      border: '1px solid var(--sh-border-default)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.5rem',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: '0.5rem',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0 }}>
                        <span
                          style={{
                            fontFamily: 'var(--sh-font-mono)',
                            fontWeight: 700,
                            color: 'var(--sh-text-muted)',
                            fontSize: '0.85rem',
                          }}
                        >
                          #{position}
                        </span>
                        <Link
                          to={`/repositories/${repo.id}`}
                          style={{
                            fontWeight: 600,
                            fontSize: '0.92rem',
                            wordBreak: 'break-word',
                          }}
                        >
                          {repo.organization_slug}/{repo.repository_slug}
                        </Link>
                      </div>
                      <ScoreDisplay score={repo.health_score} size="sm" />
                    </div>

                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.85rem',
                        fontSize: '0.8rem',
                        color: 'var(--sh-text-muted)',
                        flexWrap: 'wrap',
                      }}
                    >
                      <span>Язык: {repo.language || '—'}</span>
                      <span>
                        Лайки: {repo.likes !== null && repo.likes !== undefined ? `★ ${repo.likes}` : '—'}
                      </span>
                      <span>Активность: {formatLastActivity(repo.last_activity_at)}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
};
