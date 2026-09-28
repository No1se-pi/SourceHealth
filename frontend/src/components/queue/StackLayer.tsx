import React from 'react';
import type { StackItem } from '../../api/queueData';

export interface StackLayerProps {
  level: 'priority' | 'timed' | 'planned';
  zOffset: number;
  isTopInLevel: boolean;
  isTopOverall: boolean;
  isCycling: boolean;
  isSelectedLevel: boolean;
  emptyText?: string;
  chips?: StackItem[];
  onSelect: () => void;
}

export const StackLayer: React.FC<StackLayerProps> = ({
  level,
  zOffset,
  isTopInLevel,
  isTopOverall,
  isCycling,
  isSelectedLevel,
  emptyText,
  chips,
  onSelect,
}) => {
  const levelClass = `sh-level-${level}`;
  const selectedClass = isSelectedLevel ? 'is-selected-level' : '';
  const cyclingClass = isCycling ? 'sh-slab-cycling' : '';
  const emptyClass = emptyText ? 'sh-slab-empty' : '';

  return (
    <div
      className={`sh-stack-slab ${levelClass} ${selectedClass} ${cyclingClass} ${emptyClass}`}
      style={{ '--slab-z': `${zOffset}px` } as React.CSSProperties}
      onClick={onSelect}
      role="button"
      tabIndex={0}
      aria-label={`Слой ${level}`}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect();
        }
      }}
    >
      {/* 3D Top Surface */}
      <div className="sh-slab-top">
        {emptyText && (
          <div className="sh-empty-slab-text">{emptyText}</div>
        )}

        {!emptyText && isTopOverall && chips && chips.length > 0 && (
          <div className="sh-slab-content">
            <div className="sh-task-chips-row">
              {chips.slice(0, 3).map((chip) => (
                <span
                  key={chip.id}
                  className={`sh-task-chip ${chip.status === 'analyzing' ? 'is-analyzing' : ''}`}
                  title={`${chip.name} (${chip.status === 'analyzing' ? 'Выполняется' : 'В очереди'})`}
                >
                  <span className="sh-task-chip-dot" aria-hidden="true" />
                  <span>{chip.name}</span>
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 3D Front Thickness Face */}
      <div className="sh-slab-front" aria-hidden="true" />

      {/* 3D Right Depth Face */}
      <div className="sh-slab-right" aria-hidden="true" />

      {/* Cast Shadow */}
      <div className="sh-slab-shadow" aria-hidden="true" />
    </div>
  );
};
