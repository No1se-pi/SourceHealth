import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, type AnalysisPage } from '../../api/client';
import { STATUS_CONFIG } from '../../utils/analysis';
import { Badge } from './Badge';
import { Card } from './Card';
import { ErrorState } from './ErrorState';

export function AnalysisHistory({ repositoryId }: { repositoryId: string }) {
  const [page, setPage] = useState<AnalysisPage>();
  const [error, setError] = useState<unknown>();
  const [attempt, setAttempt] = useState(0);
  const generation = useRef(0);

  useEffect(() => {
    const request = ++generation.current;
    setPage(undefined);
    setError(undefined);
    api.analysisHistory(repositoryId).then(value => {
      if (request === generation.current) setPage(value);
    }).catch(failure => {
      if (request === generation.current) setError(failure);
    });
    return () => { generation.current++; };
  }, [repositoryId, attempt]);

  return <Card title="История анализов">
    {error != null ? <ErrorState error={error} title="Не удалось загрузить историю" onRetry={() => setAttempt(value => value + 1)} />
      : !page ? <p role="status">Загружаем историю…</p>
      : page.items.length === 0 ? <p>Анализов пока нет.</p>
      : <>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', textAlign: 'left' }}>
            <thead><tr><th>Запуск</th><th>Статус</th><th>Health</th><th>Профиль</th></tr></thead>
            <tbody>{page.items.map(run => <tr key={run.id}>
              <td><Link to={`/analyses/${run.id}`}>{new Date(run.queued_at).toLocaleString('ru-RU')}</Link></td>
              <td><Badge variant={STATUS_CONFIG[run.status].variant}>{run.status === 'failed' ? 'Ошибка анализа' : STATUS_CONFIG[run.status].label}</Badge></td>
              <td>{['completed', 'partial'].includes(run.status) ? run.health_score ?? '—' : '—'}</td>
              <td>{run.profile}</td>
            </tr>)}</tbody>
          </table>
        </div>
        {page.has_more && <p>Показаны последние 10 запусков.</p>}
      </>}
  </Card>;
}
