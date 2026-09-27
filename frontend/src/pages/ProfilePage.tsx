import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, type ConnectedRepositories, type Profile, type ApiError } from '../api/client';
import { Card } from '../components/common/Card';
import { Button, getButtonStyles } from '../components/common/Button';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { PageContainer } from '../components/common/PageContainer';
import { SourceSoul } from '../components/common/SourceSoul';
import { ScoreDisplay } from '../components/common/ScoreDisplay';
import { usePageTitle } from '../utils/usePageTitle';
import { formatTtl, formatDateTime, formatRelativeTime } from '../utils/formatters';

const REFRESH_OPTIONS = [
  { value: 'adaptive', label: 'Автоматически' },
  { value: '1h', label: 'Каждый час' },
  { value: '6h', label: 'Каждые 6 часов' },
  { value: '24h', label: 'Раз в сутки' },
  { value: '7d', label: 'Раз в неделю' },
  { value: 'off', label: 'Не обновлять автоматически' },
];

const ACHIEVEMENT_ICONS: Record<string, string> = {
  first_checkup: '✓',
  ghost_hunter: '👻',
  documentation_enjoyer: '📚',
  ci_wizard: '⚙',
  clean_scan: '🛡',
  healthy_project: '◆',
  recovery: '↗',
  maintainer: '★',
};

