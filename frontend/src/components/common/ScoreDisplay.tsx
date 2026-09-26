import React from 'react';

interface ScoreDisplayProps {
  score: number | null | undefined;
  size?: 'sm' | 'md' | 'lg' | 'hero';
  showMax?: boolean;
  className?: string;
}

export const ScoreDisplay: React.FC<ScoreDisplayProps> = ({
  score,
  size = 'md',
  showMax = true,
  className = '',
}) => {
  const fontSizes: Record<'sm' | 'md' | 'lg' | 'hero', { value: string; max: string }> = {
    sm: { value: '0.95rem', max: '0.75rem' },
    md: { value: '1.2rem', max: '0.85rem' },
    lg: { value: '1.75rem', max: '1rem' },
    hero: { value: '2.8rem', max: '1.25rem' },
  };

  // Explicit NO_DATA check: absence of score must never be treated as 0
  if (score === null || score === undefined) {
    return (
      <span
        className={`score-display score-no-data ${className}`.trim()}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          color: 'var(--sh-text-muted)',
          fontSize: fontSizes[size].value,
          fontWeight: 500,
        }}
        title="Недостаточно наблюдений для численной оценки (NO_DATA)"
        aria-label="Численная оценка пока не рассчитана"
      >
        Пока не рассчитан
      </span>
    );
  }

  // Display raw numerical score without arbitrary frontend classifications
  return (
    <span
      className={`score-display ${className}`.trim()}
      style={{
        display: 'inline-flex',
        alignItems: 'baseline',
        gap: '0.15rem',
        fontWeight: 700,
        color: 'var(--sh-text-primary)',
      }}
      aria-label={`Оценка здоровья: ${score} из 100`}
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
    </span>
  );
};
