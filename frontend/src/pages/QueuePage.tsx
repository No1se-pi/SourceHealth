import React, { useEffect, useState } from 'react';
import { getInitialQueueData, loadQueueData, type AnalysisStackData, type QueueDataPreset } from '../api/queueData';
import { AnalysisStack } from '../components/queue/AnalysisStack';
import { StackCounters } from '../components/queue/StackCounters';
import { StackLegend } from '../components/queue/StackLegend';
import { LoadingState } from '../components/common/LoadingState';
import { usePageTitle } from '../utils/usePageTitle';

export const QueuePage: React.FC = () => {
  usePageTitle('Очередь анализа');

  const [preset, setPreset] = useState<QueueDataPreset>('real');
  const [data, setData] = useState<AnalysisStackData>(() => getInitialQueueData('real'));
  const [loading, setLoading] = useState(false);
  const [selectedLevel, setSelectedLevel] = useState<'priority' | 'timed' | 'planned'>('priority');
  const [isAnimationPaused, setIsAnimationPaused] = useState(false);

  useEffect(() => {
    let active = true;
    setData(getInitialQueueData(preset));

    loadQueueData(preset)
      .then((res) => {
        if (active) {
          setData(res);
        }
      })
      .catch(() => {
        // Fallback remains active
      });

    return () => {
      active = false;
    };
  }, [preset]);

  return (
    <main className="sh-queue-page" id="main-content">
      {/* Header with Title and Live Status Indicator */}
      <header className="sh-queue-header">
        <div className="sh-queue-title-wrap">
          <h1 className="sh-queue-title">Очередь анализа</h1>
          <p className="sh-queue-subtitle">
            Так SourceHealth распределяет проверки репозиториев между срочными запросами и плановым обходом каталога.
          </p>

          <div className="sh-queue-status-bar" role="status" aria-live="polite">
            <span className="sh-status-indicator">
              <span className="sh-status-pulse-dot" aria-hidden="true" />
              <span>Планировщик активен</span>
            </span>

            {data && (
              <>
                <span className="sh-status-divider" aria-hidden="true" />
                <span>
                  {data.catalogTotal.toLocaleString('ru-RU')} репозиториев в каталоге
                </span>
                <span className="sh-status-divider" aria-hidden="true" />
                <span>
                  {data.healthAnalyzed.toLocaleString('ru-RU')} с рассчитанным Health
                </span>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Main 3D Stack Hero, Counters & Architecture Legend */}
      {loading && !data ? (
        <LoadingState message="Инициализация очереди анализа..." />
      ) : data ? (
        <>
          <AnalysisStack
            data={data}
            selectedLevel={selectedLevel}
            onSelectLevel={setSelectedLevel}
            isAnimationPaused={isAnimationPaused}
          />

          <StackCounters
            data={data}
            selectedLevel={selectedLevel}
            onSelectLevel={setSelectedLevel}
          />

          <StackLegend
            selectedLevel={selectedLevel}
            onSelectLevel={setSelectedLevel}
            activePreset={preset}
            onSelectPreset={setPreset}
            isAnimationPaused={isAnimationPaused}
            onToggleAnimation={() => setIsAnimationPaused((prev) => !prev)}
          />
        </>
      ) : null}
    </main>
  );
};
