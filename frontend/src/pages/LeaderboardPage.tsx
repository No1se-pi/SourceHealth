import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  api,
  type Repository,
  type RepositoryPage,
  type CatalogStats,
} from '../api/client';
import { Card } from '../components/common/Card';
import { Button, getButtonStyles } from '../components/common/Button';
import { ScoreDisplay } from '../components/common/ScoreDisplay';
import { LoadingState } from '../components/common/LoadingState';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { RepositoryImport } from '../components/common/RepositoryImport';
import { SourceSoul } from '../components/common/SourceSoul';
import { usePageTitle } from '../utils/usePageTitle';
import { formatLikes } from '../utils/formatters';

// Catalog v2 components
import { CatalogHero } from '../components/catalog/CatalogHero';
import { HealthHistogram } from '../components/catalog/HealthHistogram';
import { CatalogSearchBar } from '../components/catalog/CatalogSearchBar';
import { TopicChips } from '../components/catalog/TopicChips';
import { ActiveFilterChips, type ActiveFiltersState } from '../components/catalog/ActiveFilterChips';
import { AdvancedFiltersModal } from '../components/catalog/AdvancedFiltersModal';
import { CatalogPagination } from '../components/catalog/CatalogPagination';
import { RepositoryAvatar } from '../components/catalog/RepositoryAvatar';
import { CategoryMiniBars } from '../components/catalog/CategoryMiniBars';
import { CompareTray } from '../components/catalog/CompareTray';
import { CommandPalette } from '../components/catalog/CommandPalette';

