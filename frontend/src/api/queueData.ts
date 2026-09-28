/**
 * Data structures and adapters for Analysis Queue Architecture Visualization (/queue).
 *
 * Truth invariants:
 * - Real live values are strictly limited to verified catalog stats from /catalog/stats.
 * - If the API is unreachable, catalog metrics evaluate to null/unavailable ("—"),
 *   never falling back to stale historical production snapshots (e.g. 4829, 2995).
 * - Priority, Timed, and Planned tiers are explicitly typed as conceptual architecture models,
 *   not live Redis/RQ queue telemetry.
 * - No fake repository names, mock statuses, or artificial countdown timers are generated.
 */

import { api, type CatalogStats } from './client';

export interface CatalogLiveMetrics {
  catalogTotal: number | null;
  healthAnalyzed: number | null;
  loaded: boolean;
}

export interface QueueTier {
  id: 'priority' | 'timed' | 'planned';
  name: string;
  badge: string;
  badgeVariant: 'priority' | 'timed' | 'planned';
  role: string;
  subtitle: string;
  description: string;
  mode: 'conceptual';
}

export interface QueuePageData {
  catalogMetrics: CatalogLiveMetrics;
  tiers: Record<'priority' | 'timed' | 'planned', QueueTier>;
}

export const CONCEPTUAL_TIERS: Record<'priority' | 'timed' | 'planned', QueueTier> = {
  priority: {
    id: 'priority',
    name: 'Приоритет',
    badge: 'Срочные проверки',
    badgeVariant: 'priority',
    role: 'Запуск по требованию',
    subtitle: 'Ручные запуски пользователей — исполняются в первую очередь',
    description:
      'Проверки, запущенные пользователем или мейнтейнером вручную через кнопку анализа. Они получают наивысший приоритет и обрабатываются в первую очередь в обход планового расписания, обеспечивая мгновенную обратную связь.',
    mode: 'conceptual',
  },
  timed: {
    id: 'timed',
    name: 'По расписанию',
    badge: 'Интервалы',
    badgeVariant: 'timed',
    role: 'Интервальный обход',
    subtitle: 'Репозитории с наступившим сроком межпроверочного интервала',
    description:
      'Репозитории возвращаются в очередь, когда наступает срок их периодической актуализации (refresh interval). Проекты с высокой активностью коммитов и отслеживаемые репозитории проверяются чаще, экономя вычислительные ресурсы платформы.',
    mode: 'conceptual',
  },
  planned: {
    id: 'planned',
    name: 'Плановый обход',
    badge: 'Фоновый каталог',
    badgeVariant: 'planned',
    role: 'Фоновая проверка',
    subtitle: 'Постепенная фоновая проверка каталога для поддержания свежести оценок',
    description:
      'Фоновый плановый обход помогает постепенно и детерминированно актуализировать состояние всех публичных репозиториев каталога. Задачи ставятся порционно, исключая пиковые перегрузки инфраструктуры.',
    mode: 'conceptual',
  },
};

/**
 * Loads verified live catalog metrics from the existing /catalog/stats endpoint.
 * On failure, returns loaded=false with null counts. Never uses stale fallback numbers.
 */
export async function loadCatalogMetrics(): Promise<CatalogLiveMetrics> {
  try {
    const stats: CatalogStats = await api.catalogStats();
    if (typeof stats.catalog_total_public === 'number') {
      return {
        catalogTotal: stats.catalog_total_public,
        healthAnalyzed: typeof stats.health_available_count === 'number' ? stats.health_available_count : null,
        loaded: true,
      };
    }
  } catch {
    // API is offline or network error: return unloaded metrics without fake numbers
  }

  return {
    catalogTotal: null,
    healthAnalyzed: null,
    loaded: false,
  };
}
