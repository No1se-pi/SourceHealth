import React, { useRef, useState } from 'react';
import { api, type AISummaryDetail, type AISummaryMode, type AISummaryResponse,
  type GroundedStatement } from '../../api/client';
import { ErrorState } from '../common/ErrorState';

const MODES: Array<{ id: AISummaryMode; label: string; modelName: string; image: string }> = [
  { id: 'flash', label: 'Мозг', modelName: 'Alice AI LLM Flash', image: '/brand/ai/brain.png' },
  { id: 'lite', label: 'Крутой мозг', modelName: 'YandexGPT 5 Lite', image: '/brand/ai/brain-plus.png' },
  { id: 'pro', label: 'Мегамозг', modelName: 'YandexGPT 5.1 Pro', image: '/brand/ai/brain-mega.png' },
];
const DETAILS: Array<{ id: AISummaryDetail; label: string; budget: string; description: string }> = [
  { id: 'brief', label: 'Краткий', budget: 'до ~10 тыс. знаков', description: 'Основные выводы и действия.' },
  { id: 'detailed', label: 'Подробный', budget: 'до ~20 тыс. знаков', description: 'Разбор категорий и рекомендации.' },
  { id: 'expert', label: 'Экспертный', budget: 'до ~50 тыс. знаков', description: 'Полный технический отчёт с планом улучшений.' },
];

const Evidence: React.FC<{ refs: string[] }> = ({ refs }) => refs.length > 0
  ? <div className="ai-evidence">Evidence: {refs.join(', ')}</div> : null;

const StatementList: React.FC<{ items: GroundedStatement[] }> = ({ items }) => (
  <ul>{items.map((item, index) => <li key={`${item.text}-${index}`}>
    <span>{item.text}</span><Evidence refs={item.evidence_refs} />
  </li>)}</ul>
);

