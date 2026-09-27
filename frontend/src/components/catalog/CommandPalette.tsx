import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, type Repository } from '../../api/client';
import { RepositoryAvatar } from './RepositoryAvatar';

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectSearch?: (term: string) => void;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  onSelectSearch,
}) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Repository[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const reqSeqRef = useRef(0);
  const abortCtrlRef = useRef<AbortController | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    reqSeqRef.current += 1;
    if (abortCtrlRef.current) {
      abortCtrlRef.current.abort();
      abortCtrlRef.current = null;
    }
    setQuery('');
    setResults([]);
    setLoading(false);
    setSelectedIndex(0);

    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;

    const trimmed = query.trim();
    if (!trimmed) {
      reqSeqRef.current += 1;
      if (abortCtrlRef.current) {
        abortCtrlRef.current.abort();
        abortCtrlRef.current = null;
      }
      setResults([]);
      setLoading(false);
      return;
    }

    const currentSeq = ++reqSeqRef.current;
    if (abortCtrlRef.current) {
      abortCtrlRef.current.abort();
    }
    const controller = new AbortController();
    abortCtrlRef.current = controller;

    setLoading(true);
    const timer = setTimeout(() => {
      api
        .repositories({ q: trimmed, limit: 8 }, { signal: controller.signal })
        .then((res) => {
          if (currentSeq === reqSeqRef.current && !controller.signal.aborted) {
            setResults(res.items);
            setSelectedIndex(0);
            setLoading(false);
          }
        })
        .catch((err) => {
          if (err?.name === 'AbortError') return;
          if (currentSeq === reqSeqRef.current && !controller.signal.aborted) {
            setResults([]);
            setLoading(false);
          }
        });
    }, 150);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, isOpen]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      onClose();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (results.length > 0 ? (prev + 1) % results.length : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (results.length > 0 ? (prev - 1 + results.length) % results.length : 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (results[selectedIndex]) {
        navigate(`/repositories/${results[selectedIndex].id}`);
        onClose();
      } else if (query.trim() && onSelectSearch) {
        onSelectSearch(query.trim());
        onClose();
      }
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="sh-command-palette-backdrop"
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: '15vh',
        zIndex: 2000,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="sh-command-palette"
        style={{
          width: '100%',
          maxWidth: '560px',
          backgroundColor: 'var(--sh-bg-surface, #ffffff)',
          border: '1px solid var(--sh-border-default, #d0d7de)',
          borderRadius: 'var(--sh-radius-lg, 12px)',
          boxShadow: 'var(--sh-shadow-lg, 0 10px 30px rgba(0,0,0,0.25))',
          overflow: 'hidden',
        }}
        onKeyDown={handleKeyDown}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            padding: '12px 16px',
            borderBottom: '1px solid var(--sh-border-subtle, #e1e4e8)',
            gap: '10px',
          }}
        >
          <span style={{ color: 'var(--sh-text-muted, #64748b)' }}>🔍</span>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Быстрый поиск по проектам и организациям..."
            style={{
              flex: 1,
              border: 'none',
              outline: 'none',
              fontSize: '1rem',
              color: 'var(--sh-text-primary, #1f2328)',
              backgroundColor: 'transparent',
            }}
          />
          <kbd
            style={{
              fontSize: '11px',
              padding: '2px 6px',
              borderRadius: '4px',
              backgroundColor: 'var(--sh-bg-surface-elevated, #f1f3f5)',
              color: 'var(--sh-text-muted, #64748b)',
              border: '1px solid var(--sh-border-subtle, #e1e4e8)',
            }}
          >
            ESC
          </kbd>
        </div>

        <div style={{ maxHeight: '360px', overflowY: 'auto', padding: '6px 0' }}>
          {loading && (
            <div style={{ padding: '16px', textAlign: 'center', color: 'var(--sh-text-muted, #64748b)', fontSize: '0.875rem' }}>
              Поиск...
            </div>
          )}

          {!loading && results.length === 0 && query.trim() && (
            <div style={{ padding: '16px', textAlign: 'center', color: 'var(--sh-text-muted, #64748b)', fontSize: '0.875rem' }}>
              Ничего не найдено в каталоге
            </div>
          )}

          {!loading &&
            results.map((repo, idx) => {
              const isSelected = idx === selectedIndex;
              return (
                <div
                  key={repo.id}
                  onClick={() => {
                    navigate(`/repositories/${repo.id}`);
                    onClose();
                  }}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '8px 16px',
                    cursor: 'pointer',
                    backgroundColor: isSelected
                      ? 'var(--sh-bg-surface-hover, #eaeff5)'
                      : 'transparent',
                  }}
                >
                  <RepositoryAvatar name={repo.repository_slug} logoUrl={repo.logo_url} size={28} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--sh-text-primary, #1f2328)' }}>
                      {repo.organization_slug}/{repo.repository_slug}
                    </div>
                    {repo.description && (
                      <div
                        style={{
                          fontSize: '0.75rem',
                          color: 'var(--sh-text-muted, #64748b)',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {repo.description}
                      </div>
                    )}
                  </div>
                  {repo.health_score != null && (
                    <span
                      style={{
                        fontSize: '0.8125rem',
                        fontWeight: 700,
                        color: repo.health_score >= 80 ? 'var(--sh-health-good, #1a7f37)' : 'inherit',
                      }}
                    >
                      {repo.health_score}
                    </span>
                  )}
                </div>
              );
            })}
        </div>
      </div>
    </div>
  );
};
