import React, { useEffect, useState, useRef } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { api, type User } from '../../api/client';
import { Button } from '../common/Button';

export const Header: React.FC = () => {
  const [user, setUser] = useState<User | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const location = useLocation();
  const navigate = useNavigate();

  // Initialize theme from DOM attribute set by anti-FOUC script
  useEffect(() => {
    const currentTheme = document.documentElement.getAttribute('data-theme') as 'light' | 'dark';
    if (currentTheme === 'dark' || currentTheme === 'light') {
      setTheme(currentTheme);
    } else {
      const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      const initial = prefersDark ? 'dark' : 'light';
      setTheme(initial);
      document.documentElement.setAttribute('data-theme', initial);
    }
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(nextTheme);
    document.documentElement.setAttribute('data-theme', nextTheme);
    try {
      localStorage.setItem('sourcehealth_theme', nextTheme);
    } catch {
      // Ignore storage restrictions
    }
  };

  // Close mobile menu on route change unless mobileNav param is present
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (params.get('mobileNav') === '1') {
      setMobileMenuOpen(true);
    } else {
      setMobileMenuOpen(false);
    }
  }, [location.pathname, location.search]);

  // Accessible keyboard & click outside handling for mobile menu
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileMenuOpen(false);
    };
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMobileMenuOpen(false);
      }
    };
    if (mobileMenuOpen) {
      window.addEventListener('keydown', handleKeyDown);
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [mobileMenuOpen]);

  // Run session check once on mount. Unauthenticated visitors get 401, which is handled gracefully.
  useEffect(() => {
    let active = true;
    api
      .me()
      .then((data) => {
        if (active) setUser(data);
      })
      .catch(() => {
        // Unauthenticated visitor is default public state
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
      setMobileMenuOpen(false);
      navigate('/');
    } catch {
      setLogoutError('Не удалось выйти. Повторите попытку.');
    } finally {
      setLoggingOut(false);
    }
  };

  const isLeaderboardActive = location.pathname === '/' || location.pathname.startsWith('/repositories');
  const isSourceCraftActive = location.pathname === '/sourcecraft';

  return (
    <header className="app-header">
      <div className="app-header-content">
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
          <Link to="/" className="brand-logo-link" aria-label="SourceHealth главная">
            <div
              className="brand-logo-pill"
              style={{
                backgroundColor: theme === 'dark' ? '#ffffff' : 'transparent',
                padding: theme === 'dark' ? '3px 8px' : 0,
                borderRadius: theme === 'dark' ? 'var(--sh-radius-sm)' : 0,
                display: 'inline-flex',
                alignItems: 'center',
                transition: 'background var(--sh-transition)',
              }}
            >
              <img
                src="/brand/sourcehealth-logo.png"
                alt="SourceHealth"
                className="brand-logo-img"
              />
            </div>
            <span className="brand-logo-badge">beta</span>
          </Link>
          <nav className="app-nav" aria-label="Основная навигация">
            <Link
              to="/"
              className={`nav-link ${isLeaderboardActive ? 'active' : ''}`}
            >
              Лидерборд
            </Link>
            <Link
              to="/sourcecraft"
              className={`nav-link ${isSourceCraftActive ? 'active' : ''}`}
            >
              Мой SourceCraft
            </Link>
          </nav>
        </div>

        {/* Desktop actions */}
        <div className="header-actions-desktop" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {/* Theme switcher */}
          <button
            type="button"
            className="theme-toggle-btn"
            onClick={toggleTheme}
            aria-label={`Переключить тему (сейчас: ${theme === 'dark' ? 'тёмная' : 'светлая'})`}
            title={`Тема: ${theme === 'dark' ? 'Тёмная (нажмите для переключения на светлую)' : 'Светлая (нажмите для переключения на тёмную)'}`}
          >
            {theme === 'dark' ? '🌙' : '☀'}
          </button>

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
                <span>{user.id ? user.id.slice(0, 10) : 'Сессия активна'}</span>
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
                fontSize: '0.84rem',
                fontWeight: 600,
                color: 'var(--sh-text-primary)',
                backgroundColor: 'var(--sh-bg-surface-elevated)',
                border: '1px solid var(--sh-border-default)',
                padding: '0.35rem 0.75rem',
                borderRadius: 'var(--sh-radius-sm)',
                textDecoration: 'none',
                whiteSpace: 'nowrap',
                transition: 'border-color var(--sh-transition), background var(--sh-transition)',
              }}
              aria-label="Войти через Яндекс ID"
            >
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: '18px',
                  height: '18px',
                  backgroundColor: '#fc3f1d',
                  color: '#ffffff',
                  borderRadius: '4px',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  lineHeight: 1,
                }}
                aria-hidden="true"
              >
                Я
              </span>
              <span>Войти</span>
            </a>
          )}
        </div>

        {/* Mobile menu trigger */}
        <button
          type="button"
          className="mobile-menu-btn"
          onClick={() => setMobileMenuOpen((prev) => !prev)}
          aria-label={mobileMenuOpen ? 'Закрыть меню' : 'Открыть меню навигации'}
          aria-expanded={mobileMenuOpen}
          aria-controls="mobile-nav-panel"
        >
          <span aria-hidden="true">{mobileMenuOpen ? '✕' : '☰'}</span>
        </button>
      </div>

      {/* Accessible mobile drawer panel */}
      {mobileMenuOpen && (
        <div id="mobile-nav-panel" className="mobile-nav-panel" ref={menuRef} role="region" aria-label="Мобильное меню">
          <nav className="mobile-nav-links" aria-label="Мобильная навигация">
            <Link
              to="/"
              className={`mobile-nav-link ${isLeaderboardActive ? 'active' : ''}`}
              onClick={() => setMobileMenuOpen(false)}
            >
              Лидерборд
            </Link>
            <Link
              to="/sourcecraft"
              className={`mobile-nav-link ${isSourceCraftActive ? 'active' : ''}`}
              onClick={() => setMobileMenuOpen(false)}
            >
              Мой SourceCraft
            </Link>
          </nav>

          <div className="mobile-nav-divider" />

          <div className="mobile-nav-actions">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
              <span style={{ fontSize: '0.88rem', color: 'var(--sh-text-secondary)', fontWeight: 500 }}>
                Тема:
              </span>
              <button
                type="button"
                className="theme-toggle-btn"
                onClick={toggleTheme}
                aria-label={`Переключить тему (сейчас: ${theme === 'dark' ? 'тёмная' : 'светлая'})`}
              >
                {theme === 'dark' ? '🌙 Тёмная' : '☀ Светлая'}
              </button>
            </div>

            {user ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', width: '100%', marginTop: '0.25rem' }}>
                <div
                  className="auth-status-badge"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.4rem',
                    fontSize: '0.82rem',
                    color: 'var(--sh-text-secondary)',
                    backgroundColor: 'var(--sh-bg-surface-elevated)',
                    padding: '0.35rem 0.65rem',
                    borderRadius: 'var(--sh-radius-sm)',
                    border: '1px solid var(--sh-border-default)',
                  }}
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
                  <span>ID: {user.id ? user.id.slice(0, 14) : 'Сессия активна'}</span>
                </div>
                <Button
                  variant="outline"
                  size="md"
                  onClick={handleLogout}
                  disabled={loggingOut}
                  aria-label="Выйти из аккаунта"
                  style={{ width: '100%' }}
                >
                  {loggingOut ? 'Выход…' : 'Выйти'}
                </Button>
              </div>
            ) : (
              <div style={{ width: '100%', marginTop: '0.25rem' }}>
                <a
                  href="/api/v1/auth/yandex/login"
                  className="auth-login-btn"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '0.5rem',
                    width: '100%',
                    fontSize: '0.9rem',
                    fontWeight: 600,
                    color: 'var(--sh-text-primary)',
                    backgroundColor: 'var(--sh-bg-surface-elevated)',
                    border: '1px solid var(--sh-border-default)',
                    padding: '0.5rem 1rem',
                    borderRadius: 'var(--sh-radius-sm)',
                    textDecoration: 'none',
                  }}
                  aria-label="Войти через Яндекс ID"
                >
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      width: '18px',
                      height: '18px',
                      backgroundColor: '#fc3f1d',
                      color: '#ffffff',
                      borderRadius: '4px',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      lineHeight: 1,
                    }}
                    aria-hidden="true"
                  >
                    Я
                  </span>
                  <span>Войти через Яндекс ID</span>
                </a>
              </div>
            )}
          </div>
        </div>
      )}
    </header>
  );
};
