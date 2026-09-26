import React from 'react';
import { Link } from 'react-router-dom';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { ScoreDisplay } from '../components/common/ScoreDisplay';
import { mockCompletedAnalysis, mockHealthyRepo, mockNoDataRepo } from '../fixtures/sampleData';
import { CATEGORY_ORDER, CATEGORY_LABELS } from '../utils/analysis';

/** Explicitly labelled static fallback. It is never used by live API error handling. */
export const DemoPage: React.FC = () => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-5)' }}>
    <Card
      title="DEMO DATASET / OFFLINE DEMO"
      subtitle="Санитизированный статический набор для защиты, когда SourceCraft недоступен. Это не live leaderboard."
      headerAction={<Badge variant="warning">Офлайн режим</Badge>}
    >
      <p style={{ margin: 0, color: 'var(--sh-text-secondary)' }}>
        Данные заранее подготовлены из безопасных fixtures: исходный код, PAT, OAuth и персональные данные отсутствуют.
      </p>
    </Card>

    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 'var(--sh-space-4)' }}>
      {[mockHealthyRepo, mockNoDataRepo].map((repo) => (
        <Card key={repo.id} title={`${repo.organization_slug}/${repo.repository_slug}`} subtitle={repo.canonical_url}>
          <ScoreDisplay score={repo.health_score} size="lg" />
          <p style={{ color: 'var(--sh-text-muted)', marginBottom: 0 }}>
            {repo.health_score === null ? 'NO_DATA: оценка ещё не рассчитана' : 'Санитизированный пример оценки'}
          </p>
        </Card>
      ))}
    </div>

    <Card title="Пример анализа" subtitle="Статические evidence и recommendations для демонстрации UI">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 'var(--sh-space-3)' }}>
        {CATEGORY_ORDER.map((category) => {
          const item = mockCompletedAnalysis.category_scores[category];
          return (
            <div key={category} style={{ padding: 'var(--sh-space-3)', border: '1px solid var(--sh-border-subtle)', borderRadius: 'var(--sh-radius-sm)' }}>
              <div style={{ color: 'var(--sh-text-muted)', fontSize: '0.82rem' }}>{CATEGORY_LABELS[category]}</div>
              <ScoreDisplay score={item?.score ?? null} size="md" />
            </div>
          );
        })}
      </div>
      <p style={{ marginBottom: 0, marginTop: 'var(--sh-space-4)', color: 'var(--sh-text-secondary)' }}>
        Резервный режим не подменяет live анализ и не отправляет запросы к API.
      </p>
    </Card>

    <Link to="/" style={{ color: 'var(--sh-brand)' }}>← Вернуться к live leaderboard</Link>
  </div>
);
