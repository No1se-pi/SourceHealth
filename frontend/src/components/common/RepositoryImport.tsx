import { useState, type FormEvent } from 'react';
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

  return <Card>
    <form onSubmit={submit} style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'end', gap: 'var(--sh-space-3)' }}>
      <label style={{ flex: '1 1 280px' }}>
        Публичный репозиторий SourceCraft
        <input type="url" required maxLength={512} value={url} disabled={pending}
          onChange={event => setUrl(event.target.value)} placeholder="https://sourcecraft.dev/org/repo"
          style={{ width: '100%', marginTop: 'var(--sh-space-2)' }} />
      </label>
      <Button type="submit" disabled={pending}>{pending ? 'Проверяем репозиторий…' : 'Добавить репозиторий'}</Button>
    </form>
    <p style={{ marginTop: 'var(--sh-space-2)' }}>Для добавления войдите через Яндекс ID. После проверки можно запустить анализ на странице репозитория.</p>
    {error != null && <ErrorState error={error} title="Не удалось добавить репозиторий" />}
  </Card>;
}
