import React from 'react';
import { Link } from 'react-router-dom';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';

export const NotFoundPage: React.FC = () => {
  return (
    <div style={{ maxWidth: '520px', margin: 'var(--sh-space-8) auto' }}>
      <Card title="404 — Страница не найдена">
        <p style={{ margin: '0 0 var(--sh-space-5) 0', color: 'var(--sh-text-secondary)' }}>
          Запрашиваемая страница не существует или была перемещена.
        </p>
        <div>
          <Link to="/">
            <Button variant="primary">На главную страницу</Button>
          </Link>
        </div>
      </Card>
    </div>
  );
};
