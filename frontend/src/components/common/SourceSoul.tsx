import React from 'react';
import type { components } from '../../api/generated';

type ScorePreview = components['schemas']['ScorePreviewDTO'];

export function SourceSoul({ preview, compact = false }: { preview: ScorePreview | null | undefined; compact?: boolean }) {
  if (!preview) return null;
  const label = preview.numeric && preview.score !== null ? `≈${preview.score}` : 'Формируется';
  return (
    <div className={`source-soul ${compact ? 'source-soul-compact' : ''}`.trim()}
      title="Предварительная оценка. Не является Health Score и не участвует в рейтинге.">
      <svg viewBox="0 0 32 32" width="28" height="28" fill="none" aria-hidden="true">
        <path d="M7 15.5C7 9.2 10.8 5 16 5s9 4.2 9 10.5V27l-4-3-5 3-5-3-4 3V15.5Z"
          stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
        <circle cx="12.5" cy="15" r="1.3" fill="currentColor" />
        <circle cx="19.5" cy="15" r="1.3" fill="currentColor" />
        <path d="M13 20c1.8 1.2 4.2 1.2 6 0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
      <span><strong>{label}</strong><small>{preview.nominal_weight_percent}% данных</small></span>
    </div>
  );
}
