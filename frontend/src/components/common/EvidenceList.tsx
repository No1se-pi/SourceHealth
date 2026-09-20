import React, { useState } from 'react';
import type { AnalyzerResult } from '../../api/client';
import { resolveEvidence, getSafeExternalUrl } from '../../utils/analysis';

interface EvidenceListProps {
  evidenceRefs: string[];
  checks?: Record<string, AnalyzerResult>;
  label?: string;
}

export const EvidenceList: React.FC<EvidenceListProps> = ({
  evidenceRefs,
  checks,
  label = 'Подтверждающие факты',
}) => {
  const [expanded, setExpanded] = useState(false);

  if (!evidenceRefs || evidenceRefs.length === 0) {
    return null;
  }

  const resolvedEvidence = resolveEvidence(evidenceRefs, checks);

  return (
    <div style={{ borderTop: '1px solid var(--sh-border-subtle)', paddingTop: 'var(--sh-space-2)' }}>
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
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
        aria-expanded={expanded}
      >
        <span>{expanded ? `▾ Скрыть ${label.toLowerCase()}` : `▸ ${label}`}</span>
        <span style={{ color: 'var(--sh-text-muted)' }}>· {evidenceRefs.length}</span>
      </button>

      {expanded && (
        <div
          style={{
            marginTop: 'var(--sh-space-2)',
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--sh-space-2)',
          }}
        >
          {resolvedEvidence.length > 0 ? (
            resolvedEvidence.map((ev) => {
              const safeUrl = getSafeExternalUrl(ev.url);
              return (
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
                  {safeUrl ? (
                    <div>
                      <a
                        href={safeUrl}
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
                  ) : ev.url ? (
                    <div style={{ color: 'var(--sh-text-muted)', fontSize: '0.78rem' }}>
                      Источник: {ev.reference || ev.url}
                    </div>
                  ) : null}
                </div>
              );
            })
          ) : (
            <div style={{ fontSize: '0.82rem', color: 'var(--sh-text-muted)' }}>
              Ссылки на факты: {evidenceRefs.join(', ')} (детализация в checks ещё не загружена)
            </div>
          )}
        </div>
      )}
    </div>
  );
};
