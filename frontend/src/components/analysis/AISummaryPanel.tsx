import React, { useRef, useState } from 'react';
import { api, type AISummaryMode, type AISummaryResponse } from '../../api/client';
import { ErrorState } from '../common/ErrorState';

const MODES: Array<{ id: AISummaryMode; label: string; description: string; modelName: string; image: string }> = [
  { id: 'flash', label: 'Мозг', description: 'Быстрый разбор', modelName: 'Alice AI LLM Flash', image: '/brand/ai/brain.png' },
  { id: 'lite', label: 'Крутой мозг', description: 'Сбалансированный разбор', modelName: 'YandexGPT 5 Lite', image: '/brand/ai/brain-plus.png' },
  { id: 'pro', label: 'Мегамозг', description: 'Глубокий разбор', modelName: 'YandexGPT 5.1 Pro', image: '/brand/ai/brain-mega.png' },
];

export const AISummaryPanel: React.FC<{ analysisId: string }> = ({ analysisId }) => {
  const [mode, setMode] = useState<AISummaryMode>('flash');
  const [result, setResult] = useState<AISummaryResponse>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>();
  const refs = useRef<Array<HTMLButtonElement | null>>([]);

  const generate = async () => {
    setLoading(true); setError(undefined);
    try { setResult(await api.aiSummary(analysisId, mode)); }
    catch (err) { setError(err); }
    finally { setLoading(false); }
  };
  const onKeyDown = (event: React.KeyboardEvent, index: number) => {
    if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    event.preventDefault();
    const next = (index + (event.key === 'ArrowRight' ? 1 : -1) + MODES.length) % MODES.length;
    setMode(MODES[next].id); refs.current[next]?.focus();
  };

  return <section className="ai-summary" aria-labelledby="ai-summary-title">
    <div className="ai-summary__heading">
      <div><h2 id="ai-summary-title">AI-разбор результата</h2><p>Отчёт строится только по сохранённым фактам SourceHealth и не меняет Health Score.</p></div>
      <span>Yandex AI Studio</span>
    </div>
    <div className="ai-mode-selector" role="radiogroup" aria-label="Глубина AI-разбора">
      {MODES.map((item, index) => <button key={item.id} type="button" role="radio"
        aria-checked={mode === item.id} tabIndex={mode === item.id ? 0 : -1}
        ref={(node) => { refs.current[index] = node; }}
        className={mode === item.id ? 'ai-mode ai-mode--active' : 'ai-mode'}
        onClick={() => setMode(item.id)} onKeyDown={(event) => onKeyDown(event, index)}>
        <img src={item.image} alt="" aria-hidden="true" />
        <span><strong>{item.label}</strong><small>{item.description}</small><small>{item.modelName}</small></span>
      </button>)}
    </div>
    <button className="ai-generate" type="button" disabled={loading} onClick={() => void generate()}>
      {loading ? 'Формируем разбор…' : 'Сформировать AI-разбор'}
    </button>
    {Boolean(error) && <ErrorState error={error} title="Не удалось сформировать AI-разбор" onRetry={() => void generate()} />}
    {result && <div className="ai-result" aria-live="polite">
      <div className="ai-result__meta">{result.model_name} · {result.cached ? 'из кеша' : 'новый'} · факты проверены</div>
      <p className="ai-result__lead">{result.summary.executive_summary}</p>
      {([['Сильные стороны', result.summary.strengths], ['Риски', result.summary.risks],
        ['Что делать дальше', result.summary.actions], ['Ограничения', result.summary.limitations]] as const)
        .filter(([, items]) => items.length > 0).map(([title, items]) => <div key={title}>
          <h3>{title}</h3><ul>{items.map((item, i) => <li key={`${title}-${i}`}>{item.text}</li>)}</ul>
        </div>)}
    </div>}
  </section>;
};
