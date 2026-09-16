import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import { api, type RepositoryPage } from '../api/client';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { ScoreDisplay } from '../components/common/ScoreDisplay';
import { LoadingState } from '../components/common/LoadingState';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';

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
        <p style={{ maxWidth: '720px', margin: 0 }}>
          Оценки основаны на объективных фактах и проверяемых метриках SourceCraft.
          Принцип: отсутствие данных («Нет данных») не приравнивается к плохому репозиторию.
        </p>
      </div>

      <Card
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
                  fontSize: '0.88rem',
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
                  fontSize: '0.88rem',
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
              <span style={{ fontSize: '0.85rem', color: 'var(--sh-text-muted)' }}>
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
                    <th scope="col" style={{ width: '4rem', textAlign: 'center' }}>
                      #
                    </th>
                    <th scope="col">Репозиторий</th>
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
                            fontSize: '0.9rem',
                          }}
                        >
                          {position}
                        </td>
                        <td>
                          <Link
                            to={`/repositories/${repo.id}`}
                            style={{
                              fontWeight: 600,
                              fontSize: '0.95rem',
                              color: 'var(--sh-text-primary)',
                            }}
                          >
                            {repo.organization_slug}/{repo.repository_slug}
                          </Link>
                        </td>
                        <td style={{ color: 'var(--sh-text-secondary)', fontSize: '0.9rem' }}>
                          {repo.language || '—'}
                        </td>
                        <td style={{ color: 'var(--sh-text-secondary)', fontSize: '0.9rem' }}>
                          {repo.likes !== null && repo.likes !== undefined ? repo.likes : '—'}
                        </td>
                        <td style={{ color: 'var(--sh-text-secondary)', fontSize: '0.9rem' }}>
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
                      padding: 'var(--sh-space-3) var(--sh-space-4)',
                      backgroundColor: 'var(--sh-bg-base)',
                      borderRadius: 'var(--sh-radius-sm)',
                      border: '1px solid var(--sh-border-subtle)',
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
                            fontSize: '0.95rem',
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
                        gap: '1rem',
                        fontSize: '0.82rem',
                        color: 'var(--sh-text-muted)',
                        flexWrap: 'wrap',
                      }}
                    >
                      <span>Язык: {repo.language || '—'}</span>
                      <span>
                        Лайки: {repo.likes !== null && repo.likes !== undefined ? repo.likes : '—'}
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
