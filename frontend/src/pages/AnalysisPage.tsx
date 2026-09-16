import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, type Analysis, type RunStatus } from '../api/client';
import { Card } from '../components/common/Card';
import { Badge, type BadgeVariant } from '../components/common/Badge';
import { ScoreDisplay } from '../components/common/ScoreDisplay';
import { AvailabilityBadge } from '../components/common/AvailabilityBadge';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';

interface StatusMeta {
  label: string;
  variant: BadgeVariant;
  inProgress: boolean;
}

const STATUS_CONFIG: Record<RunStatus, StatusMeta> = {
  queued: { label: 'В очереди', variant: 'brand', inProgress: true },
  collecting: { label: 'Сбор данных', variant: 'brand', inProgress: true },
  analyzing: { label: 'Анализ репозитория', variant: 'brand', inProgress: true },
  scoring: { label: 'Подготовка оценки', variant: 'brand', inProgress: true },
  completed: { label: 'Завершён', variant: 'success', inProgress: false },
  partial: { label: 'Завершён с неполными данными', variant: 'warning', inProgress: false },
  failed: { label: 'Не удалось завершить', variant: 'danger', inProgress: false },
};

const CATEGORY_LABELS: Record<string, string> = {
  documentation: 'Документация',
  cicd: 'CI/CD',
  security: 'Безопасность (Security)',
  activity: 'Активность разработки',
  issues: 'Задачи и тикеты (Issues)',
  code_health: 'Качество кода (Code Health)',
};

export const AnalysisPage: React.FC = () => {
  const { id = '' } = useParams<{ id: string }>();
  const [run, setRun] = useState<Analysis>();
  const [error, setError] = useState<unknown>();

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;

    setRun(undefined);
    setError(undefined);

    async function poll() {
      try {
        const value = await api.analysis(id);
        if (!active) return;
        setRun(value);
        setError(undefined);

        if (!['completed', 'partial', 'failed'].includes(value.status)) {
          timer = setTimeout(poll, 2000);
        }
      } catch (err) {
        if (active) setError(err);
      }
    }

    void poll();

    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [id]);

  const statusMeta = run ? STATUS_CONFIG[run.status] : null;

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
          title="Ошибка загрузки состояния анализа"
        />
      ) : null}

      {!run && !error && (
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
              <ScoreDisplay score={run.health_score} size="lg" showStatusLabel />
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
                {run.repository_id && (
                  <Link to={`/repositories/${run.repository_id}`}>
                    ← К странице репозитория
                  </Link>
                )}
              </div>
              {['completed', 'partial'].includes(run.status) && (
                <a
                  href={`/api/v1/analyses/${id}/report.md`}
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
                  <span>⬇ Скачать отчёт в Markdown</span>
                </a>
              )}
            </div>
          }
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-5)' }}>
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

            <div>
              <h3 style={{ marginBottom: 'var(--sh-space-3)' }}>Оценки по категориям</h3>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                  gap: 'var(--sh-space-4)',
                }}
              >
                {Object.entries(run.category_scores).map(([key, value]) => (
                  <div
                    key={key}
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
                        {CATEGORY_LABELS[key] || key}
                      </span>
                      <AvailabilityBadge availability={value.availability} />
                    </div>
                    <div>
                      <ScoreDisplay score={value.score} size="md" />
                    </div>
                    {value.explanation && (
                      <p
                        style={{
                          margin: 0,
                          fontSize: '0.86rem',
                          color: 'var(--sh-text-secondary)',
                          lineHeight: 1.45,
                        }}
                      >
                        {value.explanation}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
};
