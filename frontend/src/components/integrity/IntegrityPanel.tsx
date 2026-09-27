import React from 'react';
import type { components } from '../../api/generated';
import { Card } from '../common/Card';
import { Badge } from '../common/Badge';

type IntegrityResponse = components['schemas']['IntegrityResponse'];

function formatFactLabel(key: string): string {
  const labels: Record<string, string> = {
    commits_last_30_days: 'Коммитов за 30 дней',
    active_days_last_30_days: 'Активных дней',
    runs_observed: 'Наблюдаемых запусков CI',
    success_rate: 'Успешность CI',
    previous_score: 'Предыдущий Health',
    current_score: 'Текущий Health',
    delta: 'Изменение',
    previous_coverage: 'Прошлое покрытие',
    current_coverage: 'Текущее покрытие',
    coverage_changed: 'Сдвиг покрытия',
  };
  return labels[key] || key;
}

function formatFactValue(key: string, val: unknown): string {
  if (val === null || val === undefined) return '—';
  if (typeof val === 'boolean') return val ? 'Да' : 'Нет';
  if (typeof val === 'number') {
    if (key === 'success_rate') {
      return `${Math.round(val <= 1 ? val * 100 : val)}%`;
    }
    if (key.includes('coverage')) {
      return `${val}%`;
    }
    return String(val);
  }
  return String(val);
}

export const IntegrityPanel: React.FC<{ integrity: IntegrityResponse }> = ({ integrity }) => {
  const hasSignals = integrity.has_signals && integrity.signals.length > 0;

  return (
    <Card
      title="Проверка устойчивости рейтинга (Integrity)"
      subtitle="Аудит аномалий и сигналы устойчивости оценки. Сигналы не изменяют Health автоматически."
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-4)' }}>
        {/* Summary Indicator */}
        <div
          style={{
            padding: 'var(--sh-space-3) var(--sh-space-4)',
            borderRadius: 'var(--sh-radius-sm)',
            border: `1px solid ${hasSignals ? 'var(--sh-border-warning, #f59e0b)' : 'var(--sh-health-good, #10b981)'}`,
            backgroundColor: 'var(--sh-bg-base)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '0.5rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span
              style={{
                fontSize: '1.1rem',
                color: hasSignals ? '#f59e0b' : 'var(--sh-health-good, #10b981)',
                fontWeight: 700,
              }}
              aria-hidden="true"
            >
              {hasSignals ? '⚠' : '✓'}
            </span>
            <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>
              {!hasSignals
                ? 'Явных сигналов нет'
                : `${integrity.signal_count} ${
                    integrity.signal_count === 1 ? 'сигнал требует' : 'сигнала(ов) требуют'
                  } внимания`}
            </span>
          </div>

          {hasSignals && (
            <div style={{ display: 'flex', gap: '0.5rem', fontSize: '0.8rem' }}>
              {integrity.warning_count > 0 && (
                <Badge variant="warning">{integrity.warning_count} предупреждение</Badge>
              )}
              {integrity.info_count > 0 && (
                <Badge variant="neutral">{integrity.info_count} инфо</Badge>
              )}
            </div>
          )}
        </div>

        {/* Signals List */}
        {hasSignals && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-3)' }}>
            {integrity.signals.map((sig) => (
              <div
                key={sig.id}
                style={{
                  padding: 'var(--sh-space-3) var(--sh-space-4)',
                  backgroundColor: 'var(--sh-bg-surface)',
                  borderRadius: 'var(--sh-radius-sm)',
                  border: '1px solid var(--sh-border-subtle)',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginBottom: '0.35rem',
                  }}
                >
                  <span style={{ fontWeight: 600, fontSize: '0.92rem' }}>{sig.title}</span>
                  <Badge variant={sig.severity === 'warning' ? 'warning' : 'neutral'}>
                    {sig.severity === 'warning' ? 'Предупреждение' : 'Информация'}
                  </Badge>
                </div>
                <p
                  style={{
                    margin: '0 0 var(--sh-space-2) 0',
                    fontSize: '0.85rem',
                    color: 'var(--sh-text-muted)',
                  }}
                >
                  {sig.description}
                </p>

                {/* Formatted Key Safe Facts */}
                {sig.facts && Object.keys(sig.facts).length > 0 && (
                  <div
                    style={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: '0.5rem',
                      marginTop: '0.4rem',
                    }}
                  >
                    {Object.entries(sig.facts).map(([key, val]) => (
                      <span
                        key={key}
                        style={{
                          fontSize: '0.78rem',
                          backgroundColor: 'var(--sh-bg-base)',
                          padding: '0.2rem 0.5rem',
                          borderRadius: 'var(--sh-radius-sm)',
                          border: '1px solid var(--sh-border-subtle)',
                        }}
                      >
                        <span style={{ color: 'var(--sh-text-muted)' }}>{formatFactLabel(key)}:</span>{' '}
                        <strong style={{ fontFamily: 'var(--sh-font-mono)' }}>
                          {formatFactValue(key, val)}
                        </strong>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Factual Integrity Protection Explanation */}
        <div
          style={{
            padding: 'var(--sh-space-4)',
            backgroundColor: 'var(--sh-bg-base)',
            borderRadius: 'var(--sh-radius-sm)',
            border: '1px solid var(--sh-border-subtle)',
          }}
        >
          <div
            style={{
              fontSize: '0.85rem',
              fontWeight: 600,
              marginBottom: 'var(--sh-space-2)',
            }}
          >
            Как SourceHealth защищает рейтинг
          </div>
          <ul
            style={{
              margin: 0,
              paddingLeft: '1.25rem',
              fontSize: '0.82rem',
              color: 'var(--sh-text-muted)',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.35rem',
            }}
          >
            <li>
              <strong>Лайки и популярность не влияют на Health:</strong> оценка рассчитывается только по объективным инженерным свойствам кодовой базы.
            </li>
            <li>
              <strong>NO_DATA не равен нулю:</strong> категории без подтверждённых данных не штрафуют проект фиктивным нулём.
            </li>
            <li>
              <strong>Сигналы не меняют баллы автоматически:</strong> аномалии отображаются для прозрачности аудита, сохраняя детерминированность скоринга.
            </li>
            <li>
              <strong>Официальная безопасность:</strong> категория Security подтверждается исключительно официальным SourceCraft AppSec.
            </li>
          </ul>
        </div>
      </div>
    </Card>
  );
};
