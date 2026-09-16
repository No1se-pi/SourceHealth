import React, { useState } from 'react';
import type { Recommendation, AnalyzerResult } from '../../api/client';
import { Badge } from './Badge';
import { CATEGORY_LABELS, getPriorityMeta, resolveEvidence } from '../../utils/analysis';

interface RecommendationCardProps {
  recommendation: Recommendation;
  checks?: Record<string, AnalyzerResult>;
}

export const RecommendationCard: React.FC<RecommendationCardProps> = ({
  recommendation,
  checks,
}) => {
  const [evidenceExpanded, setEvidenceExpanded] = useState(false);
  const priorityMeta = getPriorityMeta(recommendation.priority);
  const resolvedEvidence = resolveEvidence(recommendation.evidence_refs, checks);

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
        <span style={{ fontWeight: 600, color: 'var(--sh-brand)' }}>Действие: </span>
        <span style={{ color: 'var(--sh-text-primary)' }}>{recommendation.suggested_action}</span>
      </div>

      {recommendation.evidence_refs && recommendation.evidence_refs.length > 0 && (
        <div style={{ borderTop: '1px solid var(--sh-border-subtle)', paddingTop: 'var(--sh-space-2)' }}>
          <button
            type="button"
            onClick={() => setEvidenceExpanded(!evidenceExpanded)}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--sh-brand)',
              fontSize: '0.82rem',
              cursor: 'pointer',
              padding: '0.2rem 0',
              fontWeight: 500,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
            }}
            aria-expanded={evidenceExpanded}
          >
            <span>{evidenceExpanded ? '▾ Скрыть факты' : '▸ Подтверждающие факты'}</span>
            <span style={{ color: 'var(--sh-text-muted)' }}>
              ({recommendation.evidence_refs.length})
            </span>
          </button>

          {evidenceExpanded && (
            <div
              style={{
                marginTop: 'var(--sh-space-2)',
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--sh-space-2)',
              }}
            >
              {resolvedEvidence.length > 0 ? (
                resolvedEvidence.map((ev) => (
                  <div
                    key={ev.id}
                    style={{
                      padding: 'var(--sh-space-3)',
                      backgroundColor: 'var(--sh-bg-surface-elevated)',
                      borderRadius: 'var(--sh-radius-sm)',
                      border: '1px solid var(--sh-border-default)',
                      fontSize: '0.82rem',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.3rem',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        flexWrap: 'wrap',
                        gap: '0.5rem',
                      }}
                    >
                      <span style={{ fontFamily: 'var(--sh-font-mono)', color: 'var(--sh-text-muted)' }}>
                        {ev.id} · {ev.source}
                      </span>
                      {ev.timestamp && (
                        <span style={{ color: 'var(--sh-text-muted)' }}>
                          {new Date(ev.timestamp).toLocaleString('ru-RU')}
                        </span>
                      )}
                    </div>
                    <div style={{ color: 'var(--sh-text-primary)', fontWeight: 500 }}>
                      {ev.summary}
                    </div>
                    {(ev.location || ev.reference) && (
                      <div style={{ color: 'var(--sh-text-muted)', fontFamily: 'var(--sh-font-mono)' }}>
                        {ev.location ? `Файл/строка: ${ev.location}` : `Ссылка: ${ev.reference}`}
                      </div>
                    )}
                    {ev.url && (
                      <div>
                        <a
                          href={ev.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.25rem',
                            fontSize: '0.8rem',
                          }}
                        >
                          <span>Перейти к источнику</span>
                          <span aria-hidden="true">↗</span>
                        </a>
                      </div>
                    )}
                  </div>
                ))
              ) : (
                <div style={{ fontSize: '0.82rem', color: 'var(--sh-text-muted)' }}>
                  Ссылки на факты: {recommendation.evidence_refs.join(', ')} (детализация в checks ещё не загружена)
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
