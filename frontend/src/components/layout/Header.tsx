import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { api, type User } from '../../api/client';

export const Header: React.FC = () => {
  const [user, setUser] = useState<User | null>(null);
  const location = useLocation();

  useEffect(() => {
    let active = true;
    api
      .me()
      .then((data) => {
        if (active) setUser(data);
      })
      .catch(() => {
        // Unauthenticated session is expected for public visitors
        if (active) setUser(null);
      });
    return () => {
      active = false;
    };
  }, [location.pathname]);

  return (
    <header className="app-header">
      <div className="app-header-content">
        <div style={{ display: 'flex', alignItems: 'center', gap: '2rem' }}>
          <Link to="/" className="brand-logo-link">
            <span style={{ color: 'var(--sh-brand)', fontSize: '1.3rem' }}>✦</span>
            <span>SourceHealth</span>
            <span className="brand-logo-badge">beta</span>
          </Link>
          <nav className="app-nav">
            <Link
              to="/"
              className="nav-link"
              style={{
                color: location.pathname === '/' ? 'var(--sh-text-primary)' : undefined,
                fontWeight: location.pathname === '/' ? 600 : 500,
              }}
            >
              Лидерборд
            </Link>
          </nav>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {user ? (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                fontSize: '0.85rem',
                color: 'var(--sh-text-secondary)',
                backgroundColor: 'var(--sh-bg-surface-elevated)',
                padding: '0.3rem 0.75rem',
                borderRadius: 'var(--sh-radius-full)',
                border: '1px solid var(--sh-border-default)',
              }}
              title={`ID пользователя: ${user.id}`}
            >
              <span
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  backgroundColor: 'var(--sh-health-good)',
                  display: 'inline-block',
                }}
                aria-hidden="true"
              />
              <span>Сессия активна</span>
            </div>
          ) : (
            <a
              href="/api/v1/auth/yandex/login"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
                fontSize: '0.88rem',
                fontWeight: 600,
                color: 'var(--sh-text-primary)',
                backgroundColor: 'var(--sh-bg-surface-elevated)',
                border: '1px solid var(--sh-border-default)',
                padding: '0.45rem 0.9rem',
                borderRadius: 'var(--sh-radius-sm)',
                textDecoration: 'none',
                transition: 'border-color var(--sh-transition), background var(--sh-transition)',
              }}
            >
              <span style={{ color: '#fc3f1d', fontWeight: 700 }}>Я</span>
              <span>Войти через Я ID</span>
            </a>
          )}
        </div>
      </div>
    </header>
  );
};
