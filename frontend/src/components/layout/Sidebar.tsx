import React, { useEffect, useState } from 'react';
import { NavLink, Link, useLocation } from 'react-router-dom';
import { api, type User } from '../../api/client';

export interface SidebarProps {
  mobileOpen: boolean;
  onClose: () => void;
  onOpenAppearance: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ mobileOpen, onClose, onOpenAppearance }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);
  const location = useLocation();

  useEffect(() => {
    let active = true;
    api
      .me()
      .then((u) => {
        if (active) setUser(u);
      })
      .catch(() => {
        if (active) setUser(null);
      });
    return () => {
      active = false;
    };
  }, []);

  // Close mobile drawer on navigation
  useEffect(() => {
    onClose();
  }, [location.pathname]);

  const handleLogout = async () => {
    if (loggingOut) return;
    setLoggingOut(true);
    try {
      await api.logout();
      setUser(null);
    } catch {
      // ignore
    } finally {
      setLoggingOut(false);
    }
  };

  return (
    <aside className={`sc-sidebar ${mobileOpen ? 'mobile-open' : ''}`} aria-label="Основная навигация">
      {/* Brand Header */}
      <div className="sc-sidebar-brand">
        <Link to="/" className="sc-brand-link" aria-label="SourceHealth главная">
          <img
            src="/brand/sourcehealth-mark.png"
            alt="SourceHealth"
            className="sc-brand-mark-img"
            width="26"
            height="26"
          />
          <div className="sc-brand-text-wrap">
            <span className="sc-brand-title">
              <span className="sc-brand-word-source">Source</span>
              <span className="sc-brand-word-health">Health</span>
            </span>
            <span className="sc-brand-sub">Platform</span>
          </div>
          <span className="sc-brand-badge">BETA</span>
        </Link>
        <button
          type="button"
          className="sc-sidebar-close-btn"
          onClick={onClose}
          aria-label="Закрыть меню"
        >
          ✕
        </button>
      </div>

      {/* Main Navigation Items */}
      <div className="sc-sidebar-content">
        <div className="sc-nav-group">
          <div className="sc-nav-group-title">Навигация</div>
          <NavLink
            to="/"
            end
            className={({ isActive }) => `sc-nav-item ${isActive ? 'active' : ''}`}
          >
            <svg className="sc-nav-icon" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" aria-hidden="true">
              <rect x="2" y="2" width="5" height="5" rx="1" />
              <rect x="9" y="2" width="5" height="5" rx="1" />
              <rect x="2" y="9" width="5" height="5" rx="1" />
              <rect x="9" y="9" width="5" height="5" rx="1" />
            </svg>
            <span className="sc-nav-label">Лидерборд</span>
          </NavLink>

          <NavLink
            to="/sourcecraft"
            className={({ isActive }) => `sc-nav-item ${isActive ? 'active' : ''}`}
          >
            <svg className="sc-nav-icon" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" aria-hidden="true">
              <path d="M2 4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V4zm2-1a1 1 0 0 0-1 1v2a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V4a1 1 0 0 0-1-1H4zm-2 7a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-2zm2-1a1 1 0 0 0-1 1v2a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1H4z" />
            </svg>
            <span className="sc-nav-label">Мой SourceCraft</span>
          </NavLink>
        </div>

        {/* Repositories Quick Group */}
        <div className="sc-nav-group">
          <div className="sc-nav-group-title">Репозитории</div>
          <Link
            to="/repositories/case-18-repo-health-score-team-41"
            className="sc-nav-item sc-nav-sub-item"
            title="case-18-repo-health-score-team-41"
          >
            <svg className="sc-nav-icon" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" aria-hidden="true">
              <path d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5v-9zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8V1.5z" />
            </svg>
            <span className="sc-nav-label sc-truncate">case-18-team-41</span>
          </Link>
        </div>

        {/* SourceCraft Platform Ecosystem */}
        <div className="sc-nav-group">
          <div className="sc-nav-group-title">Экосистема</div>
          <a
            href="https://sourcecraft.dev"
            target="_blank"
            rel="noopener noreferrer"
            className="sc-nav-item sc-nav-external"
          >
            <svg className="sc-nav-icon" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" aria-hidden="true">
              <path d="M0 8a8 8 0 1 1 16 0A8 8 0 0 1 0 8zm8-6.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13z" />
            </svg>
            <span className="sc-nav-label">SourceCraft.dev</span>
            <span className="sc-external-arrow">↗</span>
          </a>
        </div>
      </div>

      {/* Sidebar Footer Controls */}
      <div className="sc-sidebar-footer">
        {/* Appearance Control Button */}
        <button
          type="button"
          className="sc-sidebar-action-btn"
          onClick={onOpenAppearance}
          aria-label="Настройки внешнего вида и темы"
        >
          <svg className="sc-btn-icon" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" aria-hidden="true">
            <path d="M8 0a8 8 0 1 0 0 16A8 8 0 0 0 8 0zm0 1.5a6.5 6.5 0 1 1 0 13V1.5z" />
          </svg>
          <span className="sc-btn-text">Внешний вид</span>
          <span className="sc-accent-dot" aria-hidden="true" />
        </button>

        {/* Auth / Profile Area */}
        <div className="sc-sidebar-user">
          {user ? (
            <div className="sc-user-card">
              <div className="sc-user-avatar" aria-hidden="true">
                {user.id ? user.id.charAt(0).toUpperCase() : 'U'}
              </div>
              <div className="sc-user-info">
                <span className="sc-user-name sc-truncate">{user.id || 'Пользователь'}</span>
                <span className="sc-user-role">Яндекс ID</span>
              </div>
              <button
                type="button"
                className="sc-user-logout-btn"
                onClick={handleLogout}
                disabled={loggingOut}
                title="Выйти из аккаунта"
                aria-label="Выйти"
              >
                <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor" aria-hidden="true">
                  <path d="M2 2.75C2 1.784 2.784 1 3.75 1h2.5a.75.75 0 0 1 0 1.5h-2.5a.25.25 0 0 0-.25.25v10.5c0 .138.112.25.25.25h2.5a.75.75 0 0 1 0 1.5h-2.5A1.75 1.75 0 0 1 2 13.25V2.75zm10.44 4.5H6.75a.75.75 0 0 0 0 1.5h5.69l-1.72 1.72a.75.75 0 1 0 1.06 1.06l3-3a.75.75 0 0 0 0-1.06l-3-3a.75.75 0 1 0-1.06 1.06l1.72 1.72z" />
                </svg>
              </button>
            </div>
          ) : (
            <a
              href="/api/v1/auth/yandex/login"
              className="sc-login-sidebar-btn"
            >
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" className="sc-yandex-id-mark">
                <path d="M2.04 12c0-5.523 4.476-10 10-10 5.522 0 10 4.477 10 10s-4.478 10-10 10c-5.524 0-10-4.477-10-10z" fill="#FC3F1D" />
                <path d="M13.32 7.666h-.924c-1.694 0-2.585.858-2.585 2.123 0 1.43.616 2.1 1.881 2.959l1.045.704-3.003 4.487H7.49l2.695-4.014c-1.55-1.111-2.42-2.19-2.42-4.015 0-2.288 1.595-3.85 4.62-3.85h3.003v11.868H13.32V7.666z" fill="#FFFFFF" />
              </svg>
              <span>Войти через Яндекс ID</span>
            </a>
          )}
        </div>
      </div>
    </aside>
  );
};
