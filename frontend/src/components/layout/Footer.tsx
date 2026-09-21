import React from 'react';

export const Footer: React.FC = () => {
  return (
    <footer className="app-footer">
      <div className="app-footer-content">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <span style={{ fontWeight: 600, color: 'var(--sh-text-primary)' }}>SourceHealth</span>
          <span>·</span>
          <span>Система объективной оценки качества и безопасности репозиториев для SourceCraft</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <a
            href="https://sourcecraft.tech"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: 'var(--sh-text-muted)' }}
          >
            SourceCraft ↗
          </a>
          <span style={{ color: 'var(--sh-border-strong)' }}>•</span>
          <span title="Отсутствие данных в источниках не приравнивается к плохому качеству">
            Принцип: NO_DATA ≠ 0
          </span>
          <span style={{ color: 'var(--sh-border-strong)' }}>•</span>
          <span>ЛЦТ 2026</span>
        </div>
      </div>
    </footer>
  );
};
