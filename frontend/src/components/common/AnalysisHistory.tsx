import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, type Analysis, type AnalysisPage, type AnalysisSummary } from '../../api/client';
import { CATEGORY_ORDER, CATEGORY_LABELS, STATUS_CONFIG } from '../../utils/analysis';
import { Badge } from './Badge';
import { Card } from './Card';
import { ErrorState } from './ErrorState';
import { LoadingState } from './LoadingState';

function formatDateTime(timestamp: string | null | undefined): string {
  if (!timestamp) return '—';
  const d = new Date(timestamp);
  return isNaN(d.getTime()) ? String(timestamp) : d.toLocaleString('ru-RU');
}

function formatDateShort(timestamp: string | null | undefined): string {
  if (!timestamp) return '—';
  const d = new Date(timestamp);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });
}

function extractCategoryScore(val: unknown): { score: number | null; availability: string } {
  if (typeof val === 'number') {
    return { score: val, availability: 'available' };
  }
  if (val && typeof val === 'object') {
    const obj = val as Record<string, unknown>;
    const score = typeof obj.score === 'number' ? obj.score : null;
    const availability =
      typeof obj.availability === 'string'
        ? obj.availability
        : score !== null
        ? 'available'
        : 'no_data';
    return { score, availability };
  }
  return { score: null, availability: 'no_data' };
}

