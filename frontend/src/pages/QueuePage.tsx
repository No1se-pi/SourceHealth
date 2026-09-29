import React, { useEffect, useState } from 'react';
import { loadCatalogMetrics, type CatalogLiveMetrics } from '../api/queueData';
import { AnalysisStack } from '../components/queue/AnalysisStack';
import { StackCounters } from '../components/queue/StackCounters';
import { StackLegend } from '../components/queue/StackLegend';
import { usePageTitle } from '../utils/usePageTitle';

export const QueuePage: React.FC = () => {
  usePageTitle('Очередь анализа');

  const [catalogMetrics, setCatalogMetrics] = useState<CatalogLiveMetrics>({
    catalogTotal: null,
    healthAnalyzed: null,
    loaded: false,
  });
  const [selectedLevel, setSelectedLevel] = useState<'priority' | 'timed' | 'planned'>('priority');
  const [isAnimationPaused, setIsAnimationPaused] = useState(false);

  useEffect(() => {
    let active = true;

    loadCatalogMetrics()
      .then((res) => {
        if (active) {
          setCatalogMetrics(res);
        }
      })
      .catch(() => {
        // Fallback remains active without mock numbers
      });

    return () => {
      active = false;
    };
  }, []);

  return (
    <main className="sh-queue-page" id="main-content">
      {/* Header with Title and Live Status Indicator */}
      <header className="sh-queue-header">
        <div className="sh-queue-title-wrap">
          <h1 className="sh-queue-title">Очередь анализа</h1>
          <p className="sh-queue-subtitle">
            Так SourceHealth объединяет ручные запуски, повторные проверки по расписанию и плановый обход каталога.
          </p>

          <div className="sh-queue-status-bar" role="status" aria-live="polite">
            <span className="sh-status-indicator">
              <span className="sh-status-pulse-dot" aria-hidden="true" />
              <span>Схема обработки</span>
            </span>

            {catalogMetrics.loaded && catalogMetrics.catalogTotal !== null ? (
              <>
                <span className="sh-status-divider" aria-hidden="true" />
                <span>
                  {catalogMetrics.catalogTotal.toLocaleString('ru-RU')} репозиториев в каталоге
                </span>
                {catalogMetrics.healthAnalyzed !== null && (
                  <>
                    <span className="sh-status-divider" aria-hidden="true" />
                    <span>
                      {catalogMetrics.healthAnalyzed.toLocaleString('ru-RU')} с рассчитанным Health
                    </span>
                  </>
                )}
              </>
            ) : (
              <>
                <span className="sh-status-divider" aria-hidden="true" />
                <span>Данные каталога недоступны</span>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Main 3D Stack Hero, Counters & Architecture Legend */}
      <AnalysisStack
        selectedLevel={selectedLevel}
        onSelectLevel={setSelectedLevel}
        isAnimationPaused={isAnimationPaused}
      />

      <StackCounters
        catalogMetrics={catalogMetrics}
        selectedLevel={selectedLevel}
        onSelectLevel={setSelectedLevel}
      />

      <StackLegend
        selectedLevel={selectedLevel}
        onSelectLevel={setSelectedLevel}
        isAnimationPaused={isAnimationPaused}
        onToggleAnimation={() => setIsAnimationPaused((prev) => !prev)}
      />
    </main>
  );
};
