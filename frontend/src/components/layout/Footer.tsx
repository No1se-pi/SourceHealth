import React from 'react';

export const Footer: React.FC = () => {
  return (
    <footer className="app-footer">
      <div className="app-footer-content">
        <div>
          <span>SourceHealth · Анализ здоровья репозиториев для ЛЦТ 2026</span>
        </div>
        <div style={{ display: 'flex', gap: '1.25rem' }}>
          <a
            href="https://sourcecraft.tech"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: 'var(--sh-text-muted)' }}
          >
            SourceCraft
          </a>
          <span style={{ color: 'var(--sh-border-strong)' }}>•</span>
          <span>Принцип: NO_DATA ≠ 0</span>
        </div>
      </div>
    </footer>
  );
};