export function AnalysisHistory({
  repositoryId,
  currentAnalysis,
}: {
  repositoryId: string;
  currentAnalysis?: Analysis | null;
}) {
  const [page, setPage] = useState<AnalysisPage>();
  const [error, setError] = useState<unknown>();
  const [attempt, setAttempt] = useState(0);
  const [hoveredRun, setHoveredRun] = useState<AnalysisSummary | null>(null);
  const [prevAnalysis, setPrevAnalysis] = useState<Analysis | null>(null);
  const generation = useRef(0);


  useEffect(() => {
    const request = ++generation.current;
    setPage(undefined);
    setError(undefined);
    api
      .analysisHistory(repositoryId, 50, 0)
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

  const items = page?.items ?? [];

  // Filter for comparable runs: profile mvp-v1, completed or partial, numeric health_score
  const comparableRuns = items.filter(
    (run) =>
      run.profile === 'mvp-v1' &&
      ['completed', 'partial'].includes(run.status) &&
      typeof run.health_score === 'number'
  );

  // Check policy versions across comparable runs
  const policyVersions = Array.from(new Set(comparableRuns.map((r) => r.scoring_policy_version)));
  const hasPolicyShift = policyVersions.length > 1;

  // History summary metrics
  const latestRun = comparableRuns[0] ?? null;
  const previousRun = comparableRuns[1] ?? null;
  const canCompareWithPrevious =
    latestRun &&
    previousRun &&
    latestRun.scoring_policy_version === previousRun.scoring_policy_version;

  const delta =
    canCompareWithPrevious && latestRun.health_score !== null && previousRun.health_score !== null
      ? Math.round((latestRun.health_score - previousRun.health_score) * 10) / 10
      : null;

  const scores = comparableRuns
    .map((r) => r.health_score)
    .filter((s): s is number => typeof s === 'number');

  const bestScore = scores.length > 0 ? Math.max(...scores) : null;
  const lowestScore = scores.length > 0 ? Math.min(...scores) : null;

  // Chronological order for chart (oldest to newest)
  const chronological = [...comparableRuns].reverse();

  // SVG Chart layout calculation
  const chartWidth = 560;
  const chartHeight = 160;
  const padLeft = 40;
  const padRight = 30;
  const padTop = 20;
  const padBottom = 25;
  const plotWidth = chartWidth - padLeft - padRight;
  const plotHeight = chartHeight - padTop - padBottom;

  const getY = (score: number) => padTop + plotHeight * (1 - Math.max(0, Math.min(100, score)) / 100);
  const getX = (index: number, count: number) => {
    if (count <= 1) return padLeft + plotWidth / 2;
    return padLeft + (index / (count - 1)) * plotWidth;
  };

  const points = chronological.map((run, idx) => ({
    x: getX(idx, chronological.length),
    y: getY(run.health_score!),
    run,
  }));

  const pathD =
    points.length === 0
      ? ''
      : points.length === 1
      ? `M ${points[0].x - 5} ${points[0].y} L ${points[0].x + 5} ${points[0].y}`
      : points.reduce((acc, pt, idx) => `${acc} ${idx === 0 ? 'M' : 'L'} ${pt.x} ${pt.y}`, '');

  const areaD =
    points.length > 1
      ? `${pathD} L ${points[points.length - 1].x} ${padTop + plotHeight} L ${points[0].x} ${
          padTop + plotHeight
        } Z`
      : '';

  return (
    <Card
      title="История анализов и динамика Health"
      subtitle="История запусков, динамика официальной оценки и проверка устойчивости методики"
    >
      {error != null ? (
        <ErrorState
          error={error}
          title="Не удалось загрузить историю"
          onRetry={() => setAttempt((v) => v + 1)}
        />
      ) : !page ? (
        <LoadingState message="Загружаем историю анализов…" />
      ) : items.length === 0 ? (
        <p style={{ color: 'var(--sh-text-muted)', margin: 0, fontSize: '0.9rem' }}>
          Анализы для данного репозитория ещё не проводились.
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-5)' }}>
          {/* Policy version notice */}
          {hasPolicyShift && (
            <div
              role="note"
              style={{
                padding: 'var(--sh-space-3) var(--sh-space-4)',
                backgroundColor: 'var(--sh-bg-base)',
                border: '1px solid var(--sh-border-warning, #f59e0b)',
                borderRadius: 'var(--sh-radius-sm)',
                fontSize: '0.85rem',
                color: 'var(--sh-text-primary)',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
              }}
            >
              <span aria-hidden="true" style={{ color: '#f59e0b', fontWeight: 700 }}>⚠</span>
              <span>
                Методика оценки менялась; значения разных версий нельзя напрямую сравнивать.
              </span>
            </div>
          )}

          {/* History Summary Grid */}
          {comparableRuns.length > 0 && (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                gap: 'var(--sh-space-3)',
                padding: 'var(--sh-space-4)',
                backgroundColor: 'var(--sh-bg-base)',
                borderRadius: 'var(--sh-radius-sm)',
                border: '1px solid var(--sh-border-subtle)',
              }}
            >
              <div>
                <span style={{ fontSize: '0.8rem', color: 'var(--sh-text-muted)', display: 'block' }}>
                  Текущий Health
                </span>
                <span style={{ fontSize: '1.25rem', fontWeight: 700, fontFamily: 'var(--sh-font-mono)' }}>
                  {latestRun?.health_score !== null && latestRun?.health_score !== undefined
                    ? `${latestRun.health_score}/100`
                    : '—'}
                </span>
                {delta !== null && (
                  <span
                    style={{
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      display: 'block',
                      color:
                        delta > 0
                          ? 'var(--sh-health-good, #10b981)'
                          : delta < 0
                          ? 'var(--sh-health-danger, #ef4444)'
                          : 'var(--sh-text-muted)',
                    }}
                  >
                    {delta > 0 ? `+${delta}` : delta} с прошлого анализа
                  </span>
                )}
                {!canCompareWithPrevious && previousRun && (
                  <span style={{ fontSize: '0.75rem', color: 'var(--sh-text-muted)', display: 'block' }}>
                    (разные версии методики)
                  </span>
                )}
              </div>

              <div>
                <span style={{ fontSize: '0.8rem', color: 'var(--sh-text-muted)', display: 'block' }}>
                  Лучший Health
                </span>
                <span style={{ fontSize: '1.25rem', fontWeight: 700, fontFamily: 'var(--sh-font-mono)' }}>
                  {bestScore !== null ? `${bestScore}/100` : '—'}
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--sh-text-muted)', display: 'block' }}>
                  Минимум: {lowestScore !== null ? `${lowestScore}/100` : '—'}
                </span>
              </div>

              <div>
                <span style={{ fontSize: '0.8rem', color: 'var(--sh-text-muted)', display: 'block' }}>
                  Сопоставимых запусков
                </span>
                <span style={{ fontSize: '1.25rem', fontWeight: 700, fontFamily: 'var(--sh-font-mono)' }}>
                  {comparableRuns.length}
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--sh-text-muted)', display: 'block' }}>
                  из {items.length} всего
                </span>
              </div>

              <div>
                <span style={{ fontSize: '0.8rem', color: 'var(--sh-text-muted)', display: 'block' }}>
                  Версия методики
                </span>
                <code style={{ fontSize: '0.85rem', fontWeight: 600 }}>
                  {latestRun?.scoring_policy_version ?? '—'}
                </code>
              </div>
            </div>
          )}

          {/* SVG Trend Chart */}
          {comparableRuns.length > 0 && (
            <div
              style={{
                padding: 'var(--sh-space-4)',
                backgroundColor: 'var(--sh-bg-base)',
                borderRadius: 'var(--sh-radius-sm)',
                border: '1px solid var(--sh-border-subtle)',
                overflowX: 'auto',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: 'var(--sh-space-2)',
                }}
              >
                <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>
                  График динамики Health (0–100)
                </span>
                {hoveredRun && (
                  <span
                    style={{
                      fontSize: '0.8rem',
                      fontFamily: 'var(--sh-font-mono)',
                      color: 'var(--sh-brand)',
                    }}
                  >
                    {formatDateShort(hoveredRun.queued_at)}: {hoveredRun.health_score}/100 ({hoveredRun.scoring_policy_version})
                  </span>
                )}
              </div>

              <div style={{ width: '100%', minWidth: '420px', maxWidth: '720px', margin: '0 auto' }}>
                <svg
                  viewBox={`0 0 ${chartWidth} ${chartHeight}`}
                  style={{ width: '100%', height: 'auto', display: 'block' }}
                  role="img"
                  aria-label={`График динамики Health: ${comparableRuns.length} точек, текущий ${latestRun?.health_score ?? 'нет данных'}`}
                >
                  <defs>
                    <linearGradient id="shHealthGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--sh-brand)" stopOpacity="0.3" />
                      <stop offset="100%" stopColor="var(--sh-brand)" stopOpacity="0.0" />
                    </linearGradient>
                  </defs>

                  {/* Y-axis grid lines: 100, 75, 50, 25, 0 */}
                  {[100, 75, 50, 25, 0].map((val) => {
                    const y = getY(val);
                    return (
                      <g key={val}>
                        <line
                          x1={padLeft}
                          y1={y}
                          x2={chartWidth - padRight}
                          y2={y}
                          stroke="var(--sh-border-subtle)"
                          strokeDasharray={val === 0 || val === 100 ? 'none' : '3 3'}
                          strokeWidth="1"
                        />
                        <text
                          x={padLeft - 8}
                          y={y + 4}
                          textAnchor="end"
                          fontSize="10"
                          fill="var(--sh-text-muted)"
                          fontFamily="var(--sh-font-mono)"
                        >
                          {val}
                        </text>
                      </g>
                    );
                  })}

                  {/* Shaded Area under line */}
                  {areaD && <path d={areaD} fill="url(#shHealthGrad)" />}

                  {/* Trend line */}
                  {pathD && (
                    <path
                      d={pathD}
                      fill="none"
                      stroke="var(--sh-brand)"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  )}

                  {/* Data Points */}
                  {points.map((pt, idx) => {
                    const isHovered = hoveredRun?.id === pt.run.id;
                    return (
                      <g key={pt.run.id}>
                        <circle
                          cx={pt.x}
                          cy={pt.y}
                          r={isHovered ? 6 : 4}
                          fill="var(--sh-bg-surface)"
                          stroke="var(--sh-brand)"
                          strokeWidth={isHovered ? 3 : 2}
                          tabIndex={0}
                          role="button"
                          aria-label={`Запуск ${formatDateTime(pt.run.queued_at)}: Health ${pt.run.health_score}/100`}
                          style={{ cursor: 'pointer', transition: 'r 0.15s ease' }}
                          onMouseEnter={() => setHoveredRun(pt.run)}
                          onMouseLeave={() => setHoveredRun(null)}
                          onFocus={() => setHoveredRun(pt.run)}
                          onBlur={() => setHoveredRun(null)}
                        />
                        {/* Short date below last and first points or if few points */}
                        {(idx === 0 || idx === points.length - 1 || points.length <= 5) && (
                          <text
                            x={pt.x}
                            y={chartHeight - 8}
                            textAnchor="middle"
                            fontSize="9"
                            fill="var(--sh-text-muted)"
                            fontFamily="var(--sh-font-mono)"
                          >
                            {formatDateShort(pt.run.queued_at)}
                          </text>
                        )}
                      </g>
                    );
                  })}
                </svg>
              </div>
            </div>
          )}

          {/* Category Deltas between two comparable runs with same policy */}
          {currentAnalysis && prevAnalysis && canCompareWithPrevious && (
            <div
              style={{
                padding: 'var(--sh-space-4)',
                backgroundColor: 'var(--sh-bg-base)',
                borderRadius: 'var(--sh-radius-sm)',
                border: '1px solid var(--sh-border-subtle)',
              }}
            >
              <div
                style={{
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  marginBottom: 'var(--sh-space-3)',
                }}
              >
                Изменения по категориям (с прошлого сопоставимого анализа)
              </div>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                  gap: 'var(--sh-space-2)',
                }}
              >
                {CATEGORY_ORDER.map((catKey) => {
                  const curr = extractCategoryScore(currentAnalysis.category_scores?.[catKey]);
                  const prev = extractCategoryScore(prevAnalysis.category_scores?.[catKey]);

                  let labelText = 'без изменений';
                  let color = 'var(--sh-text-muted)';

                  if (prev.score === null && curr.score !== null) {
                    labelText = 'появились данные';
                    color = 'var(--sh-brand)';
                  } else if (prev.score !== null && curr.score === null) {
                    labelText = 'нет данных';
                    color = 'var(--sh-text-muted)';
                  } else if (prev.score === null && curr.score === null) {
                    labelText = 'нет данных';
                    color = 'var(--sh-text-muted)';
                  } else if (prev.score !== null && curr.score !== null) {
                    const diff = Math.round((curr.score - prev.score) * 10) / 10;
                    if (diff > 0) {
                      labelText = `+${diff}`;
                      color = 'var(--sh-health-good, #10b981)';
                    } else if (diff < 0) {
                      labelText = `${diff}`;
                      color = 'var(--sh-health-danger, #ef4444)';
                    } else {
                      labelText = '0 (без изм.)';
                    }
                  }

                  return (
                    <div
                      key={catKey}
                      style={{
                        padding: '0.4rem 0.6rem',
                        backgroundColor: 'var(--sh-bg-surface)',
                        borderRadius: 'var(--sh-radius-sm)',
                        border: '1px solid var(--sh-border-subtle)',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        fontSize: '0.82rem',
                      }}
                    >
                      <span style={{ color: 'var(--sh-text-muted)' }}>{CATEGORY_LABELS[catKey]}</span>
                      <span style={{ fontWeight: 600, color, fontFamily: 'var(--sh-font-mono)' }}>
                        {labelText}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}


          {/* Runs Table */}
          <div className="table-responsive-wrapper">
            <table className="leaderboard-table" style={{ borderRadius: 'var(--sh-radius-sm)', overflow: 'hidden' }}>
              <thead>
                <tr>
                  <th scope="col">Дата запуска</th>
                  <th scope="col">Статус</th>
                  <th scope="col">Health Score</th>
                  <th scope="col">Методика</th>
                  <th scope="col" style={{ textAlign: 'right' }}>Действие</th>
                </tr>
              </thead>
              <tbody>
                {items.map((run) => {
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
                        <code>{run.scoring_policy_version}</code>
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
              Показаны последние 50 запусков.
            </p>
          )}
        </div>
      )}
    </Card>
  );
}
