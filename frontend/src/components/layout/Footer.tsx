import React from 'react';

export const Footer: React.FC = () => {
  return (
    <footer className="sc-workspace-footer" aria-label="Информация о платформе">
      <div className="sc-footer-left">
        <span className="sc-footer-brand">SourceHealth</span>
        <span className="sc-footer-sep">·</span>
        <span className="sc-footer-desc">
          Объективная оценка качества и безопасности репозиториев для SourceCraft
        </span>
      </div>
      <div className="sc-footer-right">
        <span className="sc-footer-item" title="Отсутствие данных в источниках не приравнивается к плохому качеству">
          Принцип: NO_DATA ≠ 0
        </span>
        <span className="sc-footer-sep">•</span>
        <a
          href="https://sourcecraft.dev"
          target="_blank"
          rel="noopener noreferrer"
          className="sc-footer-link"
        >
          SourceCraft.dev ↗
        </a>
        <span className="sc-footer-sep">•</span>
        <span className="sc-footer-tag">ЛЦТ 2026</span>
      </div>
    </footer>
  );
};
