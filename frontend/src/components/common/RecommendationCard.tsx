import React from 'react';
import type { Recommendation, AnalyzerResult } from '../../api/client';
import { Badge } from './Badge';
import { EvidenceList } from './EvidenceList';
import { CATEGORY_LABELS, getPriorityMeta } from '../../utils/analysis';

interface RecommendationCardProps {
  recommendation: Recommendation;
  checks?: Record<string, AnalyzerResult>;
}

export const RecommendationCard: React.FC<RecommendationCardProps> = ({
  recommendation,
  checks,
}) => {
  const priorityMeta = getPriorityMeta(recommendation.priority);

  return (
    <div
      style={{
        padding: 'var(--sh-space-4)',
        backgroundColor: 'var(--sh-bg-base)',
        border: '1px solid var(--sh-border-subtle)',
        borderRadius: 'var(--sh-radius-sm)',
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--sh-space-3)',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '0.5rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <Badge variant={priorityMeta.variant}>{priorityMeta.label}</Badge>
          <span
            style={{
              fontSize: '0.8rem',
              color: 'var(--sh-text-muted)',
              fontWeight: 500,
            }}
          >
            {CATEGORY_LABELS[recommendation.category] || recommendation.category}
          </span>
        </div>
        {recommendation.expected_impact && (
          <span
            style={{
              fontSize: '0.8rem',
              color: 'var(--sh-health-good)',
              fontWeight: 500,
              backgroundColor: 'var(--sh-health-good-bg)',
              padding: '0.15rem 0.5rem',
              borderRadius: 'var(--sh-radius-sm)',
              border: '1px solid var(--sh-health-good-border)',
            }}
          >
            Эффект: {recommendation.expected_impact}
          </span>
        )}
      </div>

      <div>
        <h4 style={{ margin: '0 0 0.35rem 0', fontSize: '1rem', color: 'var(--sh-text-primary)' }}>
          {recommendation.title}
        </h4>
        <p style={{ margin: 0, fontSize: '0.88rem', color: 'var(--sh-text-secondary)', lineHeight: 1.5 }}>
          {recommendation.description}
        </p>
      </div>

      <div
        style={{
          padding: 'var(--sh-space-3)',
          backgroundColor: 'var(--sh-bg-surface)',
          borderRadius: 'var(--sh-radius-sm)',
          border: '1px solid var(--sh-border-default)',
          fontSize: '0.88rem',
        }}
      >
        <span style={{ fontWeight: 600, color: 'var(--sh-brand-text)' }}>Действие: </span>
        <span style={{ color: 'var(--sh-text-primary)' }}>{recommendation.suggested_action}</span>
      </div>

      <EvidenceList
        evidenceRefs={recommendation.evidence_refs}
        checks={checks}
        label="Подтверждающие факты"
      />
    </div>
  );
};
