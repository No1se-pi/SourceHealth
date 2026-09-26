import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, type Analysis } from '../api/client';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { ScoreDisplay } from '../components/common/ScoreDisplay';
import { ScoreCoverage } from '../components/common/ScoreCoverage';
import { AvailabilityBadge } from '../components/common/AvailabilityBadge';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';
import { RecommendationCard } from '../components/common/RecommendationCard';
import { EvidenceList } from '../components/common/EvidenceList';
import { SourceSoul } from '../components/common/SourceSoul';
import { CategoryDetails } from '../components/common/CategoryDetails';
import { Breadcrumbs } from '../components/common/Breadcrumbs';
import { CopyButton } from '../components/common/CopyButton';
import { usePageTitle } from '../utils/usePageTitle';
import { formatDateTime, formatDurationSeconds, humanizeErrorCode } from '../utils/formatters';
import {
  CATEGORY_ORDER,
  CATEGORY_LABELS,
  STATUS_CONFIG,
  getSafeExternalUrl,
} from '../utils/analysis';

export const AnalysisPage: React.FC = () => {
  const { id = '' } = useParams<{ id: string }>();
  const [run, setRun] = useState<Analysis>();
  const [error, setError] = useState<unknown>();
  const [loading, setLoading] = useState(true);

  usePageTitle(run ? `Анализ ${run.id.substring(0, 8)}` : 'Анализ');

  const requestGenRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const pollAnalysis = useCallback(async (expectedGen: number) => {
    try {
      const value = await api.analysis(id);
      if (requestGenRef.current !== expectedGen) return;

      setRun(value);
      setError(undefined);
      setLoading(false);

      const isTerminal = ['completed', 'partial', 'failed'].includes(value.status);
      if (!isTerminal) {
        timerRef.current = setTimeout(() => {
          if (requestGenRef.current === expectedGen) {
            void pollAnalysis(expectedGen);
          }
        }, 2000);
      }
    } catch (err) {
      if (requestGenRef.current !== expectedGen) return;
      setError(err);
      setLoading(false);
      // Do NOT auto-retry on error to prevent spamming the backend
    }
  }, [id]);

  useEffect(() => {
    const currentGen = ++requestGenRef.current;
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    setRun(undefined); // Clear stale run from previous analysis immediately
    setLoading(true);
    setError(undefined);

    void pollAnalysis(currentGen);

    return () => {
      // Invalidate current generation and clear pending timer on unmount or id change
      requestGenRef.current++;
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [pollAnalysis]);

  const handleRetry = () => {
    const currentGen = ++requestGenRef.current;
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    setError(undefined);
    setLoading(true);
    void pollAnalysis(currentGen);
  };

  const statusMeta = run ? STATUS_CONFIG[run.status] : null;

  const missingCategories = run
    ? CATEGORY_ORDER.filter((catKey) => {
        const scoreData = run.category_scores?.[catKey];
        const availability = scoreData?.availability ?? run.data_coverage?.[catKey] ?? 'no_data';
        return availability === 'no_data';
      })
    : [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-6)' }}>
      <Breadcrumbs
        items={[
          { label: 'Рейтинг', href: '/' },
          ...(run?.repository_id
            ? [{ label: 'Репозиторий', href: `/repositories/${run.repository_id}` }]
            : []),
          { label: `Анализ ${run ? run.id.substring(0, 8) : id.substring(0, 8)}` },
        ]}
        backLink={
          run?.repository_id
            ? { label: 'Назад к репозиторию', href: `/repositories/${run.repository_id}` }
            : { label: 'Назад к рейтингу', href: '/' }
        }
      />

      {error ? (
        <ErrorState
          error={error}
          title="Ошибка загрузки состояния анализа"
          onRetry={handleRetry}
        />
      ) : null}

      {!run && loading && !error && (
        <Card>
          <LoadingState message="Подключение к сессии анализа…" />
        </Card>
      )}

      {run && (
        <Card
          title="Анализ репозитория"
          subtitle={
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap', marginTop: '0.25rem' }}>
              <span style={{ fontFamily: 'var(--sh-font-mono)', fontSize: '0.85rem' }}>
                ID запуска: {run.id}
              </span>
              <CopyButton
                value={run.id}
                label=""
                title="Скопировать ID запуска"
                size="sm"
              />
              {run.scoring_policy_version && (
                <span
                  style={{
                    fontSize: '0.75rem',
                    padding: '0.15rem 0.45rem',
                    borderRadius: 'var(--sh-radius-sm)',
                    backgroundColor: 'var(--sh-bg-base)',
                    border: '1px solid var(--sh-border-subtle)',
                    color: 'var(--sh-text-secondary)',
                    fontFamily: 'var(--sh-font-mono)',
                  }}
                >
                  {run.scoring_policy_version}
                </span>
              )}
              {run.completed_at && run.queued_at && (
                <span style={{ fontSize: '0.82rem', color: 'var(--sh-text-muted)' }}>
                  Время анализа: {formatDurationSeconds(Math.max(0, Math.round((new Date(run.completed_at).getTime() - new Date(run.queued_at).getTime()) / 1000)))}
                </span>
              )}
            </div>
          }
          headerAction={
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.4rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <CopyButton
                  value={() => window.location.href}
                  label="Скопировать ссылку"
                  allowShare={true}
                  shareTitle={`Анализ ${run.id.substring(0, 8)} · SourceHealth`}
                  size="sm"
                />
                {statusMeta && (
                  <Badge variant={statusMeta.variant}>
                    {statusMeta.inProgress && (
                      <span
                        className="animate-spin"
                        style={{
                          width: '0.7em',
                          height: '0.7em',
                          border: '1.5px solid currentColor',
                          borderRightColor: 'transparent',
                          borderRadius: '50%',
                          display: 'inline-block',
                        }}
                        aria-hidden="true"
                      />
                    )}
                    <span>{statusMeta.label}</span>
                  </Badge>
                )}
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--sh-text-muted)' }}>
                Официальный Health
              </div>
              <ScoreDisplay score={run.health_score} size="lg" />
              {run.health_score === null && <SourceSoul preview={run.score_preview} />}
              <ScoreCoverage analysis={run} />
            </div>
          }
          footer={
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                width: '100%',
                flexWrap: 'wrap',
                gap: '1rem',
              }}
            >
              <div style={{ fontSize: '0.85rem', color: 'var(--sh-text-muted)' }}>
                {run.completed_at ? (
                  <span>Завершено: {formatDateTime(run.completed_at)}</span>
                ) : (
                  <span>В очереди с {formatDateTime(run.queued_at)}</span>
                )}
              </div>
              {['completed', 'partial'].includes(run.status) && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <a
                    href={`/api/v1/analyses/${encodeURIComponent(run.id)}/report.md`}
                    download
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.4rem',
                      backgroundColor: 'var(--sh-bg-surface-elevated)',
                      color: 'var(--sh-text-primary)',
                      border: '1px solid var(--sh-border-default)',
                      padding: '0.45rem 0.85rem',
                      borderRadius: 'var(--sh-radius-sm)',
                      fontSize: '0.88rem',
                      fontWeight: 500,
                      textDecoration: 'none',
                    }}
                  >
                    <span>⬇ Скачать отчёт (Markdown)</span>
                  </a>
                  <CopyButton
                    value={() => `${window.location.origin}/api/v1/analyses/${encodeURIComponent(run.id)}/report.md`}
                    label="Скопировать ссылку на отчёт"
                    copiedLabel="Ссылка скопирована!"
                    size="sm"
                  />
                </div>
              )}
            </div>
          }
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-6)' }}>
            {run.status === 'partial' && (
              <div
                role="status"
                style={{
                  padding: 'var(--sh-space-3) var(--sh-space-4)',
                  backgroundColor: 'var(--sh-health-warning-bg)',
                  border: '1px solid var(--sh-health-warning-border)',
                  borderRadius: 'var(--sh-radius-sm)',
                  color: 'var(--sh-health-warning)',
                  fontSize: '0.88rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                }}
              >
                <span aria-hidden="true">⚠️</span>
                <span>Анализ завершён частично. Доступные категории рассчитаны, отсутствующие данные не стали нулём.</span>
              </div>
            )}

            {run.status === 'failed' && (
              <div
                role="alert"
                style={{
                  padding: 'var(--sh-space-3) var(--sh-space-4)',
                  backgroundColor: 'var(--sh-health-danger-bg)',
                  border: '1px solid var(--sh-health-danger-border)',
                  borderRadius: 'var(--sh-radius-sm)',
                  color: 'var(--sh-health-danger)',
                  fontSize: '0.88rem',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '0.5rem',
                }}
              >
                <span>
                  {run.error_code ? humanizeErrorCode(run.error_code) : 'Анализ завершился с ошибкой.'}
                </span>
                {run.repository_id && (
                  <Link
                    to={`/repositories/${run.repository_id}`}
                    style={{
                      backgroundColor: 'var(--sh-bg-surface-elevated)',
                      color: 'var(--sh-text-primary)',
                      border: '1px solid var(--sh-border-default)',
                      padding: '0.35rem 0.75rem',
                      borderRadius: 'var(--sh-radius-sm)',
                      fontSize: '0.85rem',
                      fontWeight: 600,
                      textDecoration: 'none',
                    }}
                  >
                    К репозиторию для перезапуска ↗
                  </Link>
                )}
              </div>
            )}

            {run.error_code && run.status !== 'failed' && (
              <div
                role="alert"
                style={{
                  padding: 'var(--sh-space-3) var(--sh-space-4)',
                  backgroundColor: 'var(--sh-health-danger-bg)',
                  border: '1px solid var(--sh-health-danger-border)',
                  color: 'var(--sh-health-danger)',
                  borderRadius: 'var(--sh-radius-sm)',
                  fontSize: '0.9rem',
                }}
              >
                Код ошибки анализа: <strong>{humanizeErrorCode(run.error_code)}</strong> ({run.error_code})
              </div>
            )}

            {missingCategories.length > 0 && (
              <div
                style={{
                  padding: '0.6rem 0.85rem',
                  backgroundColor: 'var(--sh-bg-base)',
                  border: '1px solid var(--sh-border-subtle)',
                  borderRadius: 'var(--sh-radius-sm)',
                  fontSize: '0.85rem',
                  color: 'var(--sh-text-secondary)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                }}
              >
                <span aria-hidden="true">ℹ️</span>
                <span>
                  Не хватает данных для полной оценки: {missingCategories.map((c) => CATEGORY_LABELS[c]).join(', ')}. Официальный Health рассчитан по доступным категориям.
                </span>
              </div>
            )}

            {/* Category Scores in Fixed UI Order */}
            <div>
              <h3 style={{ marginBottom: 'var(--sh-space-3)' }}>Оценки по категориям</h3>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                  gap: 'var(--sh-space-3)',
                }}
              >
                {CATEGORY_ORDER.map((catKey) => {
                  const scoreData = run.category_scores[catKey];
                  const availability = scoreData?.availability ?? run.data_coverage?.[catKey] ?? 'no_data';
                  return (
                    <div
                      key={catKey}
                      style={{
                        padding: 'var(--sh-space-4)',
                        backgroundColor: 'var(--sh-bg-base)',
                        border: '1px solid var(--sh-border-subtle)',
                        borderRadius: 'var(--sh-radius-sm)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '0.5rem',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontWeight: 600, color: 'var(--sh-text-primary)' }}>
                          {CATEGORY_LABELS[catKey]}
                        </span>
                        <AvailabilityBadge availability={availability} />
                      </div>
                      <div>
                        <ScoreDisplay score={scoreData?.score ?? null} size="md" />
                      </div>
                      {scoreData?.score == null && availability === 'available' && (
                        <span style={{ fontSize: '0.8rem', color: 'var(--sh-text-muted)' }}>
                          Недостаточно наблюдений для численной оценки
                        </span>
                      )}
                      {scoreData?.explanation && (
                        <p
                          style={{
                            margin: 0,
                            fontSize: '0.86rem',
                            color: 'var(--sh-text-secondary)',
                            lineHeight: 1.45,
                          }}
                        >
                          {scoreData.explanation}
                        </p>
                      )}
                      <CategoryDetails category={catKey} checks={run.checks} score={scoreData?.score} />
                      {scoreData?.evidence_refs && scoreData.evidence_refs.length > 0 && (
                        <EvidenceList
                          evidenceRefs={scoreData.evidence_refs}
                          checks={run.checks}
                          label="Подтверждающие факты"
                        />
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Recommendations Section */}
            <div>
              <h3 style={{ marginBottom: 'var(--sh-space-3)' }}>
                Рекомендации по улучшению ({run.recommendations ? run.recommendations.length : 0})
              </h3>
              {run.recommendations && run.recommendations.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-3)' }}>
                  {[...run.recommendations]
                    .sort((a, b) => a.priority - b.priority || a.id.localeCompare(b.id))
                    .map((rec) => (
                      <RecommendationCard
                        key={rec.id}
                        recommendation={rec}
                        checks={run.checks}
                      />
                    ))}
                </div>
              ) : (
                <p style={{ color: 'var(--sh-text-muted)', fontSize: '0.9rem', margin: 0 }}>
                  Рекомендации пока не сформированы; это не подтверждает отсутствие проблем.
                </p>
              )}
            </div>

            {/* Supporting Evidence and Checks Breakdown */}
            {run.checks && Object.keys(run.checks).length > 0 && (
              <div>
                <h3 style={{ marginBottom: 'var(--sh-space-3)' }}>Результаты проверок и факты</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-3)' }}>
                  {Object.entries(run.checks).map(([checkName, checkData]) => (
                    <div
                      key={checkName}
                      style={{
                        padding: 'var(--sh-space-3) var(--sh-space-4)',
                        backgroundColor: 'var(--sh-bg-base)',
                        borderRadius: 'var(--sh-radius-sm)',
                        border: '1px solid var(--sh-border-subtle)',
                        fontSize: '0.88rem',
                      }}
                    >
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          flexWrap: 'wrap',
                          gap: '0.5rem',
                          marginBottom: '0.35rem',
                        }}
                      >
                        <span style={{ fontWeight: 600, color: 'var(--sh-text-primary)' }}>
                          {checkName} ({checkData.source})
                        </span>
                        <AvailabilityBadge availability={checkData.availability} />
                      </div>
                      {checkData.findings && checkData.findings.length > 0 && (
                        <div style={{ color: 'var(--sh-text-muted)', fontSize: '0.82rem', marginBottom: '0.35rem' }}>
                          Находок анализатора: {checkData.findings.length}
                        </div>
                      )}
                      {checkData.evidence && checkData.evidence.length > 0 && (
                        <div style={{ marginTop: '0.5rem' }}>
                          <span style={{ fontSize: '0.78rem', color: 'var(--sh-text-muted)', display: 'block', marginBottom: '0.25rem' }}>
                            Факты ({checkData.evidence.length}):
                          </span>
                          <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.82rem', color: 'var(--sh-text-secondary)' }}>
                            {checkData.evidence.map((ev) => {
                              const safeUrl = getSafeExternalUrl(ev.url);
                              return (
                                <li key={ev.id} style={{ marginBottom: '0.25rem' }}>
                                  <span style={{ fontFamily: 'var(--sh-font-mono)', color: 'var(--sh-text-muted)' }}>
                                    {ev.id}:
                                  </span>{' '}
                                  <span>{ev.summary}</span>
                                  {safeUrl ? (
                                    <>
                                      {' — '}
                                      <a href={safeUrl} target="_blank" rel="noopener noreferrer">
                                        Источник ↗
                                      </a>
                                    </>
                                  ) : ev.url ? (
                                    <span style={{ color: 'var(--sh-text-muted)' }}>
                                      {' — '}{ev.reference || ev.url}
                                    </span>
                                  ) : null}
                                </li>
                              );
                            })}
                          </ul>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Card>
      )}
    </div>
  );
};