export const ProfilePage: React.FC = () => {
  usePageTitle('Профиль');

  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [available, setAvailable] = useState<ConnectedRepositories | null>(null);
  const [availableLoading, setAvailableLoading] = useState(false);
  const [availableError, setAvailableError] = useState<unknown | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [loadMoreError, setLoadMoreError] = useState<unknown | null>(null);
  const [trackingRepoId, setTrackingRepoId] = useState<string | null>(null);
  const [trackingError, setTrackingError] = useState<unknown | null>(null);

  const load = () =>
    api
      .profile()
      .then(setProfile)
      .catch((reason) => {
        setError(reason);
      });

  useEffect(() => {
    void load();
  }, []);

  const loadAvailable = useCallback(async () => {
    setAvailableLoading(true);
    setAvailableError(null);
    try {
      setAvailable(await api.mySourcecraftRepositories());
    } catch (reason) {
      setAvailableError(reason);
    } finally {
      setAvailableLoading(false);
    }
  }, []);

  useEffect(() => {
    if (profile?.sourcecraft.connected) {
      void loadAvailable();
    } else {
      setAvailable(null);
      setAvailableError(null);
    }
  }, [loadAvailable, profile?.sourcecraft.connected]);

  const loadMore = async () => {
    if (!available?.next_page_token) return;
    setLoadingMore(true);
    setLoadMoreError(null);
    try {
      const page = await api.mySourcecraftRepositories(available.next_page_token);
      const seen = new Set<string>();
      const items = [...available.items, ...page.items].filter((repo) => {
        const key = repo.id ?? repo.url;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
      setAvailable({ ...page, items });
    } catch (reason) {
      setLoadMoreError(reason);
    } finally {
      setLoadingMore(false);
    }
  };

  const isAuthError = (error as ApiError)?.status === 401 || (error as ApiError)?.code === 'authentication_required';

  if (error && isAuthError) {
    return (
      <PageContainer>
        <div style={{ maxWidth: '600px', margin: '2rem auto' }}>
          <Card title="Требуется авторизация">
            <p style={{ color: 'var(--sh-text-secondary)', marginBottom: '1.25rem', lineHeight: 1.5 }}>
              Войдите через Яндекс ID, чтобы открыть личный профиль, управлять расписанием отслеживаемых репозиториев и просматривать достижения.
            </p>
            <a
              href="/api/v1/auth/yandex/login"
              className="btn-link"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.4rem',
                backgroundColor: 'var(--sh-brand)',
                color: '#fff',
                padding: '0.5rem 1rem',
                borderRadius: 'var(--sh-radius-sm)',
                fontWeight: 600,
                textDecoration: 'none',
              }}
            >
              Войти через Яндекс ID ↗
            </a>
          </Card>
        </div>
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer>
        <h1>Профиль</h1>
        <ErrorState error={error} onRetry={load} />
      </PageContainer>
    );
  }

  if (!profile) {
    return (
      <PageContainer>
        <h1>Профиль</h1>
        <LoadingState message="Загрузка данных профиля…" />
      </PageContainer>
    );
  }

  const unlockedCount = profile.achievements.filter((a) => a.unlocked).length;
  const sortedAchievements = [...profile.achievements].sort((a, b) => {
    if (a.unlocked && !b.unlocked) return -1;
    if (!a.unlocked && b.unlocked) return 1;
    return 0;
  });

  return (
    <PageContainer>
      <div style={{ marginBottom: 'var(--sh-space-4)' }}>
        <h1 style={{ margin: '0 0 var(--sh-space-1) 0' }}>Профиль пользователя</h1>
        <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--sh-text-secondary)' }}>
          Отслеживается проектов: <strong>{profile.repositories.length}</strong> · Достижения:{' '}
          <strong>
            {unlockedCount} / {profile.achievements.length}
          </strong>
        </p>
      </div>

      <div className="growth-grid" style={{ marginBottom: 'var(--sh-space-6)' }}>
        {/* SourceCraft Connection Card */}
        <Card
          title="Подключение SourceCraft"
          headerAction={
            profile.sourcecraft.connected ? (
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  color: 'var(--sh-health-good)',
                  backgroundColor: 'var(--sh-health-good-bg)',
                  border: '1px solid var(--sh-health-good-border)',
                  padding: '0.2rem 0.5rem',
                  borderRadius: 'var(--sh-radius-sm)',
                }}
              >
                ● Подключено
              </span>
            ) : (
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                  fontSize: '0.8rem',
                  color: 'var(--sh-text-muted)',
                  backgroundColor: 'var(--sh-bg-base)',
                  border: '1px solid var(--sh-border-default)',
                  padding: '0.2rem 0.5rem',
                  borderRadius: 'var(--sh-radius-sm)',
                }}
              >
                ○ Не подключено
              </span>
            )
          }
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-3)' }}>
            {profile.sourcecraft.connected ? (
              <>
                <div style={{ fontSize: '0.88rem' }}>
                  Токен действует ещё: <strong>{formatTtl(profile.sourcecraft.expires_in)}</strong>
                </div>

                {profile.sourcecraft.expires_in < 1800 && (
                  <div
                    role="alert"
                    style={{
                      padding: '0.5rem 0.75rem',
                      borderRadius: 'var(--sh-radius-sm)',
                      backgroundColor: 'var(--sh-health-warning-bg)',
                      border: '1px solid var(--sh-health-warning-border)',
                      color: 'var(--sh-health-warning)',
                      fontSize: '0.82rem',
                    }}
                  >
                    ⚠️ Токен скоро истечёт. Обновите PAT в настройках подключения.
                  </div>
                )}

                <p className="growth-muted" style={{ margin: 0, fontSize: '0.82rem' }}>
                  PAT хранится на сервере в зашифрованном виде. При сроке более 30 минут он может использоваться для фонового автоанализа AppSec.
                </p>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
                  <Link
                    to="/sourcecraft"
                    className="btn-link"
                    style={getButtonStyles('secondary', 'sm')}
                  >
                    Настроить подключение
                  </Link>

                  <Button
                    variant="outline"
                    size="sm"
                    onClick={async () => {
                      if (
                        window.confirm(
                          'Удалить сохранённый PAT? Фоновый автоанализ AppSec перестанет его использовать.'
                        )
                      ) {
                        await api.disconnectSourcecraft();
                        void load();
                      }
                    }}
                  >
                    Отключить PAT
                  </Button>
                </div>
              </>
            ) : (
              <>
                <p style={{ margin: 0, fontSize: '0.88rem', color: 'var(--sh-text-secondary)', lineHeight: 1.5 }}>
                  Подключите персональный токен SourceCraft (PAT), чтобы автоматически находить свои репозитории и запускать проверки безопасности AppSec.
                </p>
                <div style={{ marginTop: '0.5rem' }}>
                  <Link
                    to="/sourcecraft"
                    className="btn-link"
                    style={getButtonStyles('primary', 'sm')}
                  >
                    Подключить SourceCraft
                  </Link>
                </div>
              </>
            )}
          </div>
        </Card>

        {/* Tracked Repositories Card */}
        <Card title="Отслеживаемые репозитории" subtitle="Проекты с настроенным периодическим анализом">
          {profile.repositories.length === 0 ? (
            <EmptyState
              title="Пока ничего не отслеживается"
              description="Добавьте репозиторий из каталога или подключите SourceCraft, чтобы настроить периодический мониторинг."
              action={
                <Link to="/" className="btn-link" style={getButtonStyles('secondary', 'sm')}>
                  Открыть рейтинг репозиториев
                </Link>
              }
            />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-4)' }}>
              {profile.repositories.map((repo) => (
                <div
                  className="growth-repository"
                  key={repo.repository_id}
                  style={{
                    padding: 'var(--sh-space-3) var(--sh-space-4)',
                    backgroundColor: 'var(--sh-bg-base)',
                    borderRadius: 'var(--sh-radius-sm)',
                    border: '1px solid var(--sh-border-subtle)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.6rem',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      flexWrap: 'wrap',
                      gap: '0.5rem',
                    }}
                  >
                    <Link
                      to={`/repositories/${repo.repository_id}`}
                      style={{
                        fontWeight: 600,
                        fontSize: '0.95rem',
                        color: 'var(--sh-text-primary)',
                      }}
                    >
                      {repo.organization_slug}/{repo.repository_slug}
                    </Link>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <ScoreDisplay score={repo.health_score} size="sm" />
                      {repo.health_score === null && repo.score_preview && (
                        <SourceSoul preview={repo.score_preview} compact />
                      )}
                    </div>
                  </div>

                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '1rem',
                      fontSize: '0.8rem',
                      color: 'var(--sh-text-muted)',
                      flexWrap: 'wrap',
                    }}
                  >
                    {repo.last_analysis_at ? (
                      <span title={formatDateTime(repo.last_analysis_at)}>
                        Анализ: {formatRelativeTime(repo.last_analysis_at)}
                      </span>
                    ) : (
                      <span>Анализ ещё не выполнялся</span>
                    )}
                    {repo.next_analysis_at && (
                      <span title={formatDateTime(repo.next_analysis_at)}>
                        Следующая проверка: {formatRelativeTime(repo.next_analysis_at)}
                      </span>
                    )}
                  </div>

                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      flexWrap: 'wrap',
                      gap: '0.75rem',
                      paddingTop: '0.35rem',
                      borderTop: '1px solid var(--sh-border-subtle)',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <label
                        htmlFor={`refresh-${repo.repository_id}`}
                        style={{ fontSize: '0.82rem', color: 'var(--sh-text-secondary)', fontWeight: 500 }}
                      >
                        Период:
                      </label>
                      <select
                        id={`refresh-${repo.repository_id}`}
                        value={repo.refresh_preference}
                        onChange={async (event) => {
                          await api.updateTrackedRepository(
                            repo.repository_id,
                            event.target.value,
                            repo.use_pat_for_scheduled_analysis
                          );
                          void load();
                        }}
                        style={{ fontSize: '0.82rem', padding: '0.2rem 0.4rem' }}
                      >
                        {REFRESH_OPTIONS.map((item) => (
                          <option key={item.value} value={item.value}>
                            {item.label}
                          </option>
                        ))}
                      </select>
                    </div>

                    <label
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.35rem',
                        fontSize: '0.82rem',
                        color: !profile.sourcecraft.connected ? 'var(--sh-text-muted)' : 'inherit',
                        cursor: !profile.sourcecraft.connected ? 'not-allowed' : 'pointer',
                      }}
                      title={!profile.sourcecraft.connected ? 'Сначала подключите SourceCraft PAT' : undefined}
                    >
                      <input
                        type="checkbox"
                        checked={repo.use_pat_for_scheduled_analysis}
                        disabled={!profile.sourcecraft.connected}
                        onChange={async (event) => {
                          await api.updateTrackedRepository(
                            repo.repository_id,
                            repo.refresh_preference,
                            event.target.checked
                          );
                          void load();
                        }}
                      />
                      <span>Использовать сохранённый PAT для AppSec при автоанализе</span>
                    </label>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <Link
                        to={`/repositories/${repo.repository_id}`}
                        style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--sh-brand)' }}
                      >
                        Открыть →
                      </Link>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={async () => {
                          if (
                            window.confirm(
                              `Перестать отслеживать ${repo.organization_slug}/${repo.repository_slug}?`
                            )
                          ) {
                            await api.untrackRepository(repo.repository_id);
                            void load();
                          }
                        }}
                      >
                        Не отслеживать
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Available Repositories from PAT */}
      {profile.sourcecraft.connected && (
        <Card
          title="Мои репозитории SourceCraft"
          subtitle="Репозитории, доступные вашему подключённому SourceCraft PAT"
        >
          {availableLoading ? (
            <LoadingState message="Загрузка доступных репозиториев…" />
          ) : availableError ? (
            <ErrorState
              error={availableError}
              title="Не удалось загрузить репозитории SourceCraft"
              onRetry={() => void loadAvailable()}
            />
          ) : !available || available.items.length === 0 ? (
            <EmptyState description="Доступные репозитории не найдены." />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-3)' }}>
              {available.items.map((repo) => {
                const repoKey = repo.id ?? repo.url;
                const isTracking = trackingRepoId === repoKey;
                return (
                  <div
                    className="growth-repository"
                    key={repoKey}
                    style={{
                      padding: '0.6rem 0.85rem',
                      backgroundColor: 'var(--sh-bg-base)',
                      borderRadius: 'var(--sh-radius-sm)',
                      border: '1px solid var(--sh-border-subtle)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      flexWrap: 'wrap',
                      gap: '0.5rem',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
                      <strong style={{ fontSize: '0.9rem' }}>
                        {repo.organization_slug}/{repo.repository_slug}
                      </strong>
                      <span
                        style={{
                          fontSize: '0.75rem',
                          padding: '0.15rem 0.45rem',
                          borderRadius: 'var(--sh-radius-sm)',
                          backgroundColor: repo.visibility === 'private' ? 'var(--sh-health-warning-bg)' : 'var(--sh-bg-surface-elevated)',
                          color: repo.visibility === 'private' ? 'var(--sh-health-warning)' : 'var(--sh-text-muted)',
                          border: '1px solid var(--sh-border-default)',
                        }}
                      >
                        {repo.visibility}
                      </span>
                    </div>

                    <div>
                      {repo.can_analyze ? (
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={isTracking}
                          onClick={async () => {
                            setTrackingRepoId(repoKey);
                            setTrackingError(null);
                            try {
                              const imported = await api.importRepository(repo.url);
                              await api.trackRepository(imported.id);
                              await load();
                            } catch (reason) {
                              setTrackingError(reason);
                            } finally {
                              setTrackingRepoId(null);
                            }
                          }}
                        >
                          {isTracking ? 'Добавление…' : 'Отслеживать'}
                        </Button>
                      ) : (
                        <span style={{ fontSize: '0.8rem', color: 'var(--sh-text-muted)' }}>
                          Анализ недоступен в текущей версии
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}

              {trackingError !== null && (
                <ErrorState
                  error={trackingError}
                  title="Не удалось добавить репозиторий"
                  onRetry={() => setTrackingError(null)}
                />
              )}

              {available.next_page_token && (
                <div style={{ marginTop: '0.5rem' }}>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={loadingMore}
                    onClick={() => void loadMore()}
                  >
                    {loadingMore ? 'Загрузка…' : 'Показать ещё'}
                  </Button>
                </div>
              )}
              {loadMoreError !== null && (
                <ErrorState
                  error={loadMoreError}
                  title="Не удалось загрузить следующую страницу SourceCraft"
                  onRetry={() => void loadMore()}
                />
              )}
            </div>
          )}
        </Card>
      )}

      {/* Achievements Section */}
      <div style={{ marginTop: 'var(--sh-space-6)' }}>
        <h2 style={{ marginBottom: 'var(--sh-space-3)' }}>
          Достижения ({unlockedCount} / {profile.achievements.length})
        </h2>
        {profile.achievements.length === 0 ? (
          <p style={{ color: 'var(--sh-text-muted)', fontSize: '0.9rem' }}>
            Достижения пока недоступны.
          </p>
        ) : (
          <div className="achievement-grid">
            {sortedAchievements.map((item) => (
              <article
                className={`achievement-card ${item.unlocked ? 'unlocked' : 'locked'}`}
                key={item.id}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
                  <span
                    aria-hidden="true"
                    style={{
                      fontSize: '1.1rem',
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      width: '24px',
                      height: '24px',
                    }}
                  >
                    {ACHIEVEMENT_ICONS[item.id] || (item.unlocked ? '◆' : '◇')}
                  </span>
                  <strong>{item.title}</strong>
                </div>
                <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.85rem' }}>{item.description}</p>
                <small style={{ color: 'var(--sh-text-muted)' }}>
                  {item.unlocked
                    ? `Открыто ${item.unlocked_at ? formatDateTime(item.unlocked_at) : ''}`
                    : 'Пока не открыто'}
                </small>
              </article>
            ))}
          </div>
        )}
      </div>
    </PageContainer>
  );
};
