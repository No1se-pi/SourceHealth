import React from 'react';
import type { CatalogStats } from '../../api/client';

interface CatalogHeroProps {
  stats?: CatalogStats;
  loading?: boolean;
}

export const CatalogHero: React.FC<CatalogHeroProps> = ({ stats, loading }) => {
  const formatNum = (num?: number | null) => {
    if (num == null) return '—';
    return num.toLocaleString('ru-RU');
  };

  const medianText = stats?.health_median != null ? `${stats.health_median}` : '—';
  const iqrText =
    stats?.health_q1 != null && stats?.health_q3 != null
      ? `${stats.health_q1} – ${stats.health_q3}`
      : '—';

  return (
    <div
      className="sh-catalog-hero"
      style={{
        background: 'var(--sh-bg-surface, #ffffff)',
        border: '1px solid var(--sh-border-default, #d0d7de)',
        borderRadius: 'var(--sh-radius-md, 8px)',
        padding: '20px 24px',
        marginBottom: '20px',
      }}
    >
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '16px',
          marginBottom: '16px',
        }}
      >
        <div className="sh-stat-box">
          <div style={{ fontSize: '0.75rem', color: 'var(--sh-text-muted, #64748b)', marginBottom: '4px' }}>
            Всего в каталоге
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--sh-text-primary, #1f2328)' }}>
            {loading ? '...' : formatNum(stats?.catalog_total_public)}
          </div>
        </div>

        <div className="sh-stat-box">
          <div style={{ fontSize: '0.75rem', color: 'var(--sh-text-muted, #64748b)', marginBottom: '4px' }}>
            Найдено
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--sh-text-primary, #1f2328)' }}>
            {loading ? '...' : formatNum(stats?.matched_total)}
          </div>
        </div>

        <div className="sh-stat-box">
          <div style={{ fontSize: '0.75rem', color: 'var(--sh-text-muted, #64748b)', marginBottom: '4px' }}>
            Проанализировано
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--sh-text-primary, #1f2328)' }}>
            {loading ? '...' : formatNum(stats?.analyzed_count)}
          </div>
        </div>

        <div className="sh-stat-box">
          <div style={{ fontSize: '0.75rem', color: 'var(--sh-text-muted, #64748b)', marginBottom: '4px' }}>
            Медиана Health
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--sh-brand-text, #dc2626)' }}>
            {loading ? '...' : medianText}
          </div>
        </div>

        <div className="sh-stat-box">
          <div style={{ fontSize: '0.75rem', color: 'var(--sh-text-muted, #64748b)', marginBottom: '4px' }}>
            Центральные 50% (Q1–Q3)
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--sh-text-primary, #1f2328)' }}>
            {loading ? '...' : iqrText}
          </div>
        </div>
      </div>

      <div
        style={{
          fontSize: '0.75rem',
          color: 'var(--sh-text-muted, #64748b)',
          lineHeight: 1.4,
          borderTop: '1px solid var(--sh-border-subtle, #e1e4e8)',
          paddingTop: '10px',
        }}
      >
        Медиана и диапазон 25–75% рассчитываются строго среди проектов с рассчитанным Health (NO_DATA исключён).
        Source Soul не является официальным Health.
      </div>
    </div>
  );
};
