import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Link, Route, Routes, useNavigate, useParams } from 'react-router-dom';
import { api, ApiError, type Analysis, type RepositoryDetails, type RepositoryPage } from './api/client';
import './style.css';

function Failure({ error }: { error: unknown }) {
  const message = error instanceof ApiError ? `${error.code} · запрос ${error.requestId}` : 'Сервис недоступен. Повторите позже.';
  return <p role="alert">{message}</p>;
}

function Leaderboard() {
  const [page, setPage] = useState<RepositoryPage>();
  const [error, setError] = useState<unknown>();
  const [offset, setOffset] = useState(0);
  const [sort, setSort] = useState('health_score');
  useEffect(() => {
    let active = true; setPage(undefined); setError(undefined);
    api.repositories(offset, sort).then(value => { if (active) setPage(value); }).catch(e => { if (active) setError(e); });
    return () => { active = false; };
  }, [offset, sort]);
  return <section><h1>Здоровье открытых репозиториев</h1>
    <p>Оценки основаны на проверяемых фактах. «Нет оценки» означает, что она ещё не рассчитана.</p>
    <label>Сортировка <select value={sort} onChange={e => { setSort(e.target.value); setOffset(0); }}>
      <option value="health_score">По здоровью проекта</option><option value="likes">По лайкам</option>
      <option value="last_activity">По последней активности</option></select></label>
    {error ? <Failure error={error} /> : !page ? <p role="status">Загрузка…</p> : <>
      {page.items.length === 0 ? <p>Репозитории пока не добавлены.</p> : <ul>{page.items.map(repo => <li key={repo.id}>
        <Link to={`/repositories/${repo.id}`}>{repo.organization_slug}/{repo.repository_slug}</Link>
        <span>{repo.health_score === null ? 'Нет оценки' : `${repo.health_score}/100`}</span>
      </li>)}</ul>}
      <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - page.limit))}>Назад</button>
      <button disabled={!page.has_more} onClick={() => setOffset(offset + page.limit)}>Далее</button>
    </>}
  </section>;
}

function RepositoryView() {
  const { id = '' } = useParams(); const navigate = useNavigate();
  const [repo, setRepo] = useState<RepositoryDetails>(); const [error, setError] = useState<unknown>();
  const [starting, setStarting] = useState(false);
  useEffect(() => {
    let active = true; setRepo(undefined); setError(undefined);
    api.repository(id).then(r => { if (active) setRepo(r); }).catch(e => { if (active) setError(e); });
    return () => { active = false; };
  }, [id]);
  async function start() {
    setStarting(true); setError(undefined);
    try { const run = await api.start(id); navigate(`/analyses/${run.id}`); }
    catch (e) { setError(e); } finally { setStarting(false); }
  }
  return <section>{error ? <Failure error={error} /> : null}{!repo ? (!error && <p>Загрузка репозитория…</p>) : <>
    <h1>{repo.organization_slug}/{repo.repository_slug}</h1><a href={repo.canonical_url}>Открыть в SourceCraft</a>
    <p>Repo Health Score: {repo.health_score ?? 'Нет оценки'}</p>
    {repo.latest_analysis_id && <p><Link to={`/analyses/${repo.latest_analysis_id}`}>Последний завершённый анализ</Link></p>}
    <button onClick={start} disabled={starting}>{starting ? 'Запускаем…' : 'Запустить анализ'}</button>
    <p>Для запуска войдите через Я ID.</p>
  </>}</section>;
}

const statusLabels: Record<string, string> = {
  queued: 'В очереди', collecting: 'Сбор данных', analyzing: 'Анализ', scoring: 'Подготовка оценки',
  completed: 'Завершён', partial: 'Завершён с неполными данными', failed: 'Не удалось завершить',
};

function AnalysisView() {
  const { id = '' } = useParams(); const [run, setRun] = useState<Analysis>(); const [error, setError] = useState<unknown>();
  useEffect(() => {
    let active = true; let timer: ReturnType<typeof setTimeout>;
    setRun(undefined); setError(undefined);
    async function poll() {
      try {
        const value = await api.analysis(id); if (!active) return; setRun(value); setError(undefined);
        if (!['completed', 'partial', 'failed'].includes(value.status)) timer = setTimeout(poll, 2000);
      } catch (e) { if (active) setError(e); }
    }
    void poll(); return () => { active = false; clearTimeout(timer); };
  }, [id]);
  return <section><h1>Анализ репозитория</h1>{error ? <Failure error={error} /> : !run ? <p>Загрузка…</p> : <>
    <p role="status">{statusLabels[run.status]}</p><p>Repo Health Score: {run.health_score ?? 'Нет оценки'}</p>
    <ul>{Object.entries(run.category_scores).map(([key, value]) => <li key={key}>
      <strong>{key}</strong><span>{value.score ?? 'Нет оценки'} · {value.availability}</span><p>{value.explanation}</p>
    </li>)}</ul>
    {run.error_code && <p role="alert">{run.error_code}</p>}
    {['completed', 'partial'].includes(run.status) && <a href={`/api/v1/analyses/${id}/report.md`}>Скачать Markdown</a>}
  </>}</section>;
}

function AuthCallback() {
  const [message, setMessage] = useState('Проверяем вход…');
  useEffect(() => { api.me().then(() => setMessage('Вход выполнен. Можно выбрать открытый репозиторий.'))
    .catch(() => setMessage('Сессия недоступна. Повторите вход.')); }, []);
  return <section><h1>Вход</h1><p role="status">{message}</p><Link to="/">К репозиториям</Link></section>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><BrowserRouter>
  <header><Link to="/">SourceHealth</Link><a href="/api/v1/auth/yandex/login">Войти через Я ID</a></header>
  <main><Routes><Route path="/" element={<Leaderboard />} /><Route path="/repositories/:id" element={<RepositoryView />} />
    <Route path="/analyses/:id" element={<AnalysisView />} /><Route path="/auth/callback" element={<AuthCallback />} />
    <Route path="*" element={<p>Страница не найдена. <Link to="/">На главную</Link></p>} /></Routes></main>
</BrowserRouter></React.StrictMode>);
