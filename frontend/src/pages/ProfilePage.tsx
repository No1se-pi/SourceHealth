import React, { useEffect, useState } from 'react';
import { api, type ConnectedRepositories, type Profile } from '../api/client';
import { Card } from '../components/common/Card';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { PageContainer } from '../components/common/PageContainer';

const refreshes = ['adaptive', '1h', '6h', '24h', '7d', 'off'];

export const ProfilePage: React.FC = () => {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [available, setAvailable] = useState<ConnectedRepositories | null>(null);
  const load = () => api.profile().then(setProfile).catch((reason) => {
    setError(reason);
  });
  useEffect(() => { void load(); }, []);
  useEffect(() => {
    if (profile?.sourcecraft.connected) void api.mySourcecraftRepositories().then(setAvailable).catch(() => setAvailable(null));
  }, [profile?.sourcecraft.connected]);
  if (error) return <PageContainer><h1>Профиль</h1><ErrorState error={error} /></PageContainer>;
  if (!profile) return <PageContainer><h1>Профиль</h1><LoadingState /></PageContainer>;
  return (
    <PageContainer><h1>Профиль</h1><p>Ваши проекты, расписание обновлений и достижения.</p>
      <div className="growth-grid">
        <Card title="SourceCraft">
          <p>{profile.sourcecraft.connected ? '● Подключено' : '○ Не подключено'}</p>
          <p>Срок хранения: {Math.round(profile.sourcecraft.retention_seconds / 3600 * 10) / 10} ч.; осталось {profile.sourcecraft.expires_in} сек.</p>
          <p className="growth-muted">PAT хранится на сервере в зашифрованном виде. При сроке более 30 минут он может использоваться для разрешённого автоанализа после выхода из веб-сессии.</p>
          <a href="/sourcecraft">Управлять подключением</a>
        </Card>
        <Card title="Отслеживаемые репозитории">
          {profile.repositories.length === 0 ? <EmptyState description="Пока нет отслеживаемых репозиториев." /> : profile.repositories.map((repo) => (
            <div className="growth-repository" key={repo.repository_id}>
              <strong>{repo.organization_slug}/{repo.repository_slug}</strong>
              <span>Health: {repo.health_score ?? 'пока не рассчитан'}</span>
              {repo.health_score == null && repo.score_preview?.numeric && <span>👻 Source Soul ≈{repo.score_preview.score}</span>}
              <label>Обновление
                <select value={repo.refresh_preference} onChange={async (event) => {
                  await api.updateTrackedRepository(repo.repository_id, event.target.value, repo.use_pat_for_scheduled_analysis); load();
                }}>{refreshes.map((item) => <option key={item}>{item}</option>)}</select>
              </label>
              <label><input type="checkbox" checked={repo.use_pat_for_scheduled_analysis} onChange={async (event) => {
                await api.updateTrackedRepository(repo.repository_id, repo.refresh_preference, event.target.checked); load();
              }} /> Использовать сохранённый PAT для AppSec при автоанализе</label>
            </div>
          ))}
        </Card>
      </div>
      {profile.sourcecraft.connected && <Card title="Мои репозитории SourceCraft" subtitle="Репозитории, доступные вашему SourceCraft PAT">
        {!available ? <LoadingState size="sm" /> : available.items.length === 0 ? <EmptyState description="Доступные репозитории не найдены." /> :
          available.items.map((repo) => <div className="growth-repository" key={repo.id ?? repo.url}>
            <strong>{repo.organization_slug}/{repo.repository_slug}</strong><span>{repo.visibility}</span>
            {repo.can_analyze ? <button type="button" onClick={async () => {
              const imported = await api.importRepository(repo.url); await api.trackRepository(imported.id); await load();
            }}>Отслеживать</button> : <span>Анализ недоступен в текущей версии</span>}
          </div>)}
      </Card>}
      <h2>Достижения</h2>
      <div className="achievement-grid">{profile.achievements.map((item) => (
        <article className={`achievement-card ${item.unlocked ? 'unlocked' : 'locked'}`} key={item.id}>
          <span aria-hidden="true">{item.unlocked ? '◆' : '◇'}</span><strong>{item.title}</strong>
          <p>{item.description}</p><small>{item.unlocked ? `Открыто ${item.unlocked_at ? new Date(item.unlocked_at).toLocaleDateString('ru-RU') : ''}` : 'Пока не открыто'}</small>
        </article>
      ))}</div>
    </PageContainer>
  );
};
