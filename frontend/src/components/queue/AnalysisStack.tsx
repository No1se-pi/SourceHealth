import React, { useEffect, useState } from 'react';
import { StackLayer } from './StackLayer';

export interface AnalysisStackProps {
  selectedLevel: 'priority' | 'timed' | 'planned' | null;
  onSelectLevel: (level: 'priority' | 'timed' | 'planned') => void;
  isAnimationPaused?: boolean;
}

export const AnalysisStack: React.FC<AnalysisStackProps> = ({
  selectedLevel,
  onSelectLevel,
  isAnimationPaused = false,
}) => {
  const [isTopCycling, setIsTopCycling] = useState(false);

  // Ambient 60 FPS CSS transform cycle: every 6.5s the top item floats and dissolves
  // Represents conceptual processing dynamics without claiming any individual repository completion
  useEffect(() => {
    if (isAnimationPaused) {
      setIsTopCycling(false);
      return;
    }

    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    const intervalId = setInterval(() => {
      setIsTopCycling(true);
      timeoutId = setTimeout(() => {
        setIsTopCycling(false);
      }, 850);
    }, 6500);

    return () => {
      clearInterval(intervalId);
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, [isAnimationPaused]);

  // Construct conceptual stack layers configuration:
  // Planned (7 plates at base) -> Timed (4 plates in middle) -> Priority (3 plates at apex)
  const plannedPlateCount = 7;
  const timedPlateCount = 4;
  const priorityPlateCount = 3;

  const pitch = 14; // vertical distance in px along 3D Z axis

  interface PlateSpec {
    id: string;
    level: 'priority' | 'timed' | 'planned';
    zOffset: number;
    isTopInLevel: boolean;
    isTopOverall: boolean;
  }

  const plates: PlateSpec[] = [];
  let currentZ = 0;

  // 1. Planned Plates (Base)
  for (let i = 0; i < plannedPlateCount; i++) {
    plates.push({
      id: `planned-${i}`,
      level: 'planned',
      zOffset: currentZ,
      isTopInLevel: i === plannedPlateCount - 1,
      isTopOverall: false,
    });
    currentZ += pitch;
  }

  // 2. Timed Plates (Middle)
  currentZ += 4; // slight gap separating levels
  for (let i = 0; i < timedPlateCount; i++) {
    plates.push({
      id: `timed-${i}`,
      level: 'timed',
      zOffset: currentZ,
      isTopInLevel: i === timedPlateCount - 1,
      isTopOverall: false,
    });
    currentZ += pitch;
  }

  // 3. Priority Plates (Apex)
  currentZ += 4; // slight gap separating levels
  for (let i = 0; i < priorityPlateCount; i++) {
    const isTop = i === priorityPlateCount - 1;
    plates.push({
      id: `priority-${i}`,
      level: 'priority',
      zOffset: currentZ,
      isTopInLevel: isTop,
      isTopOverall: isTop,
    });
    currentZ += pitch;
  }

  return (
    <section className="sh-stack-hero-section" aria-label="Изометрический концептуальный стек очереди">
      <div className="sh-stack-viewport">
        {/* 3D Isometric Stage */}
        <div
          className={`sh-stack-stage ${selectedLevel ? 'has-selected' : ''}`}
          role="region"
          aria-label="Интерактивный стек"
        >
          {plates.map((plate) => (
            <StackLayer
              key={plate.id}
              level={plate.level}
              zOffset={plate.zOffset}
              isTopInLevel={plate.isTopInLevel}
              isTopOverall={plate.isTopOverall}
              isCycling={plate.isTopOverall && isTopCycling}
              isSelectedLevel={selectedLevel === plate.level}
              onSelect={() => onSelectLevel(plate.level)}
            />
          ))}
        </div>

        {/* 2D HUD Callout Overlay (Clear Conceptual Labels Aligned Beside the 3D Stack) */}
        <aside className="sh-stack-hud" aria-label="Уровни планирования">
          {/* Priority Callout */}
          <div
            className={`sh-hud-tag is-priority ${selectedLevel === 'priority' ? 'is-active' : ''}`}
            onClick={() => onSelectLevel('priority')}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onSelectLevel('priority')}
          >
            <span className="sh-hud-tag-title">ПРИОРИТЕТ</span>
            <span className="sh-hud-tag-count">Ручные проверки</span>
          </div>

          {/* Timed Callout */}
          <div
            className={`sh-hud-tag is-timed ${selectedLevel === 'timed' ? 'is-active' : ''}`}
            onClick={() => onSelectLevel('timed')}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onSelectLevel('timed')}
          >
            <span className="sh-hud-tag-title">ПО РАСПИСАНИЮ</span>
            <span className="sh-hud-tag-count">Интервалы</span>
          </div>

          {/* Planned Callout */}
          <div
            className={`sh-hud-tag is-planned ${selectedLevel === 'planned' ? 'is-active' : ''}`}
            onClick={() => onSelectLevel('planned')}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onSelectLevel('planned')}
          >
            <span className="sh-hud-tag-title">ПЛАНОВЫЙ ОБХОД</span>
            <span className="sh-hud-tag-count">Фоновая проверка</span>
          </div>
        </aside>
      </div>
    </section>
  );
};
