import React from 'react';

interface CardProps {
  children: React.ReactNode;
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  headerAction?: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
  elevated?: boolean;
  style?: React.CSSProperties;
}

export const Card: React.FC<CardProps> = ({
  children,
  title,
  subtitle,
  headerAction,
  footer,
  className = '',
  elevated = false,
  style,
}) => {
  const baseStyle: React.CSSProperties = {
    backgroundColor: elevated ? 'var(--sh-bg-surface-elevated)' : 'var(--sh-bg-surface)',
    border: '1px solid var(--sh-border-default)',
    borderRadius: 'var(--sh-radius-md)',
    boxShadow: 'var(--sh-shadow-sm)',
    padding: 'var(--sh-space-5)',
    transition: 'border-color var(--sh-transition), background-color var(--sh-transition), box-shadow var(--sh-transition)',
    ...style,
  };

  const headerStyle: React.CSSProperties = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    flexWrap: 'wrap',
    gap: 'var(--sh-space-3)',
    marginBottom: subtitle || children ? 'var(--sh-space-4)' : 0,
    borderBottom: subtitle || children ? '1px solid var(--sh-border-subtle)' : 'none',
    paddingBottom: subtitle || children ? 'var(--sh-space-4)' : 0,
  };

  const footerStyle: React.CSSProperties = {
    marginTop: 'var(--sh-space-5)',
    paddingTop: 'var(--sh-space-3)',
    borderTop: '1px solid var(--sh-border-subtle)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    flexWrap: 'wrap',
    gap: 'var(--sh-space-3)',
  };

  return (
    <div style={baseStyle} className={className}>
      {(title || headerAction) && (
        <div style={headerStyle}>
          <div>
            {title && (
              <h2 style={{ margin: 0, fontSize: '1.15rem' }}>{title}</h2>
            )}
            {subtitle && (
              <p style={{ margin: 'var(--sh-space-1) 0 0 0', fontSize: '0.85rem' }}>
                {subtitle}
              </p>
            )}
          </div>
          {headerAction && <div>{headerAction}</div>}
        </div>
      )}
      <div>{children}</div>
      {footer && <div style={footerStyle}>{footer}</div>}
    </div>
  );
};
