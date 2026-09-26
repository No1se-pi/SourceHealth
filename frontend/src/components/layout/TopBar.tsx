import React from 'react';
import { Link, useLocation } from 'react-router-dom';

export interface TopBarProps {
  onToggleMobile: () => void;
  onOpenAppearance: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({ onToggleMobile, onOpenAppearance }) => {
  const location = useLocation();

  // Determine contextual breadcrumb path
  const path = location.pathname;
  let breadcrumbTitle = 'Лидерборд';

  if (path.startsWith('/repositories/')) {
    const repoSlug = path.replace('/repositories/', '');
    breadcrumbTitle = `Репозитории / ${decodeURIComponent(repoSlug)}`;
  } else if (path.startsWith('/analyses/')) {
    const analysisId = path.replace('/analyses/', '');
    breadcrumbTitle = `Анализ / #${analysisId.slice(0, 8)}`;
  } else if (path === '/sourcecraft') {
    breadcrumbTitle = 'Интеграция SourceCraft';
  } else if (path === '/auth/callback') {
    breadcrumbTitle = 'Авторизация';
  }

  return (
    <header className="sc-topbar" aria-label="Верхняя контекстная панель">
      <div className="sc-topbar-left">
        {/* Mobile Hamburger Button */}
        <button
          type="button"
          className="mobile-menu-btn"
          onClick={onToggleMobile}
          aria-label="Открыть навигацию"
        >
          <svg viewBox="0 0 16 16" width="18" height="18" fill="currentColor" aria-hidden="true">
            <path d="M1 3.5h14a.75.75 0 0 0 0-1.5H1a.75.75 0 0 0 0 1.5zm0 5h14a.75.75 0 0 0 0-1.5H1a.75.75 0 0 0 0 1.5zm0 5h14a.75.75 0 0 0 0-1.5H1a.75.75 0 0 0 0 1.5z" />
          </svg>
        </button>

        {/* Breadcrumb Navigation */}
        <nav className="sc-breadcrumbs" aria-label="Хлебные крошки">
          <Link to="/" className="sc-breadcrumb-home" aria-label="Главная">
            <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor" aria-hidden="true">
              <path d="M8.354 1.146a.5.5 0 0 0-.708 0l-6 6A.5.5 0 0 0 2 7.5v7a.5.5 0 0 0 .5.5h4.5a.5.5 0 0 0 .5-.5v-4h1v4a.5.5 0 0 0 .5.5h4.5a.5.5 0 0 0 .5-.5v-7a.5.5 0 0 0-.146-.354L8.354 1.146z" />
            </svg>
          </Link>
          <span className="sc-breadcrumb-sep">/</span>
          <span className="sc-breadcrumb-current sc-truncate">{breadcrumbTitle}</span>
        </nav>
      </div>

      <div className="sc-topbar-right">
        {/* Quick Appearance Shortcut Button */}
        <button
          type="button"
          className="sc-topbar-icon-btn"
          onClick={onOpenAppearance}
          title="Настроить внешний вид (тема, акцент)"
          aria-label="Настройки внешнего вида"
        >
          <svg viewBox="0 0 16 16" width="15" height="15" fill="currentColor" aria-hidden="true">
            <path d="M8 0a8 8 0 1 0 0 16A8 8 0 0 0 8 0zm0 1.5a6.5 6.5 0 1 1 0 13V1.5z" />
          </svg>
          <span className="sc-accent-dot-mini" aria-hidden="true" />
        </button>

        <a
          href="https://sourcecraft.dev"
          target="_blank"
          rel="noopener noreferrer"
          className="sc-topbar-link-pill"
          title="Открыть SourceCraft"
        >
          <span>SourceCraft</span>
          <span className="sc-arrow" aria-hidden="true">↗</span>
        </a>
      </div>
    </header>
  );
};
