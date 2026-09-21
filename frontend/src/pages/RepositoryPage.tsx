import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, type RepositoryDetails, type Analysis, type ApiError } from '../api/client';
import { Card } from '../components/common/Card';
import { Button, getButtonStyles } from '../components/common/Button';
import { Badge } from '../components/common/Badge';
import { ScoreDisplay } from '../components/common/ScoreDisplay';
import { ScoreCoverage } from '../components/common/ScoreCoverage';
import { AnalysisHistory } from '../components/common/AnalysisHistory';
import { AvailabilityBadge } from '../components/common/AvailabilityBadge';
import { LoadingState } from '../components/common/LoadingState';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { RecommendationCard } from '../components/common/RecommendationCard';
import {
  CATEGORY_ORDER,
  CATEGORY_LABELS,
  STATUS_CONFIG,
  getSafeExternalUrl,
} from '../utils/analysis';

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

export const RepositoryPage: React.FC = () => {
  const { id = '' } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [repo, setRepo] = useState<RepositoryDetails>();
  const [latestAnalysis, setLatestAnalysis] = useState<Analysis | null>(null);
  const [loadError, setLoadError] = useState<unknown>();
  const [startError, setStartError] = useState<unknown>();
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);

  const requestGenRef = useRef(0);

  const loadRepository = useCallback(async () => {
    const currentGen = ++requestGenRef.current;
    setLoading(true);
    setLoadError(undefined);
    setStartError(undefined);
    setRepo(undefined); // Clear stale repo from any previous repository immediately
    setLatestAnalysis(null); // Clear stale analysis from any previous repo immediately

    try {
      const repoData = await api.repository(id);
      if (requestGenRef.current !== currentGen) return;
      setRepo(repoData);

      if (repoData.latest_analysis_id) {
        try {
          const analysisData = await api.analysis(repoData.latest_analysis_id);
          if (requestGenRef.current !== currentGen) return;
          setLatestAnalysis(analysisData);
        } catch {
          if (requestGenRef.current !== currentGen) return;
          setLatestAnalysis(null);
        }
      }
      setLoading(false);
    } catch (err) {
      if (requestGenRef.current !== currentGen) return;
      setLoadError(err);
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void loadRepository();
    return () => {
      // Invalidate in-flight requests on unmount or id change
      requestGenRef.current++;
    };
  }, [loadRepository]);

  const handleStartAnalysis = async () => {
    if (starting) return; // Prevent double submit
    setStarting(true);
    setStartError(undefined);

    try {
      const run = await api.start(id);
      navigate(`/analyses/${run.id}`);
    } catch (err) {
      setStartError(err);
      setStarting(false);
    }
  };

  const hasAnalysis = Boolean(repo?.latest_analysis_id);
  const isAnalysisInProgress =
    latestAnalysis && ['queued', 'collecting', 'analyzing', 'scoring'].includes(latestAnalysis.status);
  const isReportReady =
    latestAnalysis && ['completed', 'partial'].includes(latestAnalysis.status);
  const analysisStatusMeta = latestAnalysis ? STATUS_CONFIG[latestAnalysis.status] : null;
  const safeCanonicalUrl = repo ? getSafeExternalUrl(repo.canonical_url) : null;
  const isAuthRequiredError = (startError as ApiError)?.status === 401;

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

      {loadError ? (
        <ErrorState
          error={loadError}
          title="Ошибка загрузки данных репозитория"
          onRetry={loadRepository}
        />
      ) : null}

      {startError && isAuthRequiredError ? (
        <div
          role="alert"
          style={{
            padding: 'var(--sh-space-3) var(--sh-space-4)',
            backgroundColor: 'var(--sh-health-warning-bg)',
            border: '1px solid var(--sh-health-warning-border)',
            borderRadius: 'var(--sh-radius-sm)',
            color: 'var(--sh-health-warning)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '0.75rem',
            fontSize: '0.9rem',
          }}
        >
          <span>Для запуска анализа необходимо войти через Яндекс ID.</span>
          <a
            href="/api/v1/auth/yandex/login"
            className="btn-link"
            style={{
              backgroundColor: 'var(--sh-bg-surface-elevated)',
              color: 'var(--sh-text-primary)',
              border: '1px solid var(--sh-border-default)',
              padding: '0.35rem 0.75rem',
              borderRadius: 'var(--sh-radius-sm)',
              fontSize: '0.85rem',
              fontWeight: 600,
            }}
          >
            Войти через Я ID ↗
          </a>
        </div>
      ) : startError ? (
        <ErrorState
          error={startError}
          title="Не удалось запустить анализ"
          onRetry={handleStartAnalysis}
        />
      ) : null}

      {loading && !repo && (
        <Card>
          <LoadingState message="Загрузка данных репозитория…" />
        </Card>
      )}

      {repo && (
        <>
          {/* Main Repository Summary Card */}
          <Card
            title={`${repo.organization_slug}/${repo.repository_slug}`}
            subtitle={
              safeCanonicalUrl ? (
                <a
                  href={safeCanonicalUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}
                >
                  <span>Открыть в SourceCraft</span>
                  <span aria-hidden="true">↗</span>
                </a>
              ) : (
                <span style={{ color: 'var(--sh-text-muted)' }}>{repo.canonical_url}</span>
              )
            }
            headerAction={
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '0.8rem', color: 'var(--sh-text-muted)', marginBottom: '0.2rem' }}>
                  Repo Health Score
                </div>
                <ScoreDisplay score={repo.health_score} size="lg" />
                <ScoreCoverage analysis={latestAnalysis?.id === repo.latest_analysis_id ? latestAnalysis : undefined} />
              </div>
            }
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-5)' }}>
              {/* Metadata Grid */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                  gap: 'var(--sh-space-3)',
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
                    Лайки
                  </span>
                  <span style={{ fontWeight: 600 }}>
                    {repo.likes !== null && repo.likes !== undefined ? repo.likes : '—'}
                  </span>
                </div>
                <div>
                  <span style={{ fontSize: '0.8rem', color: 'var(--sh-text-muted)', display: 'block' }}>
                    Последняя активность
                  </span>
                  <span style={{ fontWeight: 600 }}>
                    {formatLastActivity(repo.last_activity_at)}
                  </span>
                </div>
              </div>

              {/* Action Bar */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: '1rem',
                  paddingTop: 'var(--sh-space-2)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                  {isAnalysisInProgress ? (
                    <Link
                      to={`/analyses/${latestAnalysis.id}`}
                      className="btn-link"
                      style={getButtonStyles('primary', 'md')}
                    >
                      <span>Анализ выполняется · Открыть запуск</span>
                      <span aria-hidden="true">→</span>
                    </Link>
                  ) : (
                    <Button
                      variant="primary"
                      onClick={handleStartAnalysis}
                      loading={starting}
                      disabled={starting}
                    >
                      {starting
                        ? 'Запускаем анализ…'
                        : hasAnalysis
                          ? 'Повторить анализ'
                          : 'Запустить анализ'}
                    </Button>
                  )}

                  {hasAnalysis && (
                    <Link
                      to={`/analyses/${repo.latest_analysis_id}`}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.35rem',
                        fontSize: '0.88rem',
                        fontWeight: 600,
                        color: 'var(--sh-brand)',
                        padding: '0.45rem 0.85rem',
                        borderRadius: 'var(--sh-radius-sm)',
                        backgroundColor: 'var(--sh-brand-subtle)',
                        border: '1px solid var(--sh-brand-border)',
                        textDecoration: 'none',
                      }}
                    >
                      <span>Полный отчёт</span>
                      <span aria-hidden="true">→</span>
                    </Link>
                  )}

                  {isReportReady && (
                    <a
                      href={`/api/v1/analyses/${encodeURIComponent(repo.latest_analysis_id ?? '')}/report.md`}
                      download
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.35rem',
                        fontSize: '0.88rem',
                        fontWeight: 500,
                        color: 'var(--sh-text-secondary)',
                        padding: '0.45rem 0.85rem',
                        borderRadius: 'var(--sh-radius-sm)',
                        border: '1px solid var(--sh-border-default)',
                        backgroundColor: 'var(--sh-bg-surface-elevated)',
                        textDecoration: 'none',
                      }}
                    >
                      <span>⬇ Скачать отчёт (Markdown)</span>
                    </a>
                  )}
                </div>

                <span style={{ fontSize: '0.82rem', color: 'var(--sh-text-muted)' }}>
                  Для запуска анализа необходима авторизация через Яндекс ID.
                </span>
              </div>
            </div>
          </Card>

          {/* Latest Analysis Breakdown or Empty State */}
          <AnalysisHistory key={id} repositoryId={id} />
          {hasAnalysis && latestAnalysis ? (
            <Card
              title="Сводка последнего анализа"
              subtitle={
                <span style={{ fontSize: '0.85rem', color: 'var(--sh-text-muted)' }}>
                  Запуск {latestAnalysis.id.substring(0, 8)}… ·{' '}
                  {latestAnalysis.completed_at
                    ? `завершён ${new Date(latestAnalysis.completed_at).toLocaleString('ru-RU')}`
                    : `в процессе с ${new Date(latestAnalysis.queued_at).toLocaleString('ru-RU')}`}
                </span>
              }
              headerAction={
                analysisStatusMeta ? (
                  <Badge variant={analysisStatusMeta.variant}>
                    {analysisStatusMeta.label}
                  </Badge>
                ) : null
              }
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-6)' }}>
                {/* 6 Category Summary Cards */}
                <div>
                  <h3 style={{ marginBottom: 'var(--sh-space-3)' }}>Оценки по категориям</h3>
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                      gap: 'var(--sh-space-4)',
                    }}
                  >
                    {CATEGORY_ORDER.map((catKey) => {
                      const scoreData = latestAnalysis.category_scores?.[catKey];
                      const availability =
                        scoreData?.availability ?? latestAnalysis.data_coverage?.[catKey] ?? 'no_data';
                      const factsCount = scoreData?.evidence_refs?.length ?? 0;
                      return (
                        <div
                          key={catKey}
                          style={{
                            padding: 'var(--sh-space-3) var(--sh-space-4)',
                            backgroundColor: 'var(--sh-bg-base)',
                            borderRadius: 'var(--sh-radius-sm)',
                            border: '1px solid var(--sh-border-subtle)',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '0.4rem',
                          }}
                        >
                          <div
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                            }}
                          >
                            <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>
                              {CATEGORY_LABELS[catKey]}
                            </span>
                            <AvailabilityBadge availability={availability} />
                          </div>
                          <div>
                            <ScoreDisplay score={scoreData?.score ?? null} size="sm" />
                          </div>
                          {scoreData?.explanation && (
                            <p
                              style={{
                                margin: 0,
                                fontSize: '0.8rem',
                                color: 'var(--sh-text-muted)',
                                lineHeight: 1.4,
                              }}
                            >
                              {scoreData.explanation}
                            </p>
                          )}
                          {factsCount > 0 && (
                            <div style={{ fontSize: '0.78rem', color: 'var(--sh-text-muted)', marginTop: 'auto' }}>
                              Фактов в отчёте: {factsCount}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Top Recommendations Preview */}
                {latestAnalysis.recommendations && latestAnalysis.recommendations.length > 0 && (
                  <div>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        marginBottom: 'var(--sh-space-3)',
                      }}
                    >
                      <h3 style={{ margin: 0 }}>Ключевые рекомендации</h3>
                      <Link
                        to={`/analyses/${latestAnalysis.id}`}
                        style={{ fontSize: '0.88rem', fontWeight: 500 }}
                      >
                        Все рекомендации ({latestAnalysis.recommendations.length}) →
                      </Link>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-3)' }}>
                      {[...latestAnalysis.recommendations]
                        .sort((a, b) => a.priority - b.priority)
                        .slice(0, 3)
                        .map((rec) => (
                          <RecommendationCard
                            key={rec.id}
                            recommendation={rec}
                            checks={latestAnalysis.checks}
                          />
                        ))}
                    </div>
                  </div>
                )}
              </div>
            </Card>
          ) : !hasAnalysis ? (
            <EmptyState
              title="Анализ ещё не выполнялся"
              description="Для этого репозитория пока нет данных о здоровье кода и метриках. Запустите первичный анализ, чтобы получить подробный отчёт и рекомендации."
              action={
                <Button
                  variant="primary"
                  onClick={handleStartAnalysis}
                  loading={starting}
                  disabled={starting}
                >
                  {starting ? 'Запускаем анализ…' : 'Запустить анализ'}
                </Button>
              }
            />
          ) : null}
        </>
      )}
    </div>
  );
};
