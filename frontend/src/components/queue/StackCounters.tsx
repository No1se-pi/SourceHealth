import React from 'react';
import type { AnalysisStackData } from '../../api/queueData';

export interface StackCountersProps {
  data: AnalysisStackData;
  selectedLevel: 'priority' | 'timed' | 'planned' | null;
  onSelectLevel: (level: 'priority' | 'timed' | 'planned') => void;
}

export const StackCounters: React.FC<StackCountersProps> = ({
  data,
  selectedLevel,
  onSelectLevel,
}) => {
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
          <span className="sh-counter-badge is-priority">Срочная очередь</span>
        </div>
        <div className="sh-counter-value">
          {data.priority.count}
        </div>
        <div className="sh-counter-caption">
          {data.priority.count > 0
            ? 'Ручные запуски пользователей — исполняются в первую очередь'
            : 'Нет срочных проверок — все запросы обработаны'}
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
          {data.timed.count}
        </div>
        <div className="sh-counter-caption">
          {data.timed.count > 0
            ? `Срок обновления подошёл. Следующая пачка через ~${data.timed.nextBatchEstimateMinutes} мин`
            : 'Все проверки актуальны — интервал ещё не истёк'}
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
          <span className="sh-counter-label">Плановые</span>
          <span className="sh-counter-badge is-planned">Полный каталог</span>
        </div>
        <div className="sh-counter-value">
          {data.planned.count.toLocaleString('ru-RU')}
        </div>
        <div className="sh-counter-caption">
          Фоновый обход каталога для непрерывной актуализации метрик платформы
        </div>
      </div>
    </section>
  );
};
