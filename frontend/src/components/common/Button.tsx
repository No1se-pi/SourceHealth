import React from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

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

  const sizeStyles: Record<ButtonSize, React.CSSProperties> = {
    sm: {
      padding: '0.35rem 0.65rem',
      fontSize: '0.85rem',
      borderRadius: 'var(--sh-radius-sm)',
    },
    md: {
      padding: '0.55rem 1rem',
      fontSize: '0.93rem',
      borderRadius: 'var(--sh-radius-sm)',
    },
    lg: {
      padding: '0.75rem 1.35rem',
      fontSize: '1rem',
      borderRadius: 'var(--sh-radius-md)',
    },
  };

  const variantStyles: Record<ButtonVariant, React.CSSProperties> = {
    primary: {
      backgroundColor: 'var(--sh-brand)',
      color: '#ffffff',
      border: '1px solid var(--sh-brand)',
    },
    secondary: {
      backgroundColor: 'var(--sh-bg-surface-elevated)',
      color: 'var(--sh-text-primary)',
      border: '1px solid var(--sh-border-default)',
    },
    outline: {
      backgroundColor: 'transparent',
      color: 'var(--sh-text-primary)',
      border: '1px solid var(--sh-border-default)',
    },
    ghost: {
      backgroundColor: 'transparent',
      color: 'var(--sh-text-secondary)',
      border: '1px solid transparent',
    },
    danger: {
      backgroundColor: 'var(--sh-health-danger-bg)',
      color: 'var(--sh-health-danger)',
      border: '1px solid var(--sh-health-danger-border)',
    },
  };

  const combinedStyle: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '0.5rem',
    fontWeight: 500,
    cursor: isDisabled ? 'not-allowed' : 'pointer',
    opacity: isDisabled ? 0.6 : 1,
    transition: 'background var(--sh-transition), border-color var(--sh-transition), opacity var(--sh-transition)',
    ...sizeStyles[size],
    ...variantStyles[variant],
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
