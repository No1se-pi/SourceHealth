import React from 'react';

interface LoadingStateProps {
  message?: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = 'Загрузка данных…',
  size = 'md',
  className = '',
}) => {
  const spinnerSizes = {
    sm: 16,
    md: 24,
    lg: 36,
  };

  const spinnerPx = spinnerSizes[size];

  return (
    <div
      role="status"
      aria-live="polite"
      className={className}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 'var(--sh-space-3)',
        padding: 'var(--sh-space-8) var(--sh-space-4)',
        color: 'var(--sh-text-secondary)',
      }}
    >
      <span
        className="animate-spin"
        style={{
          width: spinnerPx,
          height: spinnerPx,
          border: '2px solid var(--sh-border-default)',
          borderTopColor: 'var(--sh-brand)',
          borderRadius: '50%',
          display: 'inline-block',
        }}
        aria-hidden="true"
      />
      <span style={{ fontSize: size === 'sm' ? '0.85rem' : '0.95rem' }}>
        {message}
      </span>
    </div>
  );
};
