import React from 'react';
import type { AnalyzerResult, Category } from '../../api/client';

const SEVERITIES = ['critical', 'high', 'medium', 'low'] as const;
const PENALTIES = { critical: 40, high: 20, medium: 5, low: 1 };

export function CategoryDetails({ category, checks, score }: {
  category: Category;
  checks?: Record<string, AnalyzerResult>;
  score?: number | null;
}) {
  const values = Object.values(checks ?? {});
  if (category === 'security') {
    const appsec = values.find((check) => check.source === 'sourcecraft_appsec' && check.availability === 'available'
      && check.metrics.complete === true);
    const counts = appsec?.metrics.open_by_severity as Record<string, unknown> | undefined;
    if (!counts || !SEVERITIES.every((name) => Number.isInteger(counts[name]) && Number(counts[name]) >= 0)) return null;
    const penalty = SEVERITIES.reduce((sum, name) => sum + Number(counts[name]) * PENALTIES[name], 0);
    const total = SEVERITIES.reduce((sum, name) => sum + Number(counts[name]), 0);
    return (
      <details className="score-explanation">
        <summary>Как рассчитана оценка?</summary>
        <strong>Official SourceCraft AppSec</strong>
        <div className="severity-grid">
          {SEVERITIES.map((name) => <React.Fragment key={name}><span>{name}</span><b>{Number(counts[name])}</b></React.Fragment>)}
        </div>
        <span>{total} открытых finding</span>
        <code>100 − {Number(counts.critical)}×40 − {Number(counts.high)}×20 − {Number(counts.medium)}×5 − {Number(counts.low)}×1 = {100 - penalty}; минимум 0; результат {score ?? 'NO_DATA'}</code>
      </details>
    );
  }
  if (category === 'code_health') {
    const sast = values.find((check) => check.source === 'sourcehealth_local');
    if (!sast?.findings?.length) return null;
    return (
      <details className="score-explanation">
        <summary>Безопасные находки local SAST ({sast.findings.length})</summary>
        <ul className="safe-findings">
          {sast.findings.map((finding, index) => (
            <li key={`${String(finding.rule_id ?? 'finding')}-${index}`}>
              <strong>{String(finding.rule_id ?? 'finding')}</strong> · {String(finding.severity ?? 'unknown')}
              {finding.path ? ` · ${String(finding.path)}${finding.line ? `:${String(finding.line)}` : ''}` : ''}
              {finding.message ? <span>{String(finding.message)}</span> : null}
              {finding.recommendation ? <span>{String(finding.recommendation)}</span> : null}
            </li>
          ))}
        </ul>
      </details>
    );
  }
  return null;
}