export const AISummaryPanel: React.FC<{ analysisId: string }> = ({ analysisId }) => {
  const [mode, setMode] = useState<AISummaryMode>('flash');
  const [detail, setDetail] = useState<AISummaryDetail>('brief');
  const [result, setResult] = useState<AISummaryResponse>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>();
  const refs = useRef<Array<HTMLButtonElement | null>>([]);
  const selectedIndex = MODES.findIndex((item) => item.id === mode);

  const generate = async () => {
    setLoading(true); setError(undefined); setResult(undefined);
    try { setResult(await api.aiReport(analysisId, mode, detail)); }
    catch (err) { setError(err); }
    finally { setLoading(false); }
  };
  const onKeyDown = (event: React.KeyboardEvent, index: number) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? MODES.length - 1
      : Math.max(0, Math.min(MODES.length - 1, index + (event.key === 'ArrowRight' ? 1 : -1)));
    setMode(MODES[next].id); refs.current[next]?.focus();
  };
  const roadmap = result?.summary.roadmap;
  const actionTitle = (id: string) => result?.summary.actions.find((item) => item.id === id)?.title ?? id;
  const categoryFinding = (id: string) => result?.summary.category_findings.find((item) => item.id === id);

  return <section className="ai-summary" aria-labelledby="ai-summary-title">
    <div className="ai-summary__heading">
      <div><h2 id="ai-summary-title">AI-разбор результата</h2><p>Отчёт строится только по сохранённым фактам SourceHealth и не меняет Health Score.</p></div>
      <span>Yandex AI Studio</span>
    </div>
    <h3 className="ai-selector-title">Модель</h3>
    <div className="ai-power" style={{ '--ai-stop': selectedIndex } as React.CSSProperties}>
      <div className="ai-power__track" aria-hidden="true"><span className="ai-power__knob" /></div>
      <div className="ai-power__stops" role="radiogroup" aria-label="Модель AI-разбора">
        {MODES.map((item, index) => <button key={item.id} type="button" role="radio"
          aria-checked={mode === item.id} tabIndex={mode === item.id ? 0 : -1}
          ref={(node) => { refs.current[index] = node; }}
          className={mode === item.id ? 'ai-power__stop ai-power__stop--active' : 'ai-power__stop'}
          onClick={() => setMode(item.id)} onKeyDown={(event) => onKeyDown(event, index)}>
          <img src={item.image} alt="" aria-hidden="true" />
          <span className="ai-power__dot" aria-hidden="true" />
          <strong>{item.label}</strong><small>{item.modelName}</small>
        </button>)}
      </div>
    </div>
    <fieldset className="ai-depth"><legend>Глубина отчёта</legend>
      {DETAILS.map((item) => <label key={item.id} className={detail === item.id ? 'ai-depth__item ai-depth__item--active' : 'ai-depth__item'}>
        <input type="radio" name="ai-detail" value={item.id} checked={detail === item.id}
          onChange={() => setDetail(item.id)} />
        <span><strong>{item.label}</strong><small>{item.budget}</small><span>{item.description}</span></span>
      </label>)}
    </fieldset>
    <button className="ai-generate" type="button" disabled={loading} onClick={() => void generate()}>
      {loading ? 'Формируем разбор…' : 'Сформировать AI-разбор'}
    </button>
    {Boolean(error) && <ErrorState error={error} title="Не удалось сформировать AI-разбор" onRetry={() => void generate()} />}
    {result && <article className="ai-result" aria-live="polite">
      <div className="ai-result__meta">{result.model_name} · {DETAILS.find((item) => item.id === result.detail)?.label}
        {' · '}{result.cached ? 'из кеша' : 'новый'} · факты проверены</div>
      <section><h3>Резюме</h3><p className="ai-result__lead">{result.summary.executive_summary}</p></section>
      {result.summary.category_analysis.length > 0 && <section><h3>Разбор категорий</h3>
        <div className="ai-categories">{result.summary.category_analysis.map((category) => <article key={category.category} className="ai-category">
          <header><strong>{category.category}</strong><span>{category.score ?? 'Нет данных'} · {category.availability}</span></header>
          <p>{category.assessment}</p>
          {category.positive_finding_ids.length > 0 && <><h4>Положительные наблюдения</h4><ul>{category.positive_finding_ids.map((id) => { const item = categoryFinding(id); return item && <li key={id}>{item.text}<Evidence refs={item.evidence_refs} /></li>; })}</ul></>}
          {category.problem_finding_ids.length > 0 && <><h4>Проблемы</h4><ul>{category.problem_finding_ids.map((id) => { const item = categoryFinding(id); return item && <li key={id}>{item.text}<Evidence refs={item.evidence_refs} /></li>; })}</ul></>}
          <Evidence refs={category.evidence_refs} />
        </article>)}</div>
      </section>}
      {result.summary.strengths.length > 0 && <section><h3>Сильные стороны</h3><StatementList items={result.summary.strengths} /></section>}
      {result.summary.risks.length > 0 && <section><h3>Риски</h3><StatementList items={result.summary.risks} /></section>}
      {result.summary.actions.length > 0 && <section><h3>Рекомендации</h3><div className="ai-actions">
        {result.summary.actions.map((item) => <article key={item.id} className="ai-action">
          <header><span>P{item.priority}</span><h4>{item.title}</h4></header>
          <p><strong>Проблема и причина:</strong> {item.why}</p><p><strong>Что сделать:</strong> {item.action}</p>
          {item.implementation_steps.length > 0 && <ol>{item.implementation_steps.map((step) => <li key={step}>{step}</li>)}</ol>}
          <p><strong>Ожидаемый результат:</strong> {item.expected_result}</p>
          <Evidence refs={[...item.recommendation_ids, ...item.evidence_refs]} />
        </article>)}
      </div></section>}
      {roadmap && (roadmap.immediate.length + roadmap.short_term.length + roadmap.later.length > 0) && <section><h3>План действий</h3>
        <div className="ai-roadmap">{([['Сейчас', roadmap.immediate], ['В ближайшее время', roadmap.short_term], ['Позже', roadmap.later]] as const)
          .filter(([, items]) => items.length > 0).map(([title, items]) => <div key={title}><h4>{title}</h4><ul>{items.map((item) => <li key={item}>{actionTitle(item)}</li>)}</ul></div>)}</div>
      </section>}
      {result.summary.limitations.length > 0 && <section><h3>Ограничения данных</h3><StatementList items={result.summary.limitations} /></section>}
    </article>}
  </section>;
};
