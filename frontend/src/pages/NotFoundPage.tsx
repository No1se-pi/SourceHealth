import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Card } from '../components/common/Card';
import { getButtonStyles } from '../components/common/Button';
import { usePageTitle } from '../utils/usePageTitle';

export const NotFoundPage: React.FC = () => {
  usePageTitle('404 — Страница не найдена');
  const location = useLocation();

  // Check if current path resembles an org/repo pattern
  const pathname = location.pathname.replace(/^\/+|\/+$/g, '');
  const segments = pathname.split('/');
  const isLikelyRepo =
    segments.length === 2 &&
    segments.every((s) => /^[A-Za-z0-9_.-]{1,128}$/.test(s)) &&
    !['api', 'analyses', 'repositories', 'compare', 'demo', 'developers', 'profile'].includes(segments[0]);

  return (
    <div style={{ maxWidth: '600px', margin: 'var(--sh-space-8) auto', padding: '0 1rem' }}>
      <Card title="404 — Страница не найдена">
        <p style={{ margin: '0 0 var(--sh-space-4) 0', color: 'var(--sh-text-secondary)', lineHeight: 1.5 }}>
          Запрашиваемая страница не существует, была удалена или перемещена по новому адресу.
        </p>

        {isLikelyRepo && (
          <div
            style={{
              padding: 'var(--sh-space-3) var(--sh-space-4)',
              marginBottom: 'var(--sh-space-4)',
              backgroundColor: 'var(--sh-bg-base)',
              borderRadius: 'var(--sh-radius-sm)',
              border: '1px solid var(--sh-border-subtle)',
              fontSize: '0.85rem',
              color: 'var(--sh-text-primary)',
            }}
          >
            <div>
              Адрес похож на репозиторий: <code>{pathname}</code>.
            </div>
            <div style={{ marginTop: '0.35rem', color: 'var(--sh-text-muted)' }}>
              SourceHealth не выполняет автоматический импорт без явного действия пользователя. Вы можете найти проект через каталог или импортировать его на главной странице.
            </div>
          </div>
        )}

        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <Link to="/" className="btn-link" style={getButtonStyles('primary', 'md')}>
            Каталог проектов
          </Link>
          <Link to="/profile" className="btn-link" style={getButtonStyles('secondary', 'md')}>
            Личный кабинет
          </Link>
          <Link to="/developers" className="btn-link" style={getButtonStyles('outline', 'md')}>
            Для разработчиков
          </Link>
        </div>
      </Card>
    </div>
  );
};
