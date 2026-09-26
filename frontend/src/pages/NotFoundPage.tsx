import React from 'react';
import { Link } from 'react-router-dom';
import { Card } from '../components/common/Card';
import { getButtonStyles } from '../components/common/Button';
import { usePageTitle } from '../utils/usePageTitle';

export const NotFoundPage: React.FC = () => {
  usePageTitle('404 — Страница не найдена');

  return (
    <div style={{ maxWidth: '560px', margin: 'var(--sh-space-8) auto', padding: '0 1rem' }}>
      <Card title="404 — Страница не найдена">
        <p style={{ margin: '0 0 var(--sh-space-5) 0', color: 'var(--sh-text-secondary)', lineHeight: 1.5 }}>
          Запрашиваемая страница не существует или была перемещена по новому адресу. Вы можете вернуться к рейтингу или изучить возможности платформы.
        </p>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <Link to="/" className="btn-link" style={getButtonStyles('primary', 'md')}>
            Открыть рейтинг
          </Link>
          <Link to="/demo" className="btn-link" style={getButtonStyles('secondary', 'md')}>
            Открыть демо
          </Link>
          <Link to="/developers" className="btn-link" style={getButtonStyles('outline', 'md')}>
            Разработчикам
          </Link>
        </div>
      </Card>
    </div>
  );
};
