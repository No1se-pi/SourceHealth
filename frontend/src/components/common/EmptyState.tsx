import React from 'react';

interface EmptyStateProps {
  title?: string;
  description?: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title = 'Нет данных',
  description,
  action,
  icon,
  className = '',
}) => {
  return (
    <div
      className={className}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        padding: 'var(--sh-space-10) var(--sh-space-4)',
        border: '1px dashed var(--sh-border-default)',
        borderRadius: 'var(--sh-radius-md)',
        backgroundColor: 'var(--sh-bg-surface)',
        margin: 'var(--sh-space-4) 0',
      }}
    >
      {icon && (
        <div
          style={{
            fontSize: '2rem',
            color: 'var(--sh-text-muted)',
            marginBottom: 'var(--sh-space-3)',
          }}
        >
          {icon}
        </div>
      )}
      <h3 style={{ margin: 0, fontSize: '1.15rem', color: 'var(--sh-text-primary)' }}>
        {title}
      </h3>
      {description && (
        <p
          style={{
            maxWidth: '460px',
            margin: 'var(--sh-space-2) 0 var(--sh-space-4) 0',
            fontSize: '0.9rem',
            color: 'var(--sh-text-secondary)',
          }}
        >
          {description}
        </p>
      )}
      {action && <div>{action}</div>}
    </div>
  );
};
