import React, { useEffect, useRef } from 'react';

export interface KeyboardHelpModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const KeyboardHelpModal: React.FC<KeyboardHelpModalProps> = ({ isOpen, onClose }) => {
  const modalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  useEffect(() => {
    if (isOpen) {
      modalRef.current?.focus();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const shortcuts = [
    {
      keys: ['Ctrl', 'K'],
      macKeys: ['⌘', 'K'],
      description: 'Открыть командную строку и быстрый поиск по каталогу',
    },
    {
      keys: ['?'],
      macKeys: ['?'],
      description: 'Показать эту справку по горячим клавишам',
    },
    {
      keys: ['Esc'],
      macKeys: ['Esc'],
      description: 'Закрыть активное диалоговое или модальное окно',
    },
  ];

  const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPod|iPad/i.test(navigator.userAgent);

  return (
    <div
      className="sc-modal-backdrop"
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: '1rem',
      }}
    >
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="keyboard-help-title"
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '100%',
          maxWidth: '460px',
          backgroundColor: 'var(--sh-bg-surface-elevated, #1c1c1f)',
          borderRadius: 'var(--sh-radius-md, 8px)',
          border: '1px solid var(--sh-border-default, #2e2e32)',
          boxShadow: '0 8px 30px rgba(0, 0, 0, 0.35)',
          padding: 'var(--sh-space-5, 1.25rem)',
          color: 'var(--sh-text-primary, #ffffff)',
          outline: 'none',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: 'var(--sh-space-4, 1rem)',
          }}
        >
          <h2
            id="keyboard-help-title"
            style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}
          >
            Горячие клавиши
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Закрыть справку"
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--sh-text-muted, #8e8e93)',
              fontSize: '1.25rem',
              cursor: 'pointer',
              padding: '0.2rem 0.5rem',
              borderRadius: 'var(--sh-radius-sm, 4px)',
            }}
          >
            ✕
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {shortcuts.map((sc, i) => {
            const activeKeys = isMac ? sc.macKeys : sc.keys;
            return (
              <div
                key={i}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.5rem 0.75rem',
                  backgroundColor: 'var(--sh-bg-base, #121214)',
                  borderRadius: 'var(--sh-radius-sm, 4px)',
                  border: '1px solid var(--sh-border-subtle, #27272a)',
                  gap: '1rem',
                }}
              >
                <span style={{ fontSize: '0.85rem', color: 'var(--sh-text-secondary, #d1d1d6)' }}>
                  {sc.description}
                </span>
                <div style={{ display: 'flex', gap: '0.3rem', alignItems: 'center' }}>
                  {activeKeys.map((k, ki) => (
                    <kbd
                      key={ki}
                      style={{
                        padding: '0.2rem 0.5rem',
                        fontSize: '0.8rem',
                        fontFamily: 'var(--sh-font-mono, monospace)',
                        fontWeight: 600,
                        backgroundColor: 'var(--sh-bg-surface, #242428)',
                        border: '1px solid var(--sh-border-default, #3a3a3c)',
                        borderRadius: '4px',
                        boxShadow: '0 1px 2px rgba(0, 0, 0, 0.2)',
                        color: 'var(--sh-text-primary, #ffffff)',
                      }}
                    >
                      {k}
                    </kbd>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        <div
          style={{
            marginTop: 'var(--sh-space-4, 1rem)',
            textAlign: 'right',
          }}
        >
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: '0.4rem 0.9rem',
              fontSize: '0.85rem',
              fontWeight: 500,
              backgroundColor: 'var(--sh-bg-surface, #242428)',
              color: 'var(--sh-text-primary, #ffffff)',
              border: '1px solid var(--sh-border-default, #3a3a3c)',
              borderRadius: 'var(--sh-radius-sm, 4px)',
              cursor: 'pointer',
            }}
          >
            Понятно
          </button>
        </div>
      </div>
    </div>
  );
};
