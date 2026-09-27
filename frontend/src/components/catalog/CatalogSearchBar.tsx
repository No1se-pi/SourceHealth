import React, { useEffect, useRef } from 'react';

interface CatalogSearchBarProps {
  value: string;
  onChange: (newValue: string) => void;
  onClear: () => void;
  onOpenCommandPalette?: () => void;
}

export const CatalogSearchBar: React.FC<CatalogSearchBarProps> = ({
  value,
  onChange,
  onClear,
  onOpenCommandPalette,
}) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const isMac = typeof window !== 'undefined' && /Mac|iPod|iPhone|iPad/.test(navigator.platform);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        if (onOpenCommandPalette) {
          onOpenCommandPalette();
        } else {
          inputRef.current?.focus();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onOpenCommandPalette]);

  const looksLikeRepoPath =
    value.includes('/') ||
    value.includes('sourcecraft.dev') ||
    value.includes('api.sourcecraft.tech');

  return (
    <div className="sh-search-bar-wrapper" style={{ position: 'relative', width: '100%' }}>
      <div
        style={{
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          width: '100%',
        }}
      >
        <span
          style={{
            position: 'absolute',
            left: '12px',
            color: 'var(--sh-text-muted, #64748b)',
            pointerEvents: 'none',
            display: 'flex',
            alignItems: 'center',
          }}
          aria-hidden="true"
        >
          🔍
        </span>

        <input
          ref={inputRef}
          type="search"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Поиск по названию, организации (org/repo) или описанию..."
          aria-label="Поиск по каталогу"
          style={{
            width: '100%',
            height: '42px',
            paddingLeft: '38px',
            paddingRight: value ? '76px' : '64px',
            fontSize: '0.875rem',
            color: 'var(--sh-text-primary, #1f2328)',
            backgroundColor: 'var(--sh-bg-input, #ffffff)',
            border: '1px solid var(--sh-border-default, #d0d7de)',
            borderRadius: 'var(--sh-radius-md, 8px)',
            outline: 'none',
            transition: 'border-color var(--sh-transition)',
          }}
        />

        <div
          style={{
            position: 'absolute',
            right: '10px',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          {value && (
            <button
              type="button"
              onClick={onClear}
              aria-label="Очистить поиск"
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--sh-text-muted, #64748b)',
                cursor: 'pointer',
                fontSize: '14px',
                padding: '4px 6px',
                borderRadius: '4px',
              }}
            >
              ✕
            </button>
          )}

          <kbd
            onClick={() => {
              if (onOpenCommandPalette) onOpenCommandPalette();
              else inputRef.current?.focus();
            }}
            style={{
              padding: '2px 6px',
              fontSize: '10px',
              color: 'var(--sh-text-muted, #64748b)',
              backgroundColor: 'var(--sh-bg-surface-elevated, #f1f3f5)',
              border: '1px solid var(--sh-border-subtle, #e1e4e8)',
              borderRadius: 'var(--sh-radius-sm, 4px)',
              cursor: 'pointer',
              userSelect: 'none',
            }}
            title={isMac ? 'Нажмите ⌘K' : 'Нажмите Ctrl+K'}
          >
            {isMac ? '⌘K' : 'Ctrl+K'}
          </kbd>
        </div>
      </div>

      {looksLikeRepoPath && (
        <div
          style={{
            fontSize: '0.75rem',
            color: 'var(--sh-brand-text, #dc2626)',
            marginTop: '4px',
            paddingLeft: '6px',
          }}
        >
          Поиск по прямому идентификатору или URL SourceCraft.
        </div>
      )}
    </div>
  );
};
