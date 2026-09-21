import React, { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import { Button } from './Button';
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
    <div className="sc-panel sc-import-panel">
      <div className="sc-import-header">
        <div className="sc-import-title-wrap">
          <svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor" className="sc-import-icon" aria-hidden="true">
            <path d="M7.75 2a.75.75 0 0 1 .75.75V7h4.25a.75.75 0 0 1 0 1.5H8.5v4.25a.75.75 0 0 1-1.5 0V8.5H2.75a.75.75 0 0 1 0-1.5H7V2.75A.75.75 0 0 1 7.75 2z" />
          </svg>
          <span className="sc-import-title">Импорт репозитория SourceCraft</span>
        </div>
        <span className="sc-import-hint">
          Поддерживаются публичные репозитории `https://sourcecraft.dev/org/repo`
        </span>
      </div>

      <form onSubmit={submit} className="sc-import-form">
        <div className="sc-import-input-row">
          <input
            type="url"
            required
            maxLength={512}
            value={url}
            disabled={pending}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://sourcecraft.dev/org/repo"
            aria-label="URL открытого репозитория SourceCraft"
            className="sc-import-input"
          />
          <Button
            type="submit"
            variant="primary"
            size="md"
            disabled={pending || !url.trim()}
            loading={pending}
          >
            {pending ? 'Проверка…' : 'Импортировать'}
          </Button>
        </div>
      </form>

      {error != null && (
        <div className="sc-import-error-wrap">
          <ErrorState error={error} title="Не удалось добавить репозиторий" />
        </div>
      )}
    </div>
  );
}
