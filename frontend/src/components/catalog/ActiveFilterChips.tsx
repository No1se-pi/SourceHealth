import React from 'react';

export interface ActiveFiltersState {
  q?: string;
  language?: string;
  topic?: string;
  origin?: string;
  health_status?: string;
  health_min?: number;
  health_max?: number;
  coverage_min?: number;
  security_min?: number;
  security_status?: string;
  activity_days?: number;
}

interface ActiveFilterChipsProps {
  filters: ActiveFiltersState;
  onRemoveFilter: (key: keyof ActiveFiltersState) => void;
  onResetAll: () => void;
}

const ORIGIN_LABELS: Record<string, string> = {
  native: 'Native',
  fork: 'Fork',
  migrated: 'Migrated',
  unknown: 'Unknown',
};

const HEALTH_STATUS_LABELS: Record<string, string> = {
  available: 'С оценкой',
  forming: 'Формируется',
  no_data: 'NO_DATA',
};

export const ActiveFilterChips: React.FC<ActiveFilterChipsProps> = ({
  filters,
  onRemoveFilter,
  onResetAll,
}) => {
  const activeChips: Array<{ key: keyof ActiveFiltersState; label: string }> = [];

  if (filters.q) {
    activeChips.push({ key: 'q', label: `Поиск: «${filters.q}»` });
  }
  if (filters.language) {
    activeChips.push({ key: 'language', label: `Язык: ${filters.language}` });
  }
  if (filters.topic) {
    activeChips.push({ key: 'topic', label: `Тема: ${filters.topic}` });
  }
  if (filters.origin) {
    activeChips.push({
      key: 'origin',
      label: `Происхождение: ${ORIGIN_LABELS[filters.origin] ?? filters.origin}`,
    });
  }
  if (filters.health_status) {
    activeChips.push({
      key: 'health_status',
      label: `Health статус: ${HEALTH_STATUS_LABELS[filters.health_status] ?? filters.health_status}`,
    });
  }
  if (filters.health_min != null || filters.health_max != null) {
    const min = filters.health_min ?? 0;
    const max = filters.health_max ?? 100;
    activeChips.push({ key: 'health_min', label: `Health: ${min}–${max}` });
  }
  if (filters.coverage_min != null) {
    activeChips.push({ key: 'coverage_min', label: `Coverage ≥ ${filters.coverage_min}%` });
  }
  if (filters.security_min != null) {
    activeChips.push({ key: 'security_min', label: `Security ≥ ${filters.security_min}` });
  }
  if (filters.security_status) {
    activeChips.push({
      key: 'security_status',
      label: `Security: ${filters.security_status === 'available' ? 'С оценкой' : 'NO_DATA'}`,
    });
  }
  if (filters.activity_days != null) {
    activeChips.push({ key: 'activity_days', label: `Активность: ≤ ${filters.activity_days} дн.` });
  }

  if (activeChips.length === 0) {
    return null;
  }

  return (
    <div
      className="sh-active-filters"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: '6px',
        marginBottom: '16px',
      }}
    >
      <span style={{ fontSize: '0.75rem', color: 'var(--sh-text-muted, #64748b)', marginRight: '4px' }}>
        Активные фильтры:
      </span>

      {activeChips.map(({ key, label }) => (
        <span
          key={key}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '5px',
            padding: '3px 8px',
            fontSize: '0.75rem',
            backgroundColor: 'var(--sh-bg-surface-elevated, #f1f3f5)',
            border: '1px solid var(--sh-border-default, #d0d7de)',
            borderRadius: 'var(--sh-radius-sm, 6px)',
            color: 'var(--sh-text-primary, #1f2328)',
          }}
        >
          <span>{label}</span>
          <button
            type="button"
            onClick={() => onRemoveFilter(key)}
            style={{
              background: 'none',
              border: 'none',
              padding: '0 2px',
              cursor: 'pointer',
              color: 'var(--sh-text-muted, #64748b)',
              fontSize: '11px',
              fontWeight: 700,
            }}
            aria-label={`Удалить фильтр ${label}`}
          >
            ✕
          </button>
        </span>
      ))}

      <button
        type="button"
        onClick={onResetAll}
        style={{
          background: 'none',
          border: 'none',
          fontSize: '0.75rem',
          color: 'var(--sh-brand-text, #dc2626)',
          cursor: 'pointer',
          textDecoration: 'underline',
          padding: '3px 6px',
        }}
      >
        Сбросить все
      </button>
    </div>
  );
};
