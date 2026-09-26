import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, type AnalysisPage } from '../../api/client';
import { STATUS_CONFIG } from '../../utils/analysis';
import { Badge } from './Badge';
import { Card } from './Card';
import { ErrorState } from './ErrorState';
import { LoadingState } from './LoadingState';

function formatDateTime(timestamp: string | null | undefined): string {
  if (!timestamp) return '—';
  const d = new Date(timestamp);
  return isNaN(d.getTime()) ? String(timestamp) : d.toLocaleString('ru-RU');
}

export function AnalysisHistory({ repositoryId }: { repositoryId: string }) {
  const [page, setPage] = useState<AnalysisPage>();
  const [error, setError] = useState<unknown>();
  const [attempt, setAttempt] = useState(0);
  const generation = useRef(0);

  useEffect(() => {
    const request = ++generation.current;
    setPage(undefined);
    setError(undefined);
    api
      .analysisHistory(repositoryId)
      .then((value) => {
        if (request === generation.current) setPage(value);
      })
      .catch((failure) => {
        if (request === generation.current) setError(failure);
      });
    return () => {
      generation.current++;
    };
  }, [repositoryId, attempt]);

  return (
    <Card
      title="История анализов"
      subtitle="Предыдущие запуски и зафиксированные оценки качества проекта"
    >
      {error != null ? (
        <ErrorState
          error={error}
          title="Не удалось загрузить историю"
          onRetry={() => setAttempt((v) => v + 1)}
        />
      ) : !page ? (
        <LoadingState message="Загружаем историю анализов…" />
      ) : page.items.length === 0 ? (
        <p style={{ color: 'var(--sh-text-muted)', margin: 0, fontSize: '0.9rem' }}>
          Анализы для данного репозитория ещё не проводились.
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-3)' }}>
          <div className="table-responsive-wrapper">
            <table className="leaderboard-table" style={{ borderRadius: 'var(--sh-radius-sm)', overflow: 'hidden' }}>
              <thead>
                <tr>
                  <th scope="col">Дата запуска</th>
                  <th scope="col">Статус</th>
                  <th scope="col">Health Score</th>
                  <th scope="col">Профиль</th>
                  <th scope="col" style={{ textAlign: 'right' }}>Действие</th>
                </tr>
              </thead>
              <tbody>
                {page.items.map((run) => {
                  const statusMeta = STATUS_CONFIG[run.status];
                  return (
                    <tr key={run.id}>
                      <td style={{ fontWeight: 500 }}>
                        <Link to={`/analyses/${run.id}`} style={{ color: 'var(--sh-text-primary)' }}>
                          {formatDateTime(run.queued_at)}
                        </Link>
                      </td>
                      <td>
                        <Badge variant={statusMeta.variant}>
                          {run.status === 'failed' ? 'Ошибка анализа' : statusMeta.label}
                        </Badge>
                      </td>
                      <td>
                        <span style={{ fontWeight: 700, fontFamily: 'var(--sh-font-mono)' }}>
                          {['completed', 'partial'].includes(run.status)
                            ? (run.health_score !== null && run.health_score !== undefined ? `${run.health_score}/100` : '—')
                            : '—'}
                        </span>
                      </td>
                      <td style={{ color: 'var(--sh-text-muted)', fontSize: '0.85rem' }}>
                        <code>{run.profile}</code>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <Link
                          to={`/analyses/${run.id}`}
                          style={{
                            fontSize: '0.82rem',
                            color: 'var(--sh-brand)',
                            fontWeight: 500,
                          }}
                        >
                          Подробнее →
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {page.has_more && (
            <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--sh-text-muted)' }}>
              Показаны последние 10 запусков.
            </p>
          )}
        </div>
      )}
    </Card>
  );
}
