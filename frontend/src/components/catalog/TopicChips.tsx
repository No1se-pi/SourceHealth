import React from 'react';

interface TopicChipsProps {
  selectedTopic?: string;
  topicCounts?: Record<string, number>;
  onSelectTopic: (topic?: string) => void;
}

const TOPICS_CONFIG: Array<{ key: string; label: string }> = [
  { key: 'bots', label: 'Боты' },
  { key: 'web', label: 'Web' },
  { key: 'ml_data', label: 'ML и данные' },
  { key: 'games', label: 'Игры' },
  { key: 'education', label: 'Учебные' },
  { key: 'mobile', label: 'Mobile' },
  { key: 'devops', label: 'DevOps' },
  { key: 'tools', label: 'Инструменты' },
  { key: 'security', label: 'Security' },
  { key: 'libraries', label: 'Библиотеки' },
  { key: 'other', label: 'Другое' },
];

export const TopicChips: React.FC<TopicChipsProps> = ({
  selectedTopic,
  topicCounts,
  onSelectTopic,
}) => {
  return (
    <div
      className="sh-topic-chips-container"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        overflowX: 'auto',
        paddingBottom: '8px',
        marginBottom: '16px',
        scrollbarWidth: 'thin',
      }}
      title="Тема определена автоматически по публичным метаданным проекта (catalog-topic-v1)"
    >
      <button
        type="button"
        onClick={() => onSelectTopic(undefined)}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '6px',
          padding: '6px 12px',
          borderRadius: 'var(--sh-radius-full, 9999px)',
          fontSize: '0.8125rem',
          fontWeight: !selectedTopic ? 600 : 500,
          border: '1px solid',
          borderColor: !selectedTopic
            ? 'var(--sh-brand, #f93333)'
            : 'var(--sh-border-default, #d0d7de)',
          backgroundColor: !selectedTopic
            ? 'var(--sh-brand-subtle, rgba(249, 51, 51, 0.08))'
            : 'var(--sh-bg-surface, #ffffff)',
          color: !selectedTopic
            ? 'var(--sh-brand-text, #dc2626)'
            : 'var(--sh-text-primary, #1f2328)',
          cursor: 'pointer',
          whiteSpace: 'nowrap',
          transition: 'all 0.15s ease',
        }}
      >
        <span>Все темы</span>
      </button>

      {TOPICS_CONFIG.map(({ key, label }) => {
        const isSelected = selectedTopic === key;
        const count = topicCounts ? topicCounts[key] : undefined;

        return (
          <button
            key={key}
            type="button"
            onClick={() => onSelectTopic(isSelected ? undefined : key)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              borderRadius: 'var(--sh-radius-full, 9999px)',
              fontSize: '0.8125rem',
              fontWeight: isSelected ? 600 : 500,
              border: '1px solid',
              borderColor: isSelected
                ? 'var(--sh-brand, #f93333)'
                : 'var(--sh-border-default, #d0d7de)',
              backgroundColor: isSelected
                ? 'var(--sh-brand-subtle, rgba(249, 51, 51, 0.08))'
                : 'var(--sh-bg-surface, #ffffff)',
              color: isSelected
                ? 'var(--sh-brand-text, #dc2626)'
                : 'var(--sh-text-primary, #1f2328)',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              transition: 'all 0.15s ease',
            }}
          >
            <span>{label}</span>
            {count !== undefined && count > 0 && (
              <span
                style={{
                  fontSize: '0.6875rem',
                  padding: '1px 5px',
                  borderRadius: 'var(--sh-radius-full, 9999px)',
                  backgroundColor: isSelected
                    ? 'rgba(249, 51, 51, 0.15)'
                    : 'var(--sh-bg-surface-elevated, #f1f3f5)',
                  color: isSelected
                    ? 'var(--sh-brand-text, #dc2626)'
                    : 'var(--sh-text-muted, #64748b)',
                }}
              >
                {count.toLocaleString('ru-RU')}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};
