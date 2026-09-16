import React, { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { api, type User } from '../../api/client';
import { Button } from '../common/Button';

export const Header: React.FC = () => {
  const [user, setUser] = useState<User | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const location = useLocation();
  const navigate = useNavigate();

  // Run session check once on mount. Unauthenticated visitors get 401, which is handled gracefully.
  useEffect(() => {
    let active = true;
    api
      .me()
      .then((data) => {
        if (active) setUser(data);
      })
      .catch(() => {
        // Unauthenticated visitor is the default public state
        if (active) setUser(null);
      });
    return () => {
      active = false;
    };
  }, []);

  const handleLogout = async () => {
    if (loggingOut) return;
    setLoggingOut(true);
    setLogoutError(null);
    try {
      await api.logout();
      setUser(null);
      navigate('/');
    } catch {
      // Do NOT clear user if server logout failed!
      setLogoutError('Не удалось выйти. Повторите попытку.');
    } finally {
      setLoggingOut(false);
    }
  };

  return (
    <header className="app-header">
      <div className="app-header-content">
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
          <Link to="/" className="brand-logo-link" aria-label="SourceHealth главная">
            <span style={{ color: 'var(--sh-brand)', fontSize: '1.3rem' }} aria-hidden="true">
              ✦
            </span>
            <span>SourceHealth</span>
            <span className="brand-logo-badge">beta</span>
          </Link>
          <nav className="app-nav" aria-label="Основная навигация">
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

        <div className="app-header-auth">
          {logoutError && (
            <span
              role="alert"
              style={{
                fontSize: '0.78rem',
                color: 'var(--sh-health-danger)',
                fontWeight: 500,
              }}
            >
              {logoutError}
            </span>
          )}

          {user ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
              <div
                className="auth-status-badge"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  fontSize: '0.82rem',
                  color: 'var(--sh-text-secondary)',
                  backgroundColor: 'var(--sh-bg-surface-elevated)',
                  padding: '0.25rem 0.65rem',
                  borderRadius: 'var(--sh-radius-full)',
                  border: '1px solid var(--sh-border-default)',
                  whiteSpace: 'nowrap',
                }}
                title={`ID пользователя: ${user.id}`}
              >
                <span
                  style={{
                    width: '7px',
                    height: '7px',
                    borderRadius: '50%',
                    backgroundColor: 'var(--sh-health-good)',
                    display: 'inline-block',
                  }}
                  aria-hidden="true"
                />
                <span>Авторизован</span>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleLogout}
                disabled={loggingOut}
                aria-label="Выйти из аккаунта"
              >
                {loggingOut ? 'Выход…' : 'Выйти'}
              </Button>
            </div>
          ) : (
            <a
              href="/api/v1/auth/yandex/login"
              className="auth-login-btn"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.45rem',
                fontSize: '0.85rem',
                fontWeight: 600,
                color: 'var(--sh-text-primary)',
                backgroundColor: 'var(--sh-bg-surface-elevated)',
                border: '1px solid var(--sh-border-default)',
                padding: '0.4rem 0.8rem',
                borderRadius: 'var(--sh-radius-sm)',
                textDecoration: 'none',
                whiteSpace: 'nowrap',
                transition: 'border-color var(--sh-transition), background var(--sh-transition)',
              }}
              aria-label="Войти через Яндекс ID"
            >
              <span style={{ color: '#fc3f1d', fontWeight: 700 }} aria-hidden="true">
                Я
              </span>
              <span>Войти</span>
            </a>
          )}
        </div>
      </div>
    </header>
  );
};
