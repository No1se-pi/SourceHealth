import React from 'react';
import type { components } from '../../api/generated';

type CompareResponse = components['schemas']['CompareResponse'];
const categories = ['documentation', 'cicd', 'security', 'activity', 'issues', 'code_health'] as const;
const labels: Record<(typeof categories)[number], string> = {
  documentation: 'Документация', cicd: 'CI/CD', security: 'Безопасность',
  activity: 'Активность', issues: 'Issues', code_health: 'Состояние кода',
};

export const CompareGrid: React.FC<{ comparison: CompareResponse }> = ({ comparison }) => (
  <div style={{ overflowX: 'auto' }}>
    {!comparison.comparable.policy_versions_match && <p role="status">Версии scoring policy различаются.</p>}
    <table>
      <thead><tr><th>Показатель</th>{comparison.repositories.map((repo) => (
        <th key={repo.repository_id}>{repo.organization_slug}/{repo.repository_slug}</th>
      ))}</tr></thead>
      <tbody>
        <tr><th>Health</th>{comparison.repositories.map((repo) => <td key={repo.repository_id}>{repo.health_score ?? 'Нет Health'}</td>)}</tr>
        <tr><th>Coverage</th>{comparison.repositories.map((repo) => <td key={repo.repository_id}>{repo.data_coverage_percent == null ? 'Нет данных' : `${repo.data_coverage_percent}%`}</td>)}</tr>
        {categories.map((category) => <tr key={category}><th>{labels[category]}</th>{comparison.repositories.map((repo) => {
          const value = repo.categories[category];
          return <td key={repo.repository_id}>{value?.score == null ? 'Нет данных' : value.score}<small>{value ? ` · ${value.availability}` : ''}</small></td>;
        })}</tr>)}
        <tr><th>Язык</th>{comparison.repositories.map((repo) => <td key={repo.repository_id}>{repo.language ?? 'Нет данных'}</td>)}</tr>
        <tr><th>Likes</th>{comparison.repositories.map((repo) => <td key={repo.repository_id}>{repo.likes ?? 'Нет данных'}</td>)}</tr>
        <tr><th>Последняя активность</th>{comparison.repositories.map((repo) => <td key={repo.repository_id}>{repo.last_activity_at ? new Date(repo.last_activity_at).toLocaleDateString('ru-RU') : 'Нет данных'}</td>)}</tr>
      </tbody>
    </table>
  </div>
);
