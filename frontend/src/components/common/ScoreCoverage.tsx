import type { Analysis } from '../../api/client';
import { CATEGORY_LABELS } from '../../utils/analysis';

export function ScoreCoverage({ analysis }: { analysis?: Analysis }) {
  const coverage = analysis?.score_coverage;
  if (!coverage) return <p style={{ fontSize: '0.8rem', color: 'var(--sh-text-muted)' }}>Охват оценки не определён.</p>;
  return <div style={{ fontSize: '0.82rem', color: 'var(--sh-text-secondary)', marginTop: 'var(--sh-space-2)' }}>
    <strong>Охват оценки: {coverage.nominal_weight_percent}% · {coverage.scored_categories}/6 категорий</strong>
    {coverage.unscored_categories.length > 0 && <div>Без оценки: {coverage.unscored_categories.map(key => CATEGORY_LABELS[key]).join(', ')}.</div>}
    {coverage.partial_categories.length > 0 && <div>Частичные данные: {coverage.partial_categories.map(key => CATEGORY_LABELS[key]).join(', ')}.</div>}
    <div>Процент номинального веса, не гарантия полноты проверок.</div>
  </div>;
}
