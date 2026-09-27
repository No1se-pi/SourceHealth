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

export const LeaderboardPage: React.FC = () => {
  usePageTitle('Каталог и поиск проектов');

  const [searchParams, setSearchParams] = useSearchParams();

  // Read URL params
  const qParam = searchParams.get('q') || '';
  const pageParam = parseInt(searchParams.get('page') || '1', 10);
  const pageSizeParam = parseInt(searchParams.get('page_size') || '20', 10);
  const sortParam = searchParams.get('sort') || 'health_score';
  const orderParam = searchParams.get('order') || 'desc';
  const langParam = searchParams.get('language') || '';
  const topicParam = searchParams.get('topic') || '';
  const originParam = searchParams.get('origin') || '';
  const healthStatusParam = searchParams.get('health_status') || '';
  const healthMinParam = searchParams.get('health_min');
  const healthMaxParam = searchParams.get('health_max');
  const secMinParam = searchParams.get('security_min');
  const secStatusParam = searchParams.get('security_status') || '';
  const covMinParam = searchParams.get('coverage_min');
  const actDaysParam = searchParams.get('activity_days');

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
      sort: sortParam,
      order: orderParam,
      q: qParam || undefined,
      language: langParam || undefined,
      topic: topicParam || undefined,
      origin: originParam || undefined,
      health_status: healthStatusParam || undefined,
      health_min: healthMinParam ? Number(healthMinParam) : undefined,
      health_max: healthMaxParam ? Number(healthMaxParam) : undefined,
      security_min: secMinParam ? Number(secMinParam) : undefined,
      security_status: secStatusParam || undefined,
      coverage_min: covMinParam ? Number(covMinParam) : undefined,
      activity_days: actDaysParam ? Number(actDaysParam) : undefined,
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
    secMinParam,
    secStatusParam,
    covMinParam,
    actDaysParam,
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
    security_min: secMinParam ? Number(secMinParam) : undefined,
    security_status: secStatusParam || undefined,
    coverage_min: covMinParam ? Number(covMinParam) : undefined,
    activity_days: actDaysParam ? Number(actDaysParam) : undefined,
  };

  const handleRemoveFilter = (key: keyof ActiveFiltersState) => {
    if (key === 'health_min' || key === 'health_max') {
      updateParams({ health_min: undefined, health_max: undefined, page: 1 });
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
              value={sortParam}
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
              {qParam && <option value="relevance">По релевантности поиска</option>}
              <option value="health_score">По Health score</option>
              <option value="likes">По лайкам</option>
              <option value="last_activity">По последней активности</option>
              <option value="name">По имени (A–Z)</option>
              <option value="security">По безопасности (AppSec)</option>
              <option value="cicd">По CI/CD</option>
              <option value="code_health">По качеству кода</option>
              <option value="coverage">По покрытию тестами</option>
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
                {qParam && qParam.includes('/') && (
                  <Button
                    variant="primary"
                    onClick={() => {
                      api
                        .importRepository(qParam.trim())
                        .then((res) => {
                          window.location.href = `/repositories/${res.id}`;
                        })
                        .catch(setError);
                    }}
                  >
                    Импортировать «{qParam.trim()}» из SourceCraft
                  </Button>
                )}
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
            <div className="leaderboard-mobile" style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
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
