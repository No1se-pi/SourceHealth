import React, { useMemo, useState } from 'react';
import { Card } from '../components/common/Card';
import { PageContainer } from '../components/common/PageContainer';

export const DevelopersPage: React.FC = () => {
  const [repository, setRepository] = useState('organization/repository');
  const badge = useMemo(() => {
    const parts = repository.trim().split('/');
    if (parts.length !== 2 || parts.some((part) => !/^[A-Za-z0-9_-]{1,128}$/.test(part))) return '';
    return `![SourceHealth](https://sourcehealth.tech/api/v1/badges/${parts[0]}/${parts[1]}.svg)`;
  }, [repository]);

  return (
    <PageContainer><h1>SourceHealth for Developers</h1><p>Публичный REST API и Health badge для README.</p>
      <div className="growth-grid">
        <Card title="Public REST API">
          <p><code>health_score: null</code> означает, что официальный Health пока не рассчитан. Это не ноль.</p>
          <pre><code>{`curl https://sourcehealth.tech/api/v1/repositories?sort=health_score`}</code></pre>
          <ul className="growth-list">
            <li>GET /api/v1/repositories</li>
            <li>GET /api/v1/repositories/&#123;id&#125;</li>
            <li>GET /api/v1/repositories/&#123;id&#125;/analyses/latest</li>
            <li>GET /api/v1/analyses/&#123;id&#125;</li>
            <li>GET /api/v1/analyses/&#123;id&#125;/report.md</li>
          </ul>
          <a href="/api/openapi.json">OpenAPI JSON</a>
        </Card>
        <Card title="README badge">
          <label className="growth-field">Репозиторий organization/repository
            <input value={repository} onChange={(event) => setRepository(event.target.value)} />
          </label>
          <pre><code>{badge || 'Введите корректный путь репозитория'}</code></pre>
          {badge && <img alt="Пример SourceHealth badge" src={`/api/v1/badges/${repository}.svg`} />}
          <p>Badge показывает только официальный Health. Source Soul в badge не публикуется.</p>
        </Card>
      </div>
    </PageContainer>
  );
};
