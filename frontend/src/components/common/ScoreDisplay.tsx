import React from 'react';

export type ScoreLevel = 'good' | 'warning' | 'danger' | 'unavailable';

export interface ScoreMeta {
  level: ScoreLevel;
  label: string;
  color: string;
  bgColor: string;
  borderColor: string;
}

export function getScoreMeta(score: number | null | undefined): ScoreMeta {
  if (score === null || score === undefined) {
    return {
      level: 'unavailable',
      label: 'Нет данных',
      color: 'var(--sh-health-unavailable)',
      bgColor: 'var(--sh-health-unavailable-bg)',
      borderColor: 'var(--sh-health-unavailable-border)',
    };
  }
  if (score >= 75) {
    return {
      level: 'good',
      label: 'Отлично',
      color: 'var(--sh-health-good)',
      bgColor: 'var(--sh-health-good-bg)',
      borderColor: 'var(--sh-health-good-border)',
    };
  }
  if (score >= 50) {
    return {
      level: 'warning',
      label: 'Требует внимания',
      color: 'var(--sh-health-warning)',
      bgColor: 'var(--sh-health-warning-bg)',
      borderColor: 'var(--sh-health-warning-border)',
    };
  }
  return {
    level: 'danger',
    label: 'Критично',
    color: 'var(--sh-health-danger)',
    bgColor: 'var(--sh-health-danger-bg)',
    borderColor: 'var(--sh-health-danger-border)',
  };
}

interface ScoreDisplayProps {
  score: number | null | undefined;
  size?: 'sm' | 'md' | 'lg' | 'hero';
  showMax?: boolean;
  showStatusLabel?: boolean;
  className?: string;
}

export const ScoreDisplay: React.FC<ScoreDisplayProps> = ({
  score,
  size = 'md',
  showMax = true,
  showStatusLabel = false,
  className = '',
}) => {
  const meta = getScoreMeta(score);

  const fontSizes: Record<'sm' | 'md' | 'lg' | 'hero', { value: string; max: string }> = {
    sm: { value: '0.95rem', max: '0.75rem' },
    md: { value: '1.25rem', max: '0.85rem' },
    lg: { value: '1.75rem', max: '1rem' },
    hero: { value: '2.8rem', max: '1.25rem' },
  };

  if (score === null || score === undefined) {
    return (
      <span
        className={`score-display score-unavailable ${className}`.trim()}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.4rem',
          color: meta.color,
          fontSize: fontSizes[size].value,
          fontWeight: 600,
        }}
        title="Оценка ещё не рассчитана (NO_DATA)"
        aria-label="Оценка здоровья: Нет данных"
      >
        <span>Нет оценки</span>
        {showStatusLabel && (
          <span
            style={{
              fontSize: '0.75rem',
              color: 'var(--sh-text-muted)',
              fontWeight: 400,
            }}
          >
            (нет данных)
          </span>
        )}
      </span>
    );
  }

  return (
    <span
      className={`score-display score-${meta.level} ${className}`.trim()}
      style={{
        display: 'inline-flex',
        alignItems: 'baseline',
        gap: '0.2rem',
        fontWeight: 700,
        color: meta.color,
      }}
      aria-label={`Оценка здоровья: ${score} из 100 (${meta.label})`}
    >
      <span style={{ fontSize: fontSizes[size].value, lineHeight: 1 }}>
        {score}
      </span>
      {showMax && (
        <span
          style={{
            fontSize: fontSizes[size].max,
            color: 'var(--sh-text-muted)',
            fontWeight: 400,
          }}
        >
          /100
        </span>
      )}
      {showStatusLabel && (
        <span
          style={{
            marginLeft: '0.5rem',
            fontSize: '0.8rem',
            padding: '0.15rem 0.45rem',
            borderRadius: 'var(--sh-radius-sm)',
            backgroundColor: meta.bgColor,
            color: meta.color,
            border: `1px solid ${meta.borderColor}`,
            fontWeight: 600,
          }}
        >
          {meta.label}
        </span>
      )}
    </span>
  );
};
