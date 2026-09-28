import React from 'react';
import type { CatalogLiveMetrics } from '../../api/queueData';

export interface StackCountersProps {
  catalogMetrics: CatalogLiveMetrics;
  selectedLevel: 'priority' | 'timed' | 'planned' | null;
  onSelectLevel: (level: 'priority' | 'timed' | 'planned') => void;
}

export const StackCounters: React.FC<StackCountersProps> = ({
  catalogMetrics,
  selectedLevel,
  onSelectLevel,
}) => {
  const catalogCountFormatted =
    catalogMetrics.loaded && catalogMetrics.catalogTotal !== null
      ? catalogMetrics.catalogTotal.toLocaleString('ru-RU')
      : '—';

  return (
    <section className="sh-stack-counters-grid" aria-label="Метрики уровней очереди">
      {/* 1. Priority Card */}
      <div
        className={`sh-counter-card ${selectedLevel === 'priority' ? 'is-active' : ''}`}
        onClick={() => onSelectLevel('priority')}
        role="button"
        tabIndex={0}
        aria-pressed={selectedLevel === 'priority'}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onSelectLevel('priority')}
      >
        <div className="sh-counter-header">
          <span className="sh-counter-label">Приоритет</span>
          <span className="sh-counter-badge is-priority">Срочные проверки</span>
        </div>
        <div className="sh-counter-value">
          Ручной запуск
        </div>
        <div className="sh-counter-caption">
          Запросы пользователей исполняются в первую очередь
        </div>
      </div>

      {/* 2. Timed Card */}
      <div
        className={`sh-counter-card ${selectedLevel === 'timed' ? 'is-active' : ''}`}
        onClick={() => onSelectLevel('timed')}
        role="button"
        tabIndex={0}
        aria-pressed={selectedLevel === 'timed'}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onSelectLevel('timed')}
      >
        <div className="sh-counter-header">
          <span className="sh-counter-label">По расписанию</span>
          <span className="sh-counter-badge is-timed">Интервалы</span>
        </div>
        <div className="sh-counter-value">
          По расписанию
        </div>
        <div className="sh-counter-caption">
          Репозитории с наступившим сроком межпроверочного интервала
        </div>
      </div>

      {/* 3. Planned Card */}
      <div
        className={`sh-counter-card ${selectedLevel === 'planned' ? 'is-active' : ''}`}
        onClick={() => onSelectLevel('planned')}
        role="button"
        tabIndex={0}
        aria-pressed={selectedLevel === 'planned'}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onSelectLevel('planned')}
      >
        <div className="sh-counter-header">
          <span className="sh-counter-label">Плановый обход</span>
          <span className="sh-counter-badge is-planned">Фоновый каталог</span>
        </div>
        <div className="sh-counter-value">
          Каталог: {catalogCountFormatted}
        </div>
        <div className="sh-counter-caption">
          Постепенная фоновая проверка каталога без перегрузки платформы
        </div>
      </div>
    </section>
  );
};
