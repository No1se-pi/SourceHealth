import React from 'react';
import type { AnalyzerResult, Category } from '../../api/client';
import { hasDetectedCiConfiguration, localSastStatus } from './categoryDetailsModel';

const SEVERITIES = ['critical', 'high', 'medium', 'low'] as const;
const PENALTIES = { critical: 40, high: 20, medium: 5, low: 1 };

export function CategoryDetails({ category, checks, score }: {
  category: Category;
  checks?: Record<string, AnalyzerResult>;
  score?: number | null;
}) {
  const values = Object.values(checks ?? {});
  if (category === 'cicd' && hasDetectedCiConfiguration(checks, score)) {
    return (
      <div className="analysis-source-note analysis-source-note--ci" role="note">
        <strong>Конфигурация CI обнаружена</strong>
        <span>SourceCraft не предоставил достаточно данных о запусках, поэтому численная оценка CI/CD сейчас не рассчитана.</span>
        <div className="analysis-source-note__rows">
          <span>✓ CI configuration — detected</span><span>— Run history — unavailable</span>
        </div>
      </div>
    );
  }
  if (category === 'security') {
    const appsec = values.find((check) => check.source === 'sourcecraft_appsec' && check.availability === 'available'
      && check.metrics.complete === true);
    const counts = appsec?.metrics.open_by_severity as Record<string, unknown> | undefined;
    if (!counts || !SEVERITIES.every((name) => Number.isInteger(counts[name]) && Number(counts[name]) >= 0)) {
      return (
        <details className="score-explanation">
          <summary>Почему нет оценки безопасности?</summary>
          <div style={{ marginTop: '0.4rem', color: 'var(--sh-text-secondary)', fontSize: '0.84rem', lineHeight: 1.45 }}>
            <p style={{ margin: '0 0 0.3rem 0' }}>Official SourceCraft AppSec не предоставил пригодных данных для этой оценки.</p>
            <p style={{ margin: 0, color: 'var(--sh-text-muted)' }}>Локальная статическая проверка относится к «Состоянию кода» и не заменяет Security.</p>
          </div>
        </details>
      );
    }
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
    const status = localSastStatus(checks);
    if (!status) return null;
    return (
      <div className="local-sast-status">
        <strong>{status.label}</strong>
        <p>
          Локальная статическая проверка влияет только на Code Health и не заменяет официальный AppSec.
        </p>
        {sast?.findings?.length ? <details className="score-explanation">
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
        </details> : null}
      </div>
    );
  }
  return null;
}
