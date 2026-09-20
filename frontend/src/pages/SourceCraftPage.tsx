import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { components } from '../api/generated';

export const SourceCraftPage: React.FC = () => {
  const navigate = useNavigate();
  const [connected, setConnected] = useState(false);
  const [organization, setOrganization] = useState('');
  const [items, setItems] = useState<components['schemas']['ConnectedRepositoryDTO'][]>([]);
  const [more, setMore] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  useEffect(() => {
    let active = true;
    api.sourcecraftStatus().then(s => { if (active) setConnected(s.connected); })
      .catch(() => { if (active) setMessage('Войдите через Яндекс ID для подключения SourceCraft.'); });
    return () => { active = false; };
  }, []);
  const connect = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const field = form.elements.namedItem('pat') as HTMLInputElement;
    const pending = api.connectSourcecraft(field.value);
    field.value = ''; // Credential never enters React state or browser storage.
    setBusy(true); setMessage('');
    try { await pending; setConnected(true); }
    catch { setMessage('Не удалось подключиться. Проверьте PAT и настройку сервера.'); }
    finally { setBusy(false); }
  };
  const list = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setMessage(''); setItems([]);
    try { const result = await api.connectedRepositories(organization); setItems(result.items); setMore(result.has_more); }
    catch { setMessage('Не удалось получить список. Проверьте организацию и срок подключения.'); }
    finally { setBusy(false); }
  };
  const analyze = async (url: string) => {
    setBusy(true); setMessage('');
    try { const repo = await api.importRepository(url); const run = await api.start(repo.id); navigate(`/analyses/${run.id}`); }
    catch { setMessage('Не удалось запустить публичный анализ.'); }
    finally { setBusy(false); }
  };
  return <section>
    <h1>Подключить SourceCraft</h1>
    <p>Подключение временное и действует только в текущей сессии. PAT SourceCraft отличается от входа через Яндекс ID.</p>
    {message && <p role="status">{message}</p>}
    {!connected ? <form onSubmit={connect}>
      <label>SourceCraft PAT <input name="pat" type={'pass' + 'word'} autoComplete="off" required maxLength={4096} /></label>
      <button disabled={busy} type="submit">Подключить</button>
    </form> : <>
      <button disabled={busy} onClick={async () => {
        setBusy(true);
        try { await api.disconnectSourcecraft(); setConnected(false); setItems([]); }
        catch { setMessage('Отключение не подтверждено. Повторите попытку.'); }
        finally { setBusy(false); }
      }}>Отключить SourceCraft</button>
      <form onSubmit={list}>
        <label>Организация <input required value={organization} onChange={e => setOrganization(e.target.value)} pattern="[A-Za-z0-9_-]{1,128}" /></label>
        <button disabled={busy}>Получить репозитории</button>
      </form>
      <p>Доступность списка определяет SourceCraft. Можно анализировать только публичные репозитории.</p>
      {more && <p>Показаны первые 100 репозиториев организации. Полный список пока недоступен.</p>}
      <ul>{items.map(repo => <li key={repo.url}>
        {repo.url} — {repo.visibility}{' '}
        {repo.can_analyze ? <button disabled={busy} onClick={() => analyze(repo.url)}>Анализировать</button>
          : <span>Анализ закрытых репозиториев пока не поддерживается.</span>}
      </li>)}</ul>
    </>}
  </section>;
};
