import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import type { components } from '../api/generated';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Badge } from '../components/common/Badge';
import { getSafeExternalUrl } from '../utils/analysis';
import { usePageTitle } from '../utils/usePageTitle';
import { formatTtl } from '../utils/formatters';

export const SourceCraftPage: React.FC = () => {
  usePageTitle('Подключение SourceCraft');

  const navigate = useNavigate();
  const [connected, setConnected] = useState(false);
  const [expiresIn, setExpiresIn] = useState<number | null>(null);
  const [retention, setRetention] = useState(1800);
  const [organization, setOrganization] = useState('');
  const [items, setItems] = useState<components['schemas']['ConnectedRepositoryDTO'][]>([]);
  const [more, setMore] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [isError, setIsError] = useState(false);
  const [showPat, setShowPat] = useState(false);
  const [patLength, setPatLength] = useState(0);

  useEffect(() => {
    let active = true;
    api
      .sourcecraftStatus()
      .then((s) => {
        if (active) {
          setConnected(s.connected);
          if (typeof s.expires_in === 'number') {
            setExpiresIn(s.expires_in);
          }
          setRetention(s.retention_seconds);
        }
      })
      .catch((err: unknown) => {
        if (active) {
          if (err instanceof ApiError && err.status === 401) {
            setMessage('Для подключения SourceCraft сначала выполните вход через Яндекс ID.');
            setIsError(false);
          } else if (err instanceof ApiError) {
            const reqId = err.requestId ? ` (ID: ${err.requestId})` : '';
            setMessage(`Ошибка сервиса SourceHealth [${err.code}]. Повторите попытку позже${reqId}.`);
            setIsError(true);
          } else {
            setMessage('Сетевая ошибка при проверке статуса SourceCraft. Попробуйте обновить страницу.');
            setIsError(true);
          }
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const connect = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const field = form.elements.namedItem('pat') as HTMLInputElement;
    const patValue = field.value;
    const pending = api.connectSourcecraft(patValue, retention);
    field.value = ''; // Credential never enters React state or browser storage.
    setPatLength(0);
    setBusy(true);
    setMessage('');
    setIsError(false);
    try {
      const conn = await pending;
      setConnected(conn.connected);
      if (typeof conn.expires_in === 'number') {
        setExpiresIn(conn.expires_in);
      }
      setMessage('SourceCraft успешно подключён к текущей сессии.');
      setIsError(false);
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 401) {
        setMessage('Сессия истекла. Пожалуйста, выполните вход через Яндекс ID.');
      } else if (err instanceof ApiError) {
        const reqId = err.requestId ? ` (ID: ${err.requestId})` : '';
        setMessage(`Не удалось подключиться: ${err.code}${reqId}. Проверьте правильность токена PAT.`);
      } else {
        setMessage('Не удалось подключиться. Проверьте правильность токена PAT.');
      }
      setIsError(true);
    } finally {
      setBusy(false);
    }
  };

  const handleDisconnect = async () => {
    if (
      !window.confirm(
        'Удалить сохранённый PAT? Фоновый автоанализ AppSec перестанет его использовать.'
      )
    ) {
      return;
    }
    setBusy(true);
    setMessage('');
    try {
      await api.disconnectSourcecraft();
      setConnected(false);
      setExpiresIn(null);
      setItems([]);
      setMessage('Подключение к SourceCraft отключено.');
      setIsError(false);
    } catch (err: unknown) {
      const reqId = err instanceof ApiError && err.requestId ? ` (ID: ${err.requestId})` : '';
      setMessage(`Отключение не подтверждено сервером${reqId}. Повторите попытку.`);
      setIsError(true);
    } finally {
      setBusy(false);
    }
  };

  const list = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!organization.trim()) return;
    setBusy(true);
    setMessage('');
    setIsError(false);
    setItems([]);
    try {
      const result = await api.connectedRepositories(organization.trim());
      setItems(result.items);
      setMore(result.has_more);
      if (result.items.length === 0) {
        setMessage('В организации не найдено доступных репозиториев.');
      }
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 401) {
        setMessage('Сессия истекла или токен SourceCraft недействителен. Повторите подключение.');
      } else if (err instanceof ApiError) {
        const reqId = err.requestId ? ` (ID: ${err.requestId})` : '';
        setMessage(`Не удалось получить список репозиториев: ${err.code}${reqId}. Проверьте имя организации.`);
      } else {
        setMessage('Не удалось получить список репозиториев. Проверьте имя организации и соединение.');
      }
      setIsError(true);
    } finally {
      setBusy(false);
    }
  };

  const analyze = async (url: string) => {
    setBusy(true);
    setMessage('');
    setIsError(false);
    try {
      const repo = await api.importRepository(url);
      await api.trackRepository(repo.id);
      const run = await api.start(repo.id);
      navigate(`/analyses/${run.id}`);
    } catch (err: unknown) {
      const reqId = err instanceof ApiError && err.requestId ? ` (ID: ${err.requestId})` : '';
      setMessage(`Не удалось запустить публичный анализ репозитория${reqId}.`);
      setIsError(true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-4)' }}>
      {/* Page Header */}
      <div>
        <h1 style={{ margin: '0 0 var(--sh-space-1) 0' }}>Интеграция с SourceCraft</h1>
        <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--sh-text-secondary)' }}>
          Подключение персонального токена доступа (PAT) для прямого взаимодействия с репозиториями SourceCraft.
        </p>
      </div>

      {/* Security Architecture Notice */}
      <div
        style={{
          padding: 'var(--sh-space-4)',
          backgroundColor: 'var(--sh-bg-surface-elevated)',
          border: '1px solid var(--sh-border-default)',
          borderRadius: 'var(--sh-radius-md)',
          display: 'flex',
          gap: 'var(--sh-space-3)',
          alignItems: 'flex-start',
          fontSize: '0.85rem',
        }}
      >
        <span style={{ fontSize: '1.2rem', lineHeight: 1 }} aria-hidden="true">
          🛡️
        </span>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          <strong style={{ color: 'var(--sh-text-primary)' }}>Безопасность подключения:</strong>
          <span style={{ color: 'var(--sh-text-secondary)' }}>
            PAT не сохраняется в браузере. На сервере он хранится только в зашифрованном виде до выбранного срока
            и может использоваться для разрешённого автоанализа.
          </span>
        </div>
      </div>

      {/* Status / Alert Banner */}
      {message && (
        <div
          role="status"
          style={{
            padding: 'var(--sh-space-3) var(--sh-space-4)',
            backgroundColor: isError ? 'var(--sh-health-danger-bg)' : 'var(--sh-health-good-bg)',
            border: `1px solid ${isError ? 'var(--sh-health-danger-border)' : 'var(--sh-health-good-border)'}`,
            borderRadius: 'var(--sh-radius-sm)',
            color: isError ? 'var(--sh-health-danger)' : 'var(--sh-health-good)',
            fontSize: '0.88rem',
            fontWeight: 500,
          }}
        >
          {message}
        </div>
      )}

      {/* Connection Section */}
      {!connected ? (
        <Card
          title="Подключение через SourceCraft PAT"
          subtitle="Создайте Personal Access Token в настройках профиля SourceCraft с правами чтения репозиториев"
        >
          <form
            onSubmit={connect}
            style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-4)', maxWidth: '600px' }}
          >
            <div>
              <label
                htmlFor="pat-input"
                style={{
                  display: 'block',
                  fontSize: '0.88rem',
                  fontWeight: 500,
                  marginBottom: 'var(--sh-space-2)',
                  color: 'var(--sh-text-primary)',
                }}
              >
                SourceCraft Personal Access Token (PAT)
              </label>
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <input
                  id="pat-input"
                  name="pat"
                  type={showPat ? 'text' : 'password'}
                  autoComplete="off"
                  spellCheck={false}
                  required
                  maxLength={4096}
                  disabled={busy}
                  placeholder="sc_pat_..."
                  onChange={(e) => setPatLength(e.target.value.length)}
                  aria-describedby="pat-help"
                  style={{
                    flex: 1,
                    fontFamily: 'var(--sh-font-mono)',
                    fontSize: '0.9rem',
                  }}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setShowPat(!showPat)}
                  style={{ padding: '0.45rem 0.75rem', fontSize: '0.82rem', whiteSpace: 'nowrap' }}
                >
                  {showPat ? 'Скрыть' : 'Показать'}
                </Button>
              </div>
              {patLength > 0 && (
                <div style={{ marginTop: '0.35rem', fontSize: '0.8rem', color: 'var(--sh-health-good)' }}>
                  ✓ PAT введён ({patLength} симв.)
                </div>
              )}
              <div id="pat-help" style={{ marginTop: '0.5rem', fontSize: '0.82rem', color: 'var(--sh-text-muted)' }}>
                PAT используется только сервером и хранится в зашифрованном виде ограниченное время.
              </div>
            </div>
            <label htmlFor="pat-retention">
              Срок хранения для автоанализа
              <select
                id="pat-retention"
                value={retention}
                onChange={(event) => setRetention(Number(event.target.value))}
                style={{ marginTop: '0.35rem', display: 'block' }}
              >
                <option value={1800}>30 минут — для ручной проверки</option>
                <option value={21600}>6 часов — короткая сессия</option>
                <option value={86400}>24 часа — на день</option>
                <option value={604800}>7 дней — автоанализ</option>
              </select>
              <span className="growth-muted" style={{ display: 'block', marginTop: '0.35rem' }}>
                При сроке более 30 минут PAT останется зашифрованным после выхода из веб-сессии до истечения срока. Удалить его можно здесь в любой момент.
              </span>
            </label>
            <div>
              <Button type="submit" variant="primary" disabled={busy} loading={busy}>
                {busy ? 'Подключение…' : 'Подключить SourceCraft'}
              </Button>
            </div>
          </form>
        </Card>
      ) : (
        <>
          {/* Active Connection Card */}
          <Card
            title="Статус подключения"
            headerAction={
              <Button
                variant="outline"
                size="sm"
                disabled={busy}
                onClick={handleDisconnect}
                style={{ color: 'var(--sh-health-danger)', borderColor: 'var(--sh-health-danger-border)' }}
              >
                {busy ? 'Удаление…' : 'Удалить PAT сейчас'}
              </Button>
            }
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
              <Badge variant="success">● SourceCraft подключён</Badge>
              <span style={{ fontSize: '0.85rem', color: 'var(--sh-text-muted)' }}>
                {expiresIn !== null && expiresIn > 0
                  ? `Осталось: ${formatTtl(expiresIn)}`
                  : 'Токен активен в рамках текущей сессии'}
              </span>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
                Хранить PAT:
                <select
                  value={retention}
                  disabled={busy}
                  onChange={async (event) => {
                    const value = Number(event.target.value);
                    setBusy(true);
                    try {
                      const updated = await api.updateSourcecraftRetention(value);
                      setRetention(updated.retention_seconds);
                      setExpiresIn(updated.expires_in);
                    } finally {
                      setBusy(false);
                    }
                  }}
                  style={{ fontSize: '0.82rem' }}
                >
                  <option value={1800}>30 минут — для ручной проверки</option>
                  <option value={21600}>6 часов — короткая сессия</option>
                  <option value={86400}>24 часа — на день</option>
                  <option value={604800}>7 дней — автоанализ</option>
                </select>
              </label>
            </div>
          </Card>

          {/* Repositories Organization Browser */}
          <Card
            title="Репозитории организации"
            subtitle="Укажите имя организации в SourceCraft для просмотра доступных репозиториев"
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-4)' }}>
              <form
                onSubmit={list}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--sh-space-3)',
                  flexWrap: 'wrap',
                  maxWidth: '600px',
                }}
              >
                <div style={{ flex: '1 1 240px' }}>
                  <label htmlFor="sourcecraft-organization" style={{ display: 'block', fontSize: '0.85rem', fontWeight: 500 }}>
                    Slug организации SourceCraft
                  </label>
                  <input
                    id="sourcecraft-organization"
                    type="text"
                    required
                    value={organization}
                    onChange={(e) => setOrganization(e.target.value)}
                    pattern="[A-Za-z0-9_-]{1,128}"
                    disabled={busy}
                    placeholder="lct-hackaton-2026"
                    style={{ width: '100%' }}
                  />
                </div>
                <Button type="submit" variant="secondary" disabled={busy || !organization.trim()} loading={busy}>
                  {busy ? 'Загрузка…' : 'Получить репозитории'}
                </Button>
              </form>

              <div style={{ fontSize: '0.82rem', color: 'var(--sh-text-muted)' }}>
                Доступность списка определяется правами токена в SourceCraft. Анализ доступен для публичных проектов.
              </div>
              {items.length > 0 && <div style={{ fontSize: '0.85rem' }}>{items.length} репозиториев найдено</div>}

              {more && (
                <div
                  style={{
                    padding: 'var(--sh-space-2) var(--sh-space-3)',
                    backgroundColor: 'var(--sh-bg-surface-elevated)',
                    borderRadius: 'var(--sh-radius-sm)',
                    fontSize: '0.82rem',
                    color: 'var(--sh-text-muted)',
                  }}
                >
                  Показаны первые 100 репозиториев организации.
                </div>
              )}

              {/* Repositories List */}
              {items.length > 0 && (
                <div className="table-responsive-wrapper">
                  <table className="leaderboard-table" style={{ borderRadius: 'var(--sh-radius-sm)', overflow: 'hidden' }}>
                    <thead>
                      <tr>
                        <th scope="col">Репозиторий</th>
                        <th scope="col">Доступность</th>
                        <th scope="col" style={{ textAlign: 'right' }}>Действие</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((repo) => {
                        const safeRepoUrl = getSafeExternalUrl(repo.url);
                        const displaySlug = repo.url.replace(/^https?:\/\/[^/]+\//, '');
                        return (
                          <tr key={repo.url}>
                            <td>
                              {safeRepoUrl ? (
                                <a
                                  href={safeRepoUrl}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  style={{ fontWeight: 600, color: 'var(--sh-text-primary)' }}
                                >
                                  {displaySlug}
                                </a>
                              ) : (
                                <span style={{ fontWeight: 600, color: 'var(--sh-text-primary)' }}>
                                  {displaySlug}
                                </span>
                              )}
                            </td>
                            <td>
                              <Badge variant={repo.visibility === 'public' ? 'success' : 'warning'}>
                                {repo.visibility === 'public' ? 'Публичный' : 'Приватный (анализ недоступен)'}
                              </Badge>
                            </td>
                            <td style={{ textAlign: 'right' }}>
                              {repo.can_analyze ? (
                                <Button
                                  size="sm"
                                  variant="primary"
                                  disabled={busy}
                                  onClick={() => analyze(repo.url)}
                                >
                                  Анализировать
                                </Button>
                              ) : (
                                <span style={{ fontSize: '0.8rem', color: 'var(--sh-text-muted)' }}>
                                  Анализ недоступен
                                </span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </Card>
        </>
      )}
    </div>
  );
};
