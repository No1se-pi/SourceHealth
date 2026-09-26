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
    boxShadow: 'none',
    padding: 'var(--sh-space-4)',
    transition: 'border-color var(--sh-transition), background-color var(--sh-transition)',
    ...style,
  };

  const hasHeader = title || headerAction || subtitle;

  const headerStyle: React.CSSProperties = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    flexWrap: 'wrap',
    gap: 'var(--sh-space-2)',
    marginBottom: children ? 'var(--sh-space-3)' : 0,
    borderBottom: children ? '1px solid var(--sh-border-subtle)' : 'none',
    paddingBottom: children ? 'var(--sh-space-3)' : 0,
  };

  const footerStyle: React.CSSProperties = {
    marginTop: 'var(--sh-space-4)',
    paddingTop: 'var(--sh-space-3)',
    borderTop: '1px solid var(--sh-border-subtle)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    flexWrap: 'wrap',
    gap: 'var(--sh-space-2)',
  };

  return (
    <div style={baseStyle} className={`sc-panel ${className}`.trim()}>
      {hasHeader && (
        <div style={headerStyle}>
          <div>
            {title && (
              <h3
                style={{
                  margin: 0,
                  fontSize: '1rem',
                  fontWeight: 600,
                  color: 'var(--sh-text-primary)',
                  letterSpacing: '-0.01em',
                }}
              >
                {title}
              </h3>
            )}
            {subtitle && (
              <div
                style={{
                  marginTop: '0.25rem',
                  fontSize: '0.8125rem',
                  color: 'var(--sh-text-muted)',
                  lineHeight: 1.4,
                }}
              >
                {subtitle}
              </div>
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
