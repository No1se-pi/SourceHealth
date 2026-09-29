import React from 'react';
import { Link } from 'react-router-dom';
import type { components } from '../../api/generated';

type CompareResponse = components['schemas']['CompareResponse'];
type ComparedRepository = components['schemas']['ComparedRepository'];
const categories = ['documentation', 'cicd', 'security', 'activity', 'issues', 'code_health'] as const;
const labels: Record<(typeof categories)[number], string> = {
  documentation: 'Документация', cicd: 'CI/CD', security: 'Безопасность',
  activity: 'Активность', issues: 'Issues', code_health: 'Состояние кода',
};

const formatDate = (value: string | null) => value
  ? new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(value))
  : 'Нет данных';

const RepositoryCard: React.FC<{ repo: ComparedRepository }> = ({ repo }) => (
  <article className="compare-repository-card">
    <div className="compare-repository-card__top">
      <Link className="compare-repository-card__name" to={`/repositories/${repo.repository_id}`}
        title={`${repo.organization_slug}/${repo.repository_slug}`}>
        <span>{repo.organization_slug}</span><strong>{repo.repository_slug}</strong>
      </Link>
      {repo.language && <span className="compare-chip">{repo.language}</span>}
    </div>
    <div className="compare-health"><span>Health Score</span>
      <strong className={repo.health_score == null ? 'compare-health__no-data' : ''}>
        {repo.health_score == null ? 'NO_DATA' : repo.health_score}
      </strong>
    </div>
    <div className="compare-coverage">
      <div><span>Coverage</span><strong>{repo.data_coverage_percent == null ? 'NO_DATA' : `${repo.data_coverage_percent}%`}</strong></div>
      <div className="compare-coverage__track" aria-hidden="true">
        {repo.data_coverage_percent != null && <span style={{ width: `${Math.max(0, Math.min(100, repo.data_coverage_percent))}%` }} />}
      </div>
    </div>
    <dl className="compare-meta">
      <div><dt>Активность</dt><dd>{formatDate(repo.last_activity_at)}</dd></div>
      <div><dt>Likes</dt><dd>{repo.likes ?? '—'}</dd></div>
    </dl>
    {repo.latest_analysis_id && <Link className="compare-analysis-link" to={`/analyses/${repo.latest_analysis_id}`}>Открыть анализ →</Link>}
  </article>
);

export const CompareGrid: React.FC<{ comparison: CompareResponse }> = ({ comparison }) => (
  <section className="compare-shell" style={{ '--compare-count': comparison.repositories.length } as React.CSSProperties}>
    {!comparison.comparable.policy_versions_match && <div className="compare-policy-warning" role="status">
      Версии scoring policy различаются — сравнивайте значения с учётом методики каждого анализа.
    </div>}
    <div className="compare-scroll" tabIndex={0} aria-label="Сравнение репозиториев">
      <div className="compare-grid compare-grid--cards">
        {comparison.repositories.map((repo) => <RepositoryCard key={repo.repository_id} repo={repo} />)}
      </div>
      <div className="compare-categories">
        <div className="compare-section-heading"><span>ДЕТАЛИ ОЦЕНКИ</span><h2>Категории</h2></div>
        {categories.map((category) => <section className="compare-category" key={category}>
          <h3>{labels[category]}</h3>
          <div className="compare-grid">
            {comparison.repositories.map((repo) => {
              const value = repo.categories[category];
              const numeric = value?.score != null;
              return <div className={`compare-score${numeric ? '' : ' compare-score--no-data'}`} key={repo.repository_id}>
                <div className="compare-score__label" title={`${repo.organization_slug}/${repo.repository_slug}`}>{repo.repository_slug}</div>
                <div className="compare-score__value">
                  {numeric ? <><div className="compare-score__track"><span style={{ width: `${Math.max(0, Math.min(100, value.score!))}%` }} /></div><strong>{value.score}</strong></>
                    : <strong>NO_DATA</strong>}
                </div>
                <span className={`compare-availability compare-availability--${value?.availability ?? 'no_data'}`}>
                  {value?.availability ?? 'no_data'}
                </span>
              </div>;
            })}
          </div>
        </section>)}
      </div>
    </div>
  </section>
);
