import React from 'react';
import { Link } from 'react-router-dom';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { ScoreDisplay } from '../components/common/ScoreDisplay';
import { getButtonStyles } from '../components/common/Button';
import { mockCompletedAnalysis, mockHealthyRepo, mockNoDataRepo } from '../fixtures/sampleData';
import { CATEGORY_ORDER, CATEGORY_LABELS } from '../utils/analysis';
import { usePageTitle } from '../utils/usePageTitle';

/** Explicitly labelled static fallback. It is never used by live API error handling. */
export const DemoPage: React.FC = () => {
  usePageTitle('Демонстрационный режим');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-5)' }}>
      {/* Demo Banner */}
      <div
        role="status"
        style={{
          padding: 'var(--sh-space-4)',
          backgroundColor: 'var(--sh-health-warning-bg)',
          border: '1px solid var(--sh-health-warning-border)',
          borderRadius: 'var(--sh-radius-md)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span style={{ fontSize: '1.4rem' }} aria-hidden="true">
            🧪
          </span>
          <div>
            <strong style={{ color: 'var(--sh-health-warning)', display: 'block', fontSize: '0.95rem' }}>
              Демонстрационный офлайн-режим (Offline Demo)
            </strong>
            <span style={{ fontSize: '0.85rem', color: 'var(--sh-text-secondary)' }}>
              Данные демонстрационные, статически подготовлены и не связаны с текущим состоянием SourceCraft API.
            </span>
          </div>
        </div>

        <Link
          to="/"
          className="btn-link"
          style={getButtonStyles('primary', 'sm')}
        >
          Перейти к живому рейтингу →
        </Link>
      </div>

      {/* Guided Steps */}
      <Card title="Как устроен SourceHealth: 3 шага к надёжности">
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            gap: 'var(--sh-space-4)',
          }}
        >
          <div
            style={{
              padding: 'var(--sh-space-3) var(--sh-space-4)',
              backgroundColor: 'var(--sh-bg-base)',
              borderRadius: 'var(--sh-radius-sm)',
              border: '1px solid var(--sh-border-subtle)',
            }}
          >
            <div style={{ fontWeight: 700, color: 'var(--sh-brand)', marginBottom: '0.25rem' }}>
              1. Официальный Health
            </div>
            <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--sh-text-secondary)', lineHeight: 1.45 }}>
              Оценка от 0 до 100 формируется строго по подтверждённым фактам. Если по категории нет данных, она не становится нулём (принцип NO_DATA ≠ 0).
            </p>
          </div>

          <div
            style={{
              padding: 'var(--sh-space-3) var(--sh-space-4)',
              backgroundColor: 'var(--sh-bg-base)',
              borderRadius: 'var(--sh-radius-sm)',
              border: '1px solid var(--sh-border-subtle)',
            }}
          >
            <div style={{ fontWeight: 700, color: 'var(--sh-brand)', marginBottom: '0.25rem' }}>
              2. 6 категорий качества
            </div>
            <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--sh-text-secondary)', lineHeight: 1.45 }}>
              Анализируются документация, CI/CD, тесты, архитектура, безопасность AppSec и активность. Каждая оценка объяснима и ссылается на факты.
            </p>
          </div>

          <div
            style={{
              padding: 'var(--sh-space-3) var(--sh-space-4)',
              backgroundColor: 'var(--sh-bg-base)',
              borderRadius: 'var(--sh-radius-sm)',
              border: '1px solid var(--sh-border-subtle)',
            }}
          >
            <div style={{ fontWeight: 700, color: 'var(--sh-brand)', marginBottom: '0.25rem' }}>
              3. Рекомендации и экспорт
            </div>
            <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--sh-text-secondary)', lineHeight: 1.45 }}>
              Система формирует приоритизированные шаги по устранению проблем, предлагает Markdown-отчёт и SVG-бейджи для README.
            </p>
          </div>
        </div>
      </Card>

      {/* Example Repositories */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 'var(--sh-space-4)' }}>
        {[mockHealthyRepo, mockNoDataRepo].map((repo) => (
          <Card
            key={repo.id}
            title={`${repo.organization_slug}/${repo.repository_slug}`}
            subtitle={repo.canonical_url}
            headerAction={
              <Badge variant={repo.health_score !== null ? 'success' : 'neutral'}>
                {repo.health_score !== null ? 'Оценка рассчитана' : 'NO_DATA'}
              </Badge>
            }
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <ScoreDisplay score={repo.health_score} size="lg" />
            </div>
            <p style={{ color: 'var(--sh-text-muted)', fontSize: '0.85rem', margin: 0 }}>
              {repo.health_score === null
                ? 'NO_DATA: источник не предоставил достаточно данных. Это не ноль и не штраф.'
                : 'Санитизированный пример подтверждённой высокой оценки здоровья.'}
            </p>
          </Card>
        ))}
      </div>

      {/* Example Category Breakdown */}
      <Card title="Пример анализа по категориям" subtitle="Статические evidence и recommendations для демонстрации UI">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 'var(--sh-space-3)' }}>
          {CATEGORY_ORDER.map((category) => {
            const item = mockCompletedAnalysis.category_scores[category];
            return (
              <div
                key={category}
                style={{
                  padding: 'var(--sh-space-3)',
                  backgroundColor: 'var(--sh-bg-base)',
                  border: '1px solid var(--sh-border-subtle)',
                  borderRadius: 'var(--sh-radius-sm)',
                }}
              >
                <div style={{ color: 'var(--sh-text-muted)', fontSize: '0.82rem', marginBottom: '0.25rem' }}>
                  {CATEGORY_LABELS[category]}
                </div>
                <ScoreDisplay score={item?.score ?? null} size="md" />
              </div>
            );
          })}
        </div>
        <p style={{ marginBottom: 0, marginTop: 'var(--sh-space-4)', color: 'var(--sh-text-secondary)', fontSize: '0.85rem' }}>
          Резервный режим не подменяет live анализ и не отправляет запросы к API.
        </p>
      </Card>

      <div>
        <Link to="/" style={{ color: 'var(--sh-brand)', fontWeight: 500, fontSize: '0.9rem' }}>
          ← Вернуться к живому рейтингу
        </Link>
      </div>
    </div>
  );
};
