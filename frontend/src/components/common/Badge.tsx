import React from 'react';

export type BadgeVariant = 'brand' | 'success' | 'warning' | 'danger' | 'neutral';

interface BadgeProps {
  variant?: BadgeVariant;
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}

export const Badge: React.FC<BadgeProps> = ({
  variant = 'neutral',
  children,
  className = '',
  style,
}) => {
  const variantStyles: Record<BadgeVariant, React.CSSProperties> = {
    brand: {
      backgroundColor: 'var(--sh-brand-subtle)',
      color: 'var(--sh-brand)',
      borderColor: 'var(--sh-brand-border)',
    },
    success: {
      backgroundColor: 'var(--sh-health-good-bg)',
      color: 'var(--sh-health-good)',
      borderColor: 'var(--sh-health-good-border)',
    },
    warning: {
      backgroundColor: 'var(--sh-health-warning-bg)',
      color: 'var(--sh-health-warning)',
      borderColor: 'var(--sh-health-warning-border)',
    },
    danger: {
      backgroundColor: 'var(--sh-health-danger-bg)',
      color: 'var(--sh-health-danger)',
      borderColor: 'var(--sh-health-danger-border)',
    },
    neutral: {
      backgroundColor: 'var(--sh-health-unavailable-bg)',
      color: 'var(--sh-text-secondary)',
      borderColor: 'var(--sh-health-unavailable-border)',
    },
  };

  const badgeStyle: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '0.35rem',
    fontSize: '0.78rem',
    fontWeight: 600,
    lineHeight: 1,
    padding: '0.25rem 0.6rem',
    borderRadius: 'var(--sh-radius-full)',
    border: '1px solid',
    whiteSpace: 'nowrap',
    ...variantStyles[variant],
    ...style,
  };

  return (
    <span style={badgeStyle} className={className}>
      {children}
    </span>
  );
};
