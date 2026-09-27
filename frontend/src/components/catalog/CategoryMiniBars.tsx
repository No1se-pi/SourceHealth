import React from 'react';
import type { CategoryScoreMini } from '../../api/client';

interface CategoryMiniBarsProps {
  categories?: Record<string, CategoryScoreMini | null> | null;
}

const CATEGORY_CONFIG: Array<{ key: string; label: string; short: string }> = [
  { key: 'documentation', label: 'Документация', short: 'Doc' },
  { key: 'cicd', label: 'CI/CD', short: 'CI' },
  { key: 'security', label: 'Безопасность (AppSec)', short: 'Sec' },
  { key: 'activity', label: 'Активность', short: 'Act' },
  { key: 'issues', label: 'Issues', short: 'Iss' },
  { key: 'code_health', label: 'Качество кода', short: 'Code' },
];

function getScoreColor(score: number | null | undefined, availability?: string | null): string {
  if (score == null || availability === 'no_data') {
    return 'var(--sh-health-unavailable, #8c959f)';
  }
  if (score >= 80) return 'var(--sh-health-good, #1a7f37)';
  if (score >= 50) return 'var(--sh-health-warning, #9a6700)';
  return 'var(--sh-health-danger, #cf222e)';
}

export const CategoryMiniBars: React.FC<CategoryMiniBarsProps> = ({ categories }) => {
  return (
    <div
      className="sh-category-mini-bars"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '3px',
      }}
      aria-label="Оценки категорий"
    >
      {CATEGORY_CONFIG.map(({ key, label, short }) => {
        const cat = categories ? categories[key] : null;
        const score = cat?.score;
        const availability = cat?.availability ?? 'no_data';
        const color = getScoreColor(score, availability);
        const heightPercent = score != null ? Math.max(20, Math.min(100, score)) : 15;
        const tooltip = score != null
          ? `${label}: ${Math.round(score * 10) / 10} / 100`
          : `${label}: Нет данных (NO_DATA)`;

        return (
          <div
            key={key}
            title={tooltip}
            style={{
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'flex-end',
              alignItems: 'center',
              width: '6px',
              height: '18px',
              backgroundColor: 'var(--sh-bg-surface-elevated, rgba(0, 0, 0, 0.06))',
              borderRadius: '2px',
              overflow: 'hidden',
              cursor: 'help',
              position: 'relative',
            }}
          >
            <div
              style={{
                width: '100%',
                height: `${heightPercent}%`,
                backgroundColor: color,
                borderRadius: '1px',
                transition: 'height 0.2s ease',
              }}
            />
          </div>
        );
      })}
    </div>
  );
};
