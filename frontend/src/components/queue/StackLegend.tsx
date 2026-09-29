import React from 'react';

export interface StackLegendProps {
  selectedLevel: 'priority' | 'timed' | 'planned';
  onSelectLevel: (level: 'priority' | 'timed' | 'planned') => void;
  isAnimationPaused: boolean;
  onToggleAnimation: () => void;
}

export const StackLegend: React.FC<StackLegendProps> = ({
  selectedLevel,
  isAnimationPaused,
  onToggleAnimation,
}) => {
  const levelDescriptions: Record<
    'priority' | 'timed' | 'planned',
    { title: string; text: string; badge: string; badgeClass: string }
  > = {
    priority: {
      title: 'Режим: Ручной запуск',
      text: 'Ручной анализ позволяет запросить актуальную проверку репозитория по требованию. После создания задача попадает в общую систему обработки SourceHealth.',
      badge: 'По требованию',
      badgeClass: 'is-priority',
    },
    timed: {
      title: 'Режим: Проверки по расписанию',
      text: 'Репозитории возвращаются для повторной проверки, когда истекает рассчитанный интервал актуализации. Недавно активные репозитории могут получать более короткий интервал.',
      badge: 'Интервалы',
      badgeClass: 'is-timed',
    },
    planned: {
      title: 'Режим: Плановый фоновый обход',
      text: 'Фоновый обход помогает постепенно и детерминированно актуализировать состояние всего публичного каталога. Планировщик плавно распределяет репозитории каталога по времени, обеспечивая равномерную нагрузку на анализаторы.',
      badge: 'Фоновый каталог',
      badgeClass: 'is-planned',
    },
  };

  const current = levelDescriptions[selectedLevel];

  return (
    <article className="sh-stack-legend-card" aria-label="Описание архитектуры очереди">
      <div className="sh-legend-header">
        <h2 className="sh-legend-title">{current.title}</h2>
        <span className={`sh-counter-badge ${current.badgeClass}`}>{current.badge}</span>
      </div>

      <p className="sh-legend-desc">{current.text}</p>

      {/* Scheduling Invariants & Truth Note */}
      <div className="sh-invariants-box">
        <div className="sh-invariants-title">Режимы обработки SourceHealth</div>
        <div>
          • <strong>Ручной запуск:</strong> анализ по запросу пользователя.
        </div>
        <div>
          • <strong>По расписанию:</strong> повторная проверка после рассчитанного интервала.
        </div>
        <div>
          • <strong>Плановый обход:</strong> постепенная фоновая обработка каталога.
        </div>
        <div>
          • Визуализация показывает логическую модель обработки, а не live telemetry отдельных RQ queues.
        </div>
      </div>

      {/* Controls for Accessibility / Reduced Motion */}
      <div className="sh-presets-bar" aria-label="Управление анимацией">
        <button
          type="button"
          className="sh-preset-btn"
          onClick={onToggleAnimation}
          title={isAnimationPaused ? 'Включить анимацию стека' : 'Приостановить анимацию'}
        >
          {isAnimationPaused ? '▶ Запустить анимацию' : '⏸ Пауза анимации'}
        </button>
      </div>
    </article>
  );
};
