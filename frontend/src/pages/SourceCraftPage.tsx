import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { components } from '../api/generated';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Badge } from '../components/common/Badge';

export const SourceCraftPage: React.FC = () => {
  const navigate = useNavigate();
  const [connected, setConnected] = useState(false);
  const [organization, setOrganization] = useState('');
  const [items, setItems] = useState<components['schemas']['ConnectedRepositoryDTO'][]>([]);
  const [more, setMore] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [isError, setIsError] = useState(false);

  useEffect(() => {
    let active = true;
    api
      .sourcecraftStatus()
      .then((s) => {
        if (active) setConnected(s.connected);
      })
      .catch(() => {
        if (active) {
          setMessage('Для подключения SourceCraft сначала выполните вход через Яндекс ID.');
          setIsError(false);
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
    const pending = api.connectSourcecraft(patValue);
    field.value = ''; // Credential never enters React state or browser storage.
    setBusy(true);
    setMessage('');
    setIsError(false);
    try {
      await pending;
      setConnected(true);
      setMessage('SourceCraft успешно подключён к текущей сессии.');
      setIsError(false);
    } catch {
      setMessage('Не удалось подключиться. Проверьте правильность токена PAT.');
      setIsError(true);
    } finally {
      setBusy(false);
    }
  };

  const handleDisconnect = async () => {
    setBusy(true);
    setMessage('');
    try {
      await api.disconnectSourcecraft();
      setConnected(false);
      setItems([]);
      setMessage('Подключение к SourceCraft отключено.');
      setIsError(false);
    } catch {
      setMessage('Отключение не подтверждено сервером. Повторите попытку.');
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
    } catch {
      setMessage('Не удалось получить список репозиториев. Проверьте имя организации и срок действия PAT.');
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
      const run = await api.start(repo.id);
      navigate(`/analyses/${run.id}`);
    } catch {
      setMessage('Не удалось запустить публичный анализ репозитория.');
      setIsError(true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-6)' }}>
      {/* Page Header */}
      <div>
        <h1 style={{ marginBottom: 'var(--sh-space-2)' }}>Интеграция с SourceCraft</h1>
        <p style={{ maxWidth: '760px', margin: 0 }}>
          Подключение персонального токена доступа (PAT) для прямого взаимодействия с репозиториями
          организаций в экосистеме SourceCraft.
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
          <strong style={{ color: 'var(--sh-text-primary)' }}>Безопасность сессии:</strong>
          <span style={{ color: 'var(--sh-text-secondary)' }}>
            Персональный токен SourceCraft хранится исключительно в оперативной памяти сервера на время
            текущей сессии и никогда не сохраняется в локальном хранилище браузера (localStorage/sessionStorage).
            Вход через Яндекс ID обеспечивает идентификацию пользователя, а PAT — доступ к репозиториям платформы.
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
              <input
                id="pat-input"
                name="pat"
                type="password"
                autoComplete="off"
                required
                maxLength={4096}
                disabled={busy}
                placeholder="sc_pat_..."
                style={{
                  width: '100%',
                  fontFamily: 'var(--sh-font-mono)',
                  fontSize: '0.9rem',
                }}
              />
            </div>
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
                {busy ? 'Отключение…' : 'Отключить SourceCraft'}
              </Button>
            }
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Badge variant="success">✓ Подключено к SourceCraft</Badge>
              <span style={{ fontSize: '0.85rem', color: 'var(--sh-text-muted)' }}>
                Токен активен в рамках текущей сессии
              </span>
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
                  <input
                    type="text"
                    required
                    value={organization}
                    onChange={(e) => setOrganization(e.target.value)}
                    pattern="[A-Za-z0-9_-]{1,128}"
                    disabled={busy}
                    placeholder="Имя организации (например: lct-hackaton-2026)"
                    aria-label="Имя организации"
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
                      {items.map((repo) => (
                        <tr key={repo.url}>
                          <td>
                            <a
                              href={repo.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{ fontWeight: 600, color: 'var(--sh-text-primary)' }}
                            >
                              {repo.url.replace(/^https?:\/\/[^/]+\//, '')}
                            </a>
                          </td>
                          <td>
                            <Badge variant={repo.visibility === 'public' ? 'success' : 'neutral'}>
                              {repo.visibility === 'public' ? 'Публичный' : repo.visibility}
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
                                Закрытый репозиторий
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
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
