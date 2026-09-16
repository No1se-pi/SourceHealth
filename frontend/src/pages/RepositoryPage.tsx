import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, type RepositoryDetails } from '../api/client';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { ScoreDisplay } from '../components/common/ScoreDisplay';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';

export const RepositoryPage: React.FC = () => {
  const { id = '' } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [repo, setRepo] = useState<RepositoryDetails>();
  const [error, setError] = useState<unknown>();
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);

  const fetchRepository = () => {
    let active = true;
    setLoading(true);
    setError(undefined);

    api
      .repository(id)
      .then((data) => {
        if (active) {
          setRepo(data);
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
    return fetchRepository();
  }, [id]);

  const handleStartAnalysis = async () => {
    setStarting(true);
    setError(undefined);
    try {
      const run = await api.start(id);
      navigate(`/analyses/${run.id}`);
    } catch (err) {
      setError(err);
    } finally {
      setStarting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-6)' }}>
      <div>
        <Link
          to="/"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.4rem',
            fontSize: '0.9rem',
            color: 'var(--sh-text-muted)',
            marginBottom: 'var(--sh-space-3)',
          }}
        >
          ← Назад к лидерборду
        </Link>
      </div>

      {error ? (
        <ErrorState
          error={error}
          title="Ошибка загрузки или запуска анализа"
          onRetry={fetchRepository}
        />
      ) : null}

      {loading && !repo && (
        <Card>
          <LoadingState message="Загрузка данных репозитория…" />
        </Card>
      )}

      {repo && (
        <Card
          title={`${repo.organization_slug}/${repo.repository_slug}`}
          subtitle={
            <a
              href={repo.canonical_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}
            >
              <span>Открыть в SourceCraft</span>
              <span aria-hidden="true">↗</span>
            </a>
          }
          headerAction={
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '0.8rem', color: 'var(--sh-text-muted)', marginBottom: '0.2rem' }}>
                Repo Health Score
              </div>
              <ScoreDisplay score={repo.health_score} size="lg" showStatusLabel />
            </div>
          }
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-5)' }}>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: 'var(--sh-space-4)',
                backgroundColor: 'var(--sh-bg-base)',
                padding: 'var(--sh-space-4)',
                borderRadius: 'var(--sh-radius-sm)',
                border: '1px solid var(--sh-border-subtle)',
              }}
            >
              <div>
                <span style={{ fontSize: '0.8rem', color: 'var(--sh-text-muted)', display: 'block' }}>
                  Основная ветка
                </span>
                <span style={{ fontFamily: 'var(--sh-font-mono)', fontWeight: 600 }}>
                  {repo.default_branch || 'не указана'}
                </span>
              </div>
              <div>
                <span style={{ fontSize: '0.8rem', color: 'var(--sh-text-muted)', display: 'block' }}>
                  Язык проекта
                </span>
                <span style={{ fontWeight: 600 }}>
                  {repo.language || 'Не определён'}
                </span>
              </div>
              <div>
                <span style={{ fontSize: '0.8rem', color: 'var(--sh-text-muted)', display: 'block' }}>
                  Последний анализ
                </span>
                {repo.latest_analysis_id ? (
                  <Link to={`/analyses/${repo.latest_analysis_id}`}>
                    Перейти к отчёту →
                  </Link>
                ) : (
                  <span style={{ color: 'var(--sh-text-muted)' }}>Ещё не проводился</span>
                )}
              </div>
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '1rem',
                paddingTop: 'var(--sh-space-3)',
              }}
            >
              <div>
                <Button
                  variant="primary"
                  onClick={handleStartAnalysis}
                  loading={starting}
                  disabled={starting}
                >
                  {starting ? 'Запускаем анализ…' : 'Запустить анализ'}
                </Button>
              </div>
              <span style={{ fontSize: '0.85rem', color: 'var(--sh-text-muted)' }}>
                Для запуска анализа необходима авторизация через Яндекс ID.
              </span>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
};
