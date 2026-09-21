import React from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

export function getButtonStyles(
  variant: ButtonVariant = 'secondary',
  size: ButtonSize = 'md',
  extraStyle?: React.CSSProperties,
): React.CSSProperties {
  const sizeStyles: Record<ButtonSize, React.CSSProperties> = {
    sm: {
      padding: '0.3rem 0.65rem',
      fontSize: '0.82rem',
      borderRadius: 'var(--sh-radius-sm)',
    },
    md: {
      padding: '0.45rem 0.95rem',
      fontSize: '0.88rem',
      borderRadius: 'var(--sh-radius-sm)',
    },
    lg: {
      padding: '0.65rem 1.25rem',
      fontSize: '0.95rem',
      borderRadius: 'var(--sh-radius-md)',
    },
  };

  const variantStyles: Record<ButtonVariant, React.CSSProperties> = {
    primary: {
      backgroundColor: 'var(--sh-brand)',
      color: '#ffffff',
      border: '1px solid var(--sh-brand)',
      fontWeight: 600,
    },
    secondary: {
      backgroundColor: 'var(--sh-bg-surface-elevated)',
      color: 'var(--sh-text-primary)',
      border: '1px solid var(--sh-border-default)',
      fontWeight: 500,
    },
    outline: {
      backgroundColor: 'transparent',
      color: 'var(--sh-text-primary)',
      border: '1px solid var(--sh-border-default)',
      fontWeight: 500,
    },
    ghost: {
      backgroundColor: 'transparent',
      color: 'var(--sh-text-secondary)',
      border: '1px solid transparent',
      fontWeight: 500,
    },
    danger: {
      backgroundColor: 'var(--sh-health-danger-bg)',
      color: 'var(--sh-health-danger)',
      border: '1px solid var(--sh-health-danger-border)',
      fontWeight: 600,
    },
  };

  return {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '0.5rem',
    textDecoration: 'none',
    cursor: 'pointer',
    lineHeight: 1.3,
    transition: 'background var(--sh-transition), border-color var(--sh-transition), opacity var(--sh-transition), transform var(--sh-transition)',
    ...sizeStyles[size],
    ...variantStyles[variant],
    ...extraStyle,
  };
}

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  children: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'secondary',
  size = 'md',
  loading = false,
  disabled = false,
  children,
  style,
  className = '',
  ...rest
}) => {
  const isDisabled = disabled || loading;

  const combinedStyle: React.CSSProperties = {
    ...getButtonStyles(variant, size),
    cursor: isDisabled ? 'not-allowed' : 'pointer',
    opacity: isDisabled ? 0.6 : 1,
    ...style,
  };

  return (
    <button
      disabled={isDisabled}
      style={combinedStyle}
      className={className}
      {...rest}
    >
      {loading && (
        <span
          className="animate-spin"
          style={{
            display: 'inline-block',
            width: '0.85em',
            height: '0.85em',
            border: '2px solid currentColor',
            borderRightColor: 'transparent',
            borderRadius: '50%',
          }}
          aria-hidden="true"
        />
      )}
      {children}
    </button>
  );
};
