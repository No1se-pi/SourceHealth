import React from 'react';
import { useNavigate } from 'react-router-dom';
import type { Repository } from '../../api/client';

interface CompareTrayProps {
  selectedRepos: Repository[];
  onRemoveRepo: (repoId: string) => void;
  onClearAll: () => void;
}

export const CompareTray: React.FC<CompareTrayProps> = ({
  selectedRepos,
  onRemoveRepo,
  onClearAll,
}) => {
  const navigate = useNavigate();

  if (selectedRepos.length === 0) return null;

  const canCompare = selectedRepos.length >= 2 && selectedRepos.length <= 4;

  const handleCompare = () => {
    if (!canCompare) return;
    const params = new URLSearchParams();
    selectedRepos.forEach((r) => params.append('repository_id', r.id));
    navigate(`/compare?${params.toString()}`);
  };

  return (
    <div
      className="sh-compare-tray"
      style={{
        position: 'fixed',
        bottom: '20px',
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 500,
        backgroundColor: 'var(--sh-bg-surface, #ffffff)',
        border: '1px solid var(--sh-border-strong, #57606a)',
        borderRadius: 'var(--sh-radius-lg, 12px)',
        boxShadow: 'var(--sh-shadow-lg, 0 10px 25px rgba(0,0,0,0.2))',
        padding: '12px 20px',
        display: 'flex',
        alignItems: 'center',
        gap: '16px',
        maxWidth: '90vw',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--sh-text-primary, #1f2328)' }}>
          Сравнение ({selectedRepos.length} из 4):
        </span>

        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {selectedRepos.map((repo) => (
            <span
              key={repo.id}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '3px 8px',
                fontSize: '0.75rem',
                backgroundColor: 'var(--sh-bg-surface-elevated, #f1f3f5)',
                border: '1px solid var(--sh-border-default, #d0d7de)',
                borderRadius: 'var(--sh-radius-sm, 6px)',
              }}
            >
              <span>{repo.repository_slug}</span>
              <button
                type="button"
                onClick={() => onRemoveRepo(repo.id)}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--sh-text-muted, #64748b)',
                  padding: '0 2px',
                  fontSize: '11px',
                }}
              >
                ✕
              </button>
            </span>
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <button
          type="button"
          onClick={onClearAll}
          style={{
            background: 'none',
            border: 'none',
            fontSize: '0.8125rem',
            color: 'var(--sh-text-muted, #64748b)',
            cursor: 'pointer',
            padding: '6px 8px',
          }}
        >
          Очистить
        </button>

        <button
          type="button"
          disabled={!canCompare}
          onClick={handleCompare}
          style={{
            padding: '6px 16px',
            borderRadius: 'var(--sh-radius-sm, 6px)',
            border: '1px solid var(--sh-btn-primary-border, #1f2328)',
            backgroundColor: canCompare
              ? 'var(--sh-btn-primary-bg, #1f2328)'
              : 'var(--sh-bg-surface-elevated, #f1f3f5)',
            color: canCompare ? 'var(--sh-btn-primary-text, #ffffff)' : 'var(--sh-text-muted, #64748b)',
            fontWeight: 600,
            fontSize: '0.8125rem',
            cursor: canCompare ? 'pointer' : 'not-allowed',
            opacity: canCompare ? 1 : 0.6,
          }}
          title={
            selectedRepos.length < 2
              ? 'Выберите минимум 2 проекта для сравнения'
              : selectedRepos.length > 4
              ? 'Максимум 4 проекта'
              : 'Перейти к сравнению проектов'
          }
        >
          Сравнить ({selectedRepos.length})
        </button>
      </div>
    </div>
  );
};
