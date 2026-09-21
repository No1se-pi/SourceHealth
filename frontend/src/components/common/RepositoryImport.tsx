import React, { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import { Button } from './Button';
import { Card } from './Card';
import { ErrorState } from './ErrorState';

export function RepositoryImport() {
  const [url, setUrl] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>();
  const navigate = useNavigate();

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!url.trim()) return;
    setPending(true);
    setError(undefined);
    try {
      const repository = await api.importRepository(url.trim());
      navigate(`/repositories/${repository.id}`);
    } catch (failure) {
      setError(failure);
    } finally {
      setPending(false);
    }
  }

  return (
    <Card
      title="Добавить репозиторий для анализа"
      subtitle="Импорт открытого репозитория SourceCraft в систему мониторинга SourceHealth"
    >
      <form
        onSubmit={submit}
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--sh-space-3)',
        }}
      >
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--sh-space-3)', alignItems: 'center' }}>
          <div style={{ flex: '1 1 320px' }}>
            <input
              type="url"
              required
              maxLength={512}
              value={url}
              disabled={pending}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://sourcecraft.dev/org/repo или https://sourcecraft.tech/org/repo"
              aria-label="URL открытого репозитория SourceCraft"
              style={{
                width: '100%',
                padding: '0.55rem 0.85rem',
                fontSize: '0.9rem',
              }}
            />
          </div>
          <Button
            type="submit"
            variant="primary"
            disabled={pending || !url.trim()}
            loading={pending}
          >
            {pending ? 'Проверяем репозиторий…' : 'Импортировать'}
          </Button>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.82rem', color: 'var(--sh-text-muted)' }}>
          <span>ℹ</span>
          <span>
            Для добавления требуется активная сессия Яндекс ID. Доступен анализ только публичных репозиториев.
          </span>
        </div>
      </form>

      {error != null && (
        <div style={{ marginTop: 'var(--sh-space-4)' }}>
          <ErrorState error={error} title="Не удалось добавить репозиторий" />
        </div>
      )}
    </Card>
  );
}
