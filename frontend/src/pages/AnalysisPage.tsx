import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, type Analysis } from '../api/client';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { ScoreDisplay } from '../components/common/ScoreDisplay';
import { AvailabilityBadge } from '../components/common/AvailabilityBadge';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';
import { RecommendationCard } from '../components/common/RecommendationCard';
import { EvidenceList } from '../components/common/EvidenceList';
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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-6)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <Link
            to="/"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
              fontSize: '0.9rem',
              color: 'var(--sh-text-muted)',
            }}
          >
            ← К лидерборду
          </Link>
          {run && run.repository_id && (
            <Link
              to={`/repositories/${run.repository_id}`}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.4rem',
                fontSize: '0.9rem',
                color: 'var(--sh-text-muted)',
              }}
            >
              ← К репозиторию
            </Link>
          )}
        </div>
      </div>

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
            <span style={{ fontFamily: 'var(--sh-font-mono)', fontSize: '0.85rem' }}>
              ID запуска: {run.id}
            </span>
          }
          headerAction={
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.5rem' }}>
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
              <ScoreDisplay score={run.health_score} size="lg" />
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
                  <span>Завершено: {new Date(run.completed_at).toLocaleString('ru-RU')}</span>
                ) : (
                  <span>В очереди с {new Date(run.queued_at).toLocaleString('ru-RU')}</span>
                )}
              </div>
              {['completed', 'partial'].includes(run.status) && (
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
              )}
            </div>
          }
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-6)' }}>
            {run.error_code && (
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
                Код ошибки анализа: <strong>{run.error_code}</strong>
              </div>
            )}

            {/* Category Scores in Fixed UI Order */}
            <div>
              <h3 style={{ marginBottom: 'var(--sh-space-3)' }}>Оценки по категориям</h3>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                  gap: 'var(--sh-space-4)',
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
              <h3 style={{ marginBottom: 'var(--sh-space-3)' }}>Рекомендации по улучшению</h3>
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
