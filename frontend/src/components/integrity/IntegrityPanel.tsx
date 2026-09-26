import React from 'react';
import type { components } from '../../api/generated';

type IntegrityResponse = components['schemas']['IntegrityResponse'];

export const IntegrityPanel: React.FC<{ integrity: IntegrityResponse }> = ({ integrity }) => (
  <section aria-labelledby="integrity-title">
    <h2 id="integrity-title">Проверка устойчивости рейтинга</h2>
    <p>Сигналы не изменяют Health автоматически. Они помогают заметить ситуации, где результат стоит интерпретировать осторожнее.</p>
    {!integrity.has_signals ? <p>✓ Явных сигналов нет</p> : (
      <div>
        <p>{integrity.signal_count} сигнал(а)</p>
        {integrity.signals.map((signal) => (
          <article key={signal.id}>
            <strong>{signal.severity === 'warning' ? '⚠' : 'ⓘ'} {signal.title}</strong>
            <p>{signal.description}</p>
          </article>
        ))}
      </div>
    )}
  </section>
);