function formatLastActivity(timestamp: string | null | undefined): string {
  if (!timestamp) return '—';
  const date = new Date(timestamp);
  if (isNaN(date.getTime())) return '—';

  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return 'Сегодня';
  if (diffDays === 1) return 'Вчера';
  if (diffDays > 1 && diffDays < 7) return `${diffDays} дн. назад`;

  return date.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

const ORIGIN_BADGES: Record<string, { label: string; color: string }> = {
  native: { label: 'Native', color: '#16a34a' },
  fork: { label: 'Fork', color: '#7c3aed' },
  migrated: { label: 'Migrated', color: '#0891b2' },
  unknown: { label: 'External', color: '#64748b' },
};

const SUPPORTED_PAGE_SIZES = [20, 50, 100] as const;
const DEFAULT_PAGE_SIZE = 20;
const DEFAULT_PAGE = 1;

export function sanitizePage(val: unknown): number {
  if (val === null || val === undefined) return DEFAULT_PAGE;
  const num = typeof val === 'number' ? val : parseInt(String(val), 10);
  if (isNaN(num) || num < 1 || !isFinite(num)) return DEFAULT_PAGE;
  return Math.floor(num);
}

export function sanitizePageSize(val: unknown): number {
  if (val === null || val === undefined) return DEFAULT_PAGE_SIZE;
  const num = typeof val === 'number' ? val : parseInt(String(val), 10);
  if (isNaN(num) || !SUPPORTED_PAGE_SIZES.includes(num as any)) return DEFAULT_PAGE_SIZE;
  return num;
}

export function getValidImportUrl(query: string | null | undefined): string | null {
  if (!query) return null;
  const trimmed = query.trim();

  // Case 1: canonical or standard SourceCraft URL
  const urlMatch = trimmed.match(/^https?:\/\/(?:www\.)?sourcecraft\.dev\/([a-zA-Z0-9_.-]+)\/([a-zA-Z0-9_.-]+)\/?$/i);
  if (urlMatch) {
    return `https://sourcecraft.dev/${urlMatch[1]}/${urlMatch[2]}`;
  }

  // Case 2: strict org/repo slug
  const slugMatch = trimmed.match(/^([a-zA-Z0-9_.-]+)\/([a-zA-Z0-9_.-]+)$/);
  if (slugMatch) {
    return `https://sourcecraft.dev/${slugMatch[1]}/${slugMatch[2]}`;
  }

  return null;
}

export const LeaderboardPage: React.FC = () => {
  usePageTitle('Каталог и поиск проектов');

  const [searchParams, setSearchParams] = useSearchParams();

  // Read and sanitize URL params
  const qParam = searchParams.get('q') || '';
  const rawPage = searchParams.get('page');
  const rawPageSize = searchParams.get('page_size');
  const pageParam = sanitizePage(rawPage);
  const pageSizeParam = sanitizePageSize(rawPageSize);
  const sortParam = searchParams.get('sort');
  const orderParam = searchParams.get('order') || 'desc';
  const effectiveSort = sortParam || (qParam ? 'relevance' : 'health_score');

  const langParam = searchParams.get('language') || '';
  const topicParam = searchParams.get('topic') || '';
  const originParam = searchParams.get('origin') || '';
  const healthStatusParam = searchParams.get('health_status') || '';
  const healthMinParam = searchParams.get('health_min');
  const healthMaxParam = searchParams.get('health_max');
  const covMinParam = searchParams.get('coverage_min');
  const actDaysParam = searchParams.get('activity_days');

  // Six categories
  const secMinParam = searchParams.get('security_min');
  const secMaxParam = searchParams.get('security_max');
  const secStatusParam = searchParams.get('security_status') || '';

  const cicdMinParam = searchParams.get('cicd_min');
  const cicdMaxParam = searchParams.get('cicd_max');
  const cicdStatusParam = searchParams.get('cicd_status') || '';

  const actMinParam = searchParams.get('activity_min');
  const actMaxParam = searchParams.get('activity_max');
  const actStatusParam = searchParams.get('activity_status') || '';

  const docMinParam = searchParams.get('documentation_min');
  const docMaxParam = searchParams.get('documentation_max');
  const docStatusParam = searchParams.get('documentation_status') || '';

  const issuesMinParam = searchParams.get('issues_min');
  const issuesMaxParam = searchParams.get('issues_max');
  const issuesStatusParam = searchParams.get('issues_status') || '';

  const codeMinParam = searchParams.get('code_health_min');
  const codeMaxParam = searchParams.get('code_health_max');
  const codeStatusParam = searchParams.get('code_health_status') || '';

  // Search input local state for debouncing
  const [searchInput, setSearchInput] = useState(qParam);

  // Data states
  const [page, setPage] = useState<RepositoryPage>();
  const [stats, setStats] = useState<CatalogStats>();
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);
  const [error, setError] = useState<unknown>();

  // Modals & Trays
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [selectedRepos, setSelectedRepos] = useState<Repository[]>([]);

  const requestGenRef = useRef(0);

  // Sync search input when URL changes externally
  useEffect(() => {
    setSearchInput(qParam);
  }, [qParam]);

  // Canonicalize URL in background if invalid page/page_size was provided
  useEffect(() => {
    let changed = false;
    const next = new URLSearchParams(searchParams);
    if (rawPage !== null && (String(pageParam) !== rawPage || pageParam === DEFAULT_PAGE)) {
      if (pageParam === DEFAULT_PAGE) {
        next.delete('page');
      } else {
        next.set('page', String(pageParam));
      }
      changed = true;
    }
    if (rawPageSize !== null && (String(pageSizeParam) !== rawPageSize || pageSizeParam === DEFAULT_PAGE_SIZE)) {
      if (pageSizeParam === DEFAULT_PAGE_SIZE) {
        next.delete('page_size');
      } else {
        next.set('page_size', String(pageSizeParam));
      }
      changed = true;
    }
    if (changed) {
      setSearchParams(next, { replace: true });
    }
  }, [rawPage, rawPageSize, pageParam, pageSizeParam, searchParams, setSearchParams]);

  // Debounced search query sync to URL
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchInput !== qParam) {
        const next = new URLSearchParams(searchParams);
        if (searchInput.trim()) {
          next.set('q', searchInput.trim());
        } else {
          next.delete('q');
        }
        next.set('page', '1');
        setSearchParams(next, { replace: true });
      }
    }, 280);
    return () => clearTimeout(timer);
  }, [searchInput, qParam, searchParams, setSearchParams]);

  // Helper to update URL params
  const updateParams = useCallback(
    (updates: Record<string, string | number | undefined | null>) => {
      const next = new URLSearchParams(searchParams);
      for (const [key, value] of Object.entries(updates)) {
        if (value === undefined || value === null || value === '') {
          next.delete(key);
        } else {
          next.set(key, String(value));
        }
      }
      setSearchParams(next);
    },
    [searchParams, setSearchParams],
  );

  // Fetch repositories & catalog stats
  const fetchData = useCallback(() => {
    const currentGen = ++requestGenRef.current;
    setLoading(true);
    setStatsLoading(true);
    setError(undefined);

    const offset = (Math.max(1, pageParam) - 1) * pageSizeParam;

    const queryParams: Record<string, string | number | undefined> = {
      offset,
      limit: pageSizeParam,
      sort: sortParam || undefined,
      order: orderParam,
      q: qParam || undefined,
      language: langParam || undefined,
      topic: topicParam || undefined,
      origin: originParam || undefined,
      health_status: healthStatusParam || undefined,
      health_min: healthMinParam ? Number(healthMinParam) : undefined,
      health_max: healthMaxParam ? Number(healthMaxParam) : undefined,
      coverage_min: covMinParam ? Number(covMinParam) : undefined,
      activity_days: actDaysParam ? Number(actDaysParam) : undefined,

      security_min: secMinParam ? Number(secMinParam) : undefined,
      security_max: secMaxParam ? Number(secMaxParam) : undefined,
      security_status: secStatusParam || undefined,

      cicd_min: cicdMinParam ? Number(cicdMinParam) : undefined,
      cicd_max: cicdMaxParam ? Number(cicdMaxParam) : undefined,
      cicd_status: cicdStatusParam || undefined,

      activity_min: actMinParam ? Number(actMinParam) : undefined,
      activity_max: actMaxParam ? Number(actMaxParam) : undefined,
      activity_status: actStatusParam || undefined,

      documentation_min: docMinParam ? Number(docMinParam) : undefined,
      documentation_max: docMaxParam ? Number(docMaxParam) : undefined,
      documentation_status: docStatusParam || undefined,

      issues_min: issuesMinParam ? Number(issuesMinParam) : undefined,
      issues_max: issuesMaxParam ? Number(issuesMaxParam) : undefined,
      issues_status: issuesStatusParam || undefined,

      code_health_min: codeMinParam ? Number(codeMinParam) : undefined,
      code_health_max: codeMaxParam ? Number(codeMaxParam) : undefined,
      code_health_status: codeStatusParam || undefined,
    };

    // 1. Fetch Repositories
    api
      .repositories(queryParams)
      .then((res) => {
        if (requestGenRef.current === currentGen) {
          setPage(res);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (requestGenRef.current === currentGen) {
          setError(err);
          setLoading(false);
        }
      });

    // 2. Fetch Catalog Stats
    api
      .catalogStats(queryParams)
      .then((st) => {
        if (requestGenRef.current === currentGen) {
          setStats(st);
          setStatsLoading(false);
        }
      })
      .catch(() => {
        if (requestGenRef.current === currentGen) {
          setStatsLoading(false);
        }
      });
  }, [
    pageParam,
    pageSizeParam,
    sortParam,
    orderParam,
    qParam,
    langParam,
    topicParam,
    originParam,
    healthStatusParam,
    healthMinParam,
    healthMaxParam,
    covMinParam,
    actDaysParam,
    secMinParam,
    secMaxParam,
    secStatusParam,
    cicdMinParam,
    cicdMaxParam,
    cicdStatusParam,
    actMinParam,
    actMaxParam,
    actStatusParam,
    docMinParam,
    docMaxParam,
    docStatusParam,
    issuesMinParam,
    issuesMaxParam,
    issuesStatusParam,
    codeMinParam,
    codeMaxParam,
    codeStatusParam,
  ]);

  useEffect(() => {
    fetchData();
    return () => {
      requestGenRef.current++;
    };
  }, [fetchData]);

  // Active filters object for chips
  const activeFilters: ActiveFiltersState = {
    q: qParam || undefined,
    language: langParam || undefined,
    topic: topicParam || undefined,
    origin: originParam || undefined,
    health_status: healthStatusParam || undefined,
    health_min: healthMinParam ? Number(healthMinParam) : undefined,
    health_max: healthMaxParam ? Number(healthMaxParam) : undefined,
    coverage_min: covMinParam ? Number(covMinParam) : undefined,
    activity_days: actDaysParam ? Number(actDaysParam) : undefined,

    security_min: secMinParam ? Number(secMinParam) : undefined,
    security_max: secMaxParam ? Number(secMaxParam) : undefined,
    security_status: secStatusParam || undefined,

    cicd_min: cicdMinParam ? Number(cicdMinParam) : undefined,
    cicd_max: cicdMaxParam ? Number(cicdMaxParam) : undefined,
    cicd_status: cicdStatusParam || undefined,

    activity_min: actMinParam ? Number(actMinParam) : undefined,
    activity_max: actMaxParam ? Number(actMaxParam) : undefined,
    activity_status: actStatusParam || undefined,

    documentation_min: docMinParam ? Number(docMinParam) : undefined,
    documentation_max: docMaxParam ? Number(docMaxParam) : undefined,
    documentation_status: docStatusParam || undefined,

    issues_min: issuesMinParam ? Number(issuesMinParam) : undefined,
    issues_max: issuesMaxParam ? Number(issuesMaxParam) : undefined,
    issues_status: issuesStatusParam || undefined,

    code_health_min: codeMinParam ? Number(codeMinParam) : undefined,
    code_health_max: codeMaxParam ? Number(codeMaxParam) : undefined,
    code_health_status: codeStatusParam || undefined,
  };

  const handleRemoveFilter = (key: keyof ActiveFiltersState) => {
    if (key === 'health_min' || key === 'health_max') {
      updateParams({ health_min: undefined, health_max: undefined, page: 1 });
    } else if (key === 'security_min' || key === 'security_max') {
      updateParams({ security_min: undefined, security_max: undefined, page: 1 });
    } else if (key === 'cicd_min' || key === 'cicd_max') {
      updateParams({ cicd_min: undefined, cicd_max: undefined, page: 1 });
    } else if (key === 'activity_min' || key === 'activity_max') {
      updateParams({ activity_min: undefined, activity_max: undefined, page: 1 });
    } else if (key === 'documentation_min' || key === 'documentation_max') {
      updateParams({ documentation_min: undefined, documentation_max: undefined, page: 1 });
    } else if (key === 'issues_min' || key === 'issues_max') {
      updateParams({ issues_min: undefined, issues_max: undefined, page: 1 });
    } else if (key === 'code_health_min' || key === 'code_health_max') {
      updateParams({ code_health_min: undefined, code_health_max: undefined, page: 1 });
    } else if (key === 'q') {
      setSearchInput('');
      updateParams({ q: undefined, page: 1 });
    } else {
      updateParams({ [key]: undefined, page: 1 });
    }
  };

  const handleResetAllFilters = () => {
    setSearchInput('');
    setSearchParams(new URLSearchParams());
  };

  // Histogram click handler
  const handleHistogramSelect = (min?: number, max?: number, isNoData?: boolean) => {
    if (isNoData) {
      if (healthStatusParam === 'no_data') {
        updateParams({ health_status: undefined, page: 1 });
      } else {
        updateParams({ health_status: 'no_data', health_min: undefined, health_max: undefined, page: 1 });
      }
    } else if (min != null && max != null) {
      if (Number(healthMinParam) === min && Number(healthMaxParam) === max) {
        updateParams({ health_min: undefined, health_max: undefined, page: 1 });
      } else {
        updateParams({ health_min: min, health_max: max, health_status: undefined, page: 1 });
      }
    }
  };

  // Compare selection toggle
  const toggleSelectRepo = (repo: Repository) => {
    setSelectedRepos((prev) => {
      const exists = prev.some((r) => r.id === repo.id);
      if (exists) {
        return prev.filter((r) => r.id !== repo.id);
      }
      if (prev.length >= 4) {
        return prev;
      }
      return [...prev, repo];
    });
  };

  const totalItems = page?.total ?? (page ? page.items.length : 0);
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSizeParam));

  // Count active non-default filters
  const activeFiltersCount = Object.values(activeFilters).filter((v) => v !== undefined && v !== '').length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-4)' }}>
      {/* Page Title & Mission */}
      <div>
        <h1 style={{ margin: '0 0 var(--sh-space-1) 0' }}>Каталог открытых проектов SourceCraft</h1>
        <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--sh-text-secondary)' }}>
          Полноценный каталог качества, надежности и безопасности репозиториев платформы SourceCraft · Принцип: NO_DATA ≠ 0
        </p>
      </div>

      {/* Direct Import Banner */}
      <RepositoryImport />

      {/* Catalog Overview Statistics & Quartiles */}
      <CatalogHero stats={stats} loading={statsLoading} />

      {/* Health Distribution Histogram */}
      <HealthHistogram
        buckets={stats?.health_histogram}
        noDataCount={stats?.histogram_no_data_count ?? stats?.health_no_data_count}
        totalAnalyzed={stats?.analyzed_count}
        selectedRange={
          healthMinParam != null && healthMaxParam != null
            ? { min: Number(healthMinParam), max: Number(healthMaxParam) }
            : null
        }
        selectedNoData={healthStatusParam === 'no_data'}
        onSelectBucket={handleHistogramSelect}
      />

      <Card>
        {/* Search, Filter Drawer Button, Sort */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            flexWrap: 'wrap',
            marginBottom: '16px',
          }}
        >
          <div style={{ flex: '1 1 320px' }}>
            <CatalogSearchBar
              value={searchInput}
              onChange={setSearchInput}
              onClear={() => {
                setSearchInput('');
                updateParams({ q: undefined, page: 1 });
              }}
              onOpenCommandPalette={() => setIsCommandPaletteOpen(true)}
            />
          </div>

          {/* Advanced Filters Button */}
          <button
            type="button"
            onClick={() => setIsAdvancedOpen(true)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '9px 14px',
              borderRadius: 'var(--sh-radius-md, 8px)',
              border: '1px solid var(--sh-border-default, #d0d7de)',
              backgroundColor: 'var(--sh-bg-surface, #ffffff)',
              color: 'var(--sh-text-primary, #1f2328)',
              fontSize: '0.875rem',
              fontWeight: 500,
              cursor: 'pointer',
              height: '42px',
            }}
          >
            <span>⚙ Фильтры</span>
            {activeFiltersCount > 0 && (
              <span
                style={{
                  backgroundColor: 'var(--sh-brand, #f93333)',
                  color: '#ffffff',
                  fontSize: '11px',
                  fontWeight: 700,
                  borderRadius: 'var(--sh-radius-full, 9999px)',
                  padding: '1px 6px',
                }}
              >
                {activeFiltersCount}
              </span>
            )}
          </button>

          {/* Language Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <select
              value={langParam}
              onChange={(e) => updateParams({ language: e.target.value || undefined, page: 1 })}
              style={{
                height: '42px',
                padding: '0 12px',
                borderRadius: 'var(--sh-radius-md, 8px)',
                border: '1px solid var(--sh-border-default, #d0d7de)',
                backgroundColor: 'var(--sh-bg-surface, #ffffff)',
                color: 'var(--sh-text-primary, #1f2328)',
                fontSize: '0.875rem',
              }}
              aria-label="Фильтр по языку"
            >
              <option value="">Все языки</option>
              {stats?.languages &&
                Object.entries(stats.languages).map(([lang, count]) => (
                  <option key={lang} value={lang}>
                    {lang} ({count.toLocaleString('ru-RU')})
                  </option>
                ))}
            </select>
          </div>

          {/* Sort Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <select
              value={effectiveSort}
              onChange={(e) => updateParams({ sort: e.target.value, page: 1 })}
              style={{
                height: '42px',
                padding: '0 12px',
                borderRadius: 'var(--sh-radius-md, 8px)',
                border: '1px solid var(--sh-border-default, #d0d7de)',
                backgroundColor: 'var(--sh-bg-surface, #ffffff)',
                color: 'var(--sh-text-primary, #1f2328)',
                fontSize: '0.875rem',
              }}
              aria-label="Сортировка репозиториев"
            >
              <option value="relevance">По релевантности поиска</option>
              <option value="health_score">По общему Health score</option>
              <option value="likes">По числу звёзд / лайков</option>
              <option value="last_activity">По дате активности</option>
              <option value="name">По названию (A–Z)</option>
              <option value="coverage">По охвату данных для Health</option>
              <option value="security">По безопасности (AppSec)</option>
              <option value="cicd">По CI/CD</option>
              <option value="activity">По активности разработки</option>
              <option value="documentation">По документации</option>
              <option value="issues">По обработке дефектов (Issues)</option>
              <option value="code_health">По качеству кода (Code Health)</option>
            </select>

            <button
              type="button"
              onClick={() => updateParams({ order: orderParam === 'asc' ? 'desc' : 'asc', page: 1 })}
              title={orderParam === 'asc' ? 'По возрастанию (нажмите для убывания)' : 'По убыванию (нажмите для возрастания)'}
              style={{
                height: '42px',
                padding: '0 10px',
                borderRadius: 'var(--sh-radius-md, 8px)',
                border: '1px solid var(--sh-border-default, #d0d7de)',
                backgroundColor: 'var(--sh-bg-surface, #ffffff)',
                color: 'var(--sh-text-primary, #1f2328)',
                fontSize: '1rem',
                cursor: 'pointer',
              }}
            >
              {orderParam === 'asc' ? '↑' : '↓'}
            </button>
          </div>
        </div>

        {/* Topic Chips */}
        <TopicChips
          selectedTopic={topicParam}
          topicCounts={stats?.topics}
          onSelectTopic={(t) => updateParams({ topic: t, page: 1 })}
        />

        {/* Active Filters Removable Tags */}
        <ActiveFilterChips
          filters={activeFilters}
          onRemoveFilter={handleRemoveFilter}
          onResetAll={handleResetAllFilters}
        />

        {/* Table & Results Area */}
        {error ? (
          <ErrorState error={error} title="Не удалось загрузить каталог" onRetry={fetchData} />
        ) : loading && !page ? (
          <LoadingState message="Загрузка каталога репозиториев…" />
        ) : !page || page.items.length === 0 ? (
          <EmptyState
            title="Ничего не найдено"
            description={
              qParam
                ? `По запросу «${qParam}» в каталоге не найдено ни одного проекта.`
                : 'По выбранным критериям и фильтрам репозиториев не найдено.'
            }
            action={
              <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', justifyContent: 'center' }}>
                <Button variant="outline" onClick={handleResetAllFilters}>
                  Сбросить все фильтры
                </Button>
                {(() => {
                  const importUrl = getValidImportUrl(qParam);
                  if (!importUrl) return null;
                  return (
                    <Button
                      variant="primary"
                      onClick={() => {
                        api
                          .importRepository(importUrl)
                          .then((res) => {
                            window.location.href = `/repositories/${res.id}`;
                          })
                          .catch(setError);
                      }}
                    >
                      Импортировать «{importUrl}» из SourceCraft
                    </Button>
                  );
                })()}
                <Link to="/demo" className="btn-link" style={getButtonStyles('secondary', 'md')}>
                  Посмотреть демо
                </Link>
              </div>
            }
          />
        ) : (
          <div>
            {/* Desktop Table */}
            <div className="table-responsive-wrapper leaderboard-desktop">
              <table className="leaderboard-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--sh-border-default, #d0d7de)' }}>
                    <th scope="col" style={{ width: '32px', textAlign: 'center' }} aria-label="Сравнить">
                      ✓
                    </th>
                    <th scope="col" style={{ width: '40px', textAlign: 'center' }}>
                      #
                    </th>
                    <th scope="col" style={{ width: '44px' }}></th>
                    <th scope="col">Репозиторий</th>
                    <th scope="col" style={{ width: '130px', textAlign: 'center' }}>
                      Health
                    </th>
                    <th scope="col" style={{ width: '90px', textAlign: 'center' }}>
                      Категории
                    </th>
                    <th scope="col" style={{ width: '90px' }}>Лайки</th>
                    <th scope="col" style={{ width: '110px' }}>Язык</th>
                    <th scope="col" style={{ width: '110px' }}>Активность</th>
                  </tr>
                </thead>
                <tbody>
                  {page.items.map((repo, index) => {
                    const offset = (Math.max(1, pageParam) - 1) * pageSizeParam;
                    const position = offset + index + 1;
                    const isChecked = selectedRepos.some((r) => r.id === repo.id);
                    const originInfo = repo.origin ? ORIGIN_BADGES[repo.origin] : null;

                    return (
                      <tr
                        key={repo.id}
                        style={{
                          borderBottom: '1px solid var(--sh-border-subtle, #e1e4e8)',
                          backgroundColor: isChecked ? 'var(--sh-brand-subtle, rgba(249, 51, 51, 0.04))' : 'inherit',
                        }}
                      >
                        {/* Compare checkbox */}
                        <td style={{ textAlign: 'center' }}>
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => toggleSelectRepo(repo)}
                            title="Выбрать для сравнения (до 4 проектов)"
                            aria-label={`Выбрать ${repo.organization_slug}/${repo.repository_slug} для сравнения`}
                          />
                        </td>

                        {/* Rank */}
                        <td
                          style={{
                            textAlign: 'center',
                            fontFamily: 'var(--sh-font-mono)',
                            color: 'var(--sh-text-muted, #64748b)',
                            fontWeight: 600,
                            fontSize: '0.8125rem',
                          }}
                        >
                          {repo.health_score != null ? position : '—'}
                        </td>

                        {/* Avatar */}
                        <td>
                          <RepositoryAvatar name={repo.repository_slug} logoUrl={repo.logo_url} size={32} />
                        </td>

                        {/* Repository Identity + Description + Origin + Topics */}
                        <td>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                              <Link
                                to={`/repositories/${repo.id}`}
                                title={`${repo.organization_slug}/${repo.repository_slug}`}
                                style={{
                                  fontWeight: 600,
                                  fontSize: '0.9rem',
                                  color: 'var(--sh-text-primary, #1f2328)',
                                  wordBreak: 'break-word',
                                }}
                              >
                                {repo.organization_slug}/{repo.repository_slug}
                              </Link>

                              {originInfo && repo.origin !== 'native' && (
                                <span
                                  style={{
                                    fontSize: '10px',
                                    fontWeight: 600,
                                    padding: '1px 5px',
                                    borderRadius: 'var(--sh-radius-sm, 4px)',
                                    backgroundColor: 'var(--sh-bg-surface-elevated, #f1f3f5)',
                                    color: originInfo.color,
                                    border: '1px solid var(--sh-border-subtle, #e1e4e8)',
                                  }}
                                >
                                  {originInfo.label}
                                </span>
                              )}
                            </div>

                            {repo.description && (
                              <span
                                style={{
                                  fontSize: '0.78rem',
                                  color: 'var(--sh-text-secondary, #475569)',
                                  lineHeight: 1.3,
                                  maxHeight: '2.6em',
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  display: '-webkit-box',
                                  WebkitLineClamp: 2,
                                  WebkitBoxOrient: 'vertical',
                                }}
                              >
                                {repo.description}
                              </span>
                            )}

                            {repo.topics && repo.topics.length > 0 && (
                              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '2px' }}>
                                {repo.topics.slice(0, 3).map((t) => (
                                  <span
                                    key={t}
                                    style={{
                                      fontSize: '10px',
                                      padding: '1px 5px',
                                      borderRadius: '4px',
                                      backgroundColor: 'var(--sh-bg-surface-elevated, #f1f3f5)',
                                      color: 'var(--sh-text-muted, #64748b)',
                                    }}
                                  >
                                    #{t}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        </td>

                        {/* Health Score */}
                        <td style={{ textAlign: 'center' }}>
                          {repo.health_score != null ? (
                            <ScoreDisplay score={repo.health_score} size="md" />
                          ) : (
                            <SourceSoul preview={repo.score_preview} compact />
                          )}
                        </td>

                        {/* Category Mini Bars */}
                        <td style={{ textAlign: 'center' }}>
                          <CategoryMiniBars categories={repo.category_scores} />
                        </td>

                        {/* Likes */}
                        <td style={{ color: 'var(--sh-text-secondary, #475569)', fontSize: '0.85rem' }}>
                          {repo.likes != null ? (
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                              <span>★</span>
                              <span>{formatLikes(repo.likes)}</span>
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>

                        {/* Language */}
                        <td style={{ color: 'var(--sh-text-secondary, #475569)', fontSize: '0.85rem' }}>
                          {repo.language ? (
                            <span
                              style={{
                                display: 'inline-flex',
                                padding: '2px 6px',
                                backgroundColor: 'var(--sh-bg-surface-elevated, #f1f3f5)',
                                border: '1px solid var(--sh-border-default, #d0d7de)',
                                borderRadius: 'var(--sh-radius-sm, 4px)',
                                fontSize: '0.75rem',
                              }}
                            >
                              {repo.language}
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>

                        {/* Last Activity */}
                        <td style={{ color: 'var(--sh-text-secondary, #475569)', fontSize: '0.8125rem' }}>
                          {formatLastActivity(repo.last_activity_at)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Mobile Card List View (< 768px) */}
            <div className="leaderboard-mobile">
              {page.items.map((repo, index) => {
                const offset = (Math.max(1, pageParam) - 1) * pageSizeParam;
                const position = offset + index + 1;
                const isChecked = selectedRepos.some((r) => r.id === repo.id);

                return (
                  <div
                    key={repo.id}
                    style={{
                      padding: '14px',
                      backgroundColor: isChecked
                        ? 'var(--sh-brand-subtle, rgba(249, 51, 51, 0.04))'
                        : 'var(--sh-bg-base, #f6f8fa)',
                      borderRadius: 'var(--sh-radius-md, 8px)',
                      border: '1px solid var(--sh-border-default, #d0d7de)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '8px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleSelectRepo(repo)}
                          aria-label={`Выбрать ${repo.organization_slug}/${repo.repository_slug} для сравнения`}
                        />
                        <RepositoryAvatar name={repo.repository_slug} logoUrl={repo.logo_url} size={28} />
                        <div style={{ minWidth: 0 }}>
                          <span style={{ fontSize: '0.75rem', color: 'var(--sh-text-muted, #64748b)', marginRight: '6px' }}>
                            #{position}
                          </span>
                          <Link
                            to={`/repositories/${repo.id}`}
                            style={{
                              fontWeight: 600,
                              fontSize: '0.875rem',
                              color: 'var(--sh-text-primary, #1f2328)',
                              wordBreak: 'break-word',
                            }}
                          >
                            {repo.organization_slug}/{repo.repository_slug}
                          </Link>
                        </div>
                      </div>

                      {repo.health_score != null ? (
                        <ScoreDisplay score={repo.health_score} size="sm" />
                      ) : (
                        <SourceSoul preview={repo.score_preview} compact />
                      )}
                    </div>

                    {repo.description && (
                      <div
                        style={{
                          fontSize: '0.78rem',
                          color: 'var(--sh-text-secondary, #475569)',
                          lineHeight: 1.3,
                        }}
                      >
                        {repo.description}
                      </div>
                    )}

                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        borderTop: '1px solid var(--sh-border-subtle, #e1e4e8)',
                        paddingTop: '6px',
                        fontSize: '0.75rem',
                        color: 'var(--sh-text-muted, #64748b)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span>{repo.language || '—'}</span>
                        {repo.likes != null && <span>★ {formatLikes(repo.likes)}</span>}
                      </div>
                      <CategoryMiniBars categories={repo.category_scores} />
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Pagination */}
            <CatalogPagination
              currentPage={pageParam}
              totalPages={totalPages}
              totalItems={totalItems}
              pageSize={pageSizeParam}
              onPageChange={(p) => updateParams({ page: p })}
              onPageSizeChange={(ps) => updateParams({ page_size: ps, page: 1 })}
            />
          </div>
        )}
      </Card>

      {/* Floating Compare Tray for 1-4 Repositories */}
      <CompareTray
        selectedRepos={selectedRepos}
        onRemoveRepo={(id) => setSelectedRepos((prev) => prev.filter((r) => r.id !== id))}
        onClearAll={() => setSelectedRepos([])}
      />

      {/* Advanced Filters Modal */}
      <AdvancedFiltersModal
        isOpen={isAdvancedOpen}
        filters={activeFilters}
        onClose={() => setIsAdvancedOpen(false)}
        onApply={(updated) => updateParams({ ...updated, page: 1 })}
        onReset={handleResetAllFilters}
      />

      {/* Command Palette (Ctrl+K) */}
      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        onSelectSearch={(term) => {
          setSearchInput(term);
          updateParams({ q: term, page: 1 });
        }}
      />
    </div>
  );
};
