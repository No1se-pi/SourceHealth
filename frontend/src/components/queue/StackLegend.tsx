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
      title: 'Уровень: Приоритетные проверки (Priority)',
      text: 'Проверки, запущенные пользователем или мейнтейнером вручную через кнопку анализа, получают наивысший приоритет. Они исполняются в первую очередь в обход планового расписания, чтобы автор репозитория получил мгновенную обратную связь.',
      badge: 'Приоритет 1 (Мгновенный запуск)',
      badgeClass: 'is-priority',
    },
    timed: {
      title: 'Уровень: Проверки по расписанию (Timed)',
      text: 'Репозитории возвращаются в очередь, когда наступает срок их периодической актуализации (refresh interval). Проекты с высокой частотой коммитов и отслеживаемые репозитории проверяются чаще, экономя вычислительные ресурсы платформы.',
      badge: 'Приоритет 2 (По таймеру)',
      badgeClass: 'is-timed',
    },
    planned: {
      title: 'Уровень: Плановый фоновый обход (Planned)',
      text: 'Фоновый обход помогает постепенно и детерминированно актуализировать состояние всего публичного каталога. Планировщик плавно распределяет репозитории каталога по времени, обеспечивая равномерную нагрузку на анализаторы.',
      badge: 'Приоритет 3 (Фоновый цикл)',
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
        <div className="sh-invariants-title">Принципы честного планирования SourceHealth:</div>
        <div>
          • <strong>Строгая приоритизация:</strong> Priority &gt; Timed &gt; Planned. Задачи ручного анализа не стоят в хвосте очереди каталога.
        </div>
        <div>
          • <strong>Честность данных:</strong> Визуализация очереди отражает архитектурную модель стека. Платформа не фабрикует фиктивные события «repository completed», если статус не подтверждён фактическим анализом.
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
