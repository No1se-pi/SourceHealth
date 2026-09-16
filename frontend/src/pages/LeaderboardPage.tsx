import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, type RepositoryPage } from '../api/client';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { ScoreDisplay } from '../components/common/ScoreDisplay';
import { LoadingState } from '../components/common/LoadingState';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';

export const LeaderboardPage: React.FC = () => {
  const [page, setPage] = useState<RepositoryPage>();
  const [error, setError] = useState<unknown>();
  const [offset, setOffset] = useState(0);
  const [sort, setSort] = useState('health_score');
  const [loading, setLoading] = useState(true);

  const fetchRepositories = () => {
    let active = true;
    setLoading(true);
    setError(undefined);

    api
      .repositories(offset, sort)
      .then((value) => {
        if (active) {
          setPage(value);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (active) {
          setError(err);
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  };

  useEffect(() => {
    return fetchRepositories();
  }, [offset, sort]);

  const handleSortChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSort(e.target.value);
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
          Принцип: отсутствие данных («Нет оценки») не приравнивается к плохому репозиторию.
        </p>
      </div>

      <Card
        headerAction={
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
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
        }
        footer={
          page && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                width: '100%',
              }}
            >
              <span style={{ fontSize: '0.85rem', color: 'var(--sh-text-muted)' }}>
                Показано {page.items.length} репозиториев (смещение: {offset})
              </span>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - page.limit))}
                >
                  ← Назад
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!page.has_more}
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
            title="Репозитории пока не добавлены"
            description="В системе ещё нет открытых репозиториев для отображения в лидерборде."
          />
        ) : (
          <div className="table-responsive-wrapper">
            <ul
              style={{
                listStyle: 'none',
                padding: 0,
                margin: 0,
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              {page.items.map((repo) => (
                <li
                  key={repo.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: 'var(--sh-space-4) 0',
                    borderBottom: '1px solid var(--sh-border-subtle)',
                    gap: '1rem',
                  }}
                >
                  <div style={{ minWidth: 0 }}>
                    <Link
                      to={`/repositories/${repo.id}`}
                      style={{
                        fontSize: '1.05rem',
                        fontWeight: 600,
                        wordBreak: 'break-word',
                      }}
                    >
                      {repo.organization_slug}/{repo.repository_slug}
                    </Link>
                    {repo.language && (
                      <span
                        style={{
                          display: 'inline-block',
                          marginLeft: '0.75rem',
                          fontSize: '0.78rem',
                          color: 'var(--sh-text-muted)',
                        }}
                      >
                        {repo.language}
                      </span>
                    )}
                  </div>
                  <div style={{ flexShrink: 0 }}>
                    <ScoreDisplay score={repo.health_score} size="md" showStatusLabel />
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Card>
    </div>
  );
};
