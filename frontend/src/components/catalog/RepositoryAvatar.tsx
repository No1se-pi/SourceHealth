import React, { useState } from 'react';

interface RepositoryAvatarProps {
  name: string;
  logoUrl?: string | null;
  size?: number;
  className?: string;
}

const PALETTE = [
  '#2563eb', '#7c3aed', '#db2777', '#ea580c',
  '#16a34a', '#0891b2', '#4f46e5', '#d97706',
];

function getInitials(name: string): string {
  const parts = name.split(/[-_/.]+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

function getColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  const index = Math.abs(hash) % PALETTE.length;
  return PALETTE[index];
}

export const RepositoryAvatar: React.FC<RepositoryAvatarProps> = ({
  name,
  logoUrl,
  size = 36,
  className = '',
}) => {
  const [loadFailed, setLoadFailed] = useState(false);
  const initials = getInitials(name);
  const bgColor = getColor(name);

  if (logoUrl && !loadFailed) {
    return (
      <img
        src={logoUrl}
        alt={name}
        width={size}
        height={size}
        onError={() => setLoadFailed(true)}
        className={`sh-avatar ${className}`}
        style={{
          width: size,
          height: size,
          borderRadius: 'var(--sh-radius-sm, 6px)',
          objectFit: 'cover',
          backgroundColor: 'var(--sh-bg-surface-elevated, #f1f3f5)',
          border: '1px solid var(--sh-border-subtle, #e1e4e8)',
          flexShrink: 0,
        }}
        loading="lazy"
      />
    );
  }

  return (
    <div
      className={`sh-avatar-fallback ${className}`}
      style={{
        width: size,
        height: size,
        borderRadius: 'var(--sh-radius-sm, 6px)',
        backgroundColor: bgColor,
        color: '#ffffff',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontWeight: 600,
        fontSize: Math.max(11, Math.floor(size * 0.4)),
        letterSpacing: '0.04em',
        flexShrink: 0,
        userSelect: 'none',
      }}
      title={name}
      aria-hidden="true"
    >
      {initials}
    </div>
  );
};
