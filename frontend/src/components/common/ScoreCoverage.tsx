import React from 'react';
import type { Analysis } from '../../api/client';
import { CATEGORY_LABELS } from '../../utils/analysis';

export function ScoreCoverage({ analysis }: { analysis?: Analysis }) {
  const coverage = analysis?.score_coverage;
  if (!coverage) {
    return (
      <div style={{ fontSize: '0.78rem', color: 'var(--sh-text-muted)' }}>
        Охват оценки: не определён
      </div>
    );
  }

  return (
    <div
      style={{
        display: 'inline-flex',
        flexDirection: 'column',
        alignItems: 'flex-end',
        fontSize: '0.8rem',
        color: 'var(--sh-text-secondary)',
        marginTop: 'var(--sh-space-1)',
        gap: '0.2rem',
      }}
    >
      <div
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.4rem',
          backgroundColor: 'var(--sh-bg-surface-elevated)',
          border: '1px solid var(--sh-border-default)',
          borderRadius: 'var(--sh-radius-sm)',
          padding: '0.2rem 0.55rem',
          fontWeight: 600,
          color: 'var(--sh-text-primary)',
        }}
        title="Процент номинального веса категорий с доступными данными"
      >
        <span>Охват оценки:</span>
        <span style={{ color: 'var(--sh-brand)' }}>{coverage.nominal_weight_percent}%</span>
        <span style={{ color: 'var(--sh-text-muted)', fontWeight: 400 }}>· {coverage.scored_categories}/6 категорий</span>
      </div>
      {coverage.unscored_categories && coverage.unscored_categories.length > 0 && (
        <span style={{ fontSize: '0.74rem', color: 'var(--sh-text-muted)' }}>
          Без оценки: {coverage.unscored_categories.map((k) => CATEGORY_LABELS[k] || k).join(', ')}
        </span>
      )}
      {coverage.partial_categories && coverage.partial_categories.length > 0 && (
        <span style={{ fontSize: '0.74rem', color: 'var(--sh-health-warning)' }}>
          Частично: {coverage.partial_categories.map((k) => CATEGORY_LABELS[k] || k).join(', ')}
        </span>
      )}
    </div>
  );
}
