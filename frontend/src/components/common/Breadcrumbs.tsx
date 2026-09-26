import React from 'react';
import { Link } from 'react-router-dom';

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

export interface BreadcrumbsProps {
  items: BreadcrumbItem[];
  backLink?: {
    label: string;
    href: string;
  };
}

export const Breadcrumbs: React.FC<BreadcrumbsProps> = ({ items, backLink }) => {
  return (
    <nav className="sc-breadcrumbs-nav" aria-label="Хлебные крошки" style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
      <ol style={{ display: 'flex', alignItems: 'center', listStyle: 'none', margin: 0, padding: 0, gap: '0.4rem', fontSize: '0.85rem', color: 'var(--sh-text-secondary)' }}>
        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          return (
            <li key={index} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              {index > 0 && <span aria-hidden="true" style={{ opacity: 0.5 }}>/</span>}
              {item.href && !isLast ? (
                <Link
                  to={item.href}
                  className="sc-breadcrumb-link"
                  style={{ color: 'var(--sh-brand)', textDecoration: 'none', fontWeight: 500 }}
                >
                  {item.label}
                </Link>
              ) : (
                <span
                  style={{
                    color: isLast ? 'var(--sh-text-primary)' : 'inherit',
                    fontWeight: isLast ? 600 : 400,
                  }}
                  aria-current={isLast ? 'page' : undefined}
                >
                  {item.label}
                </span>
              )}
            </li>
          );
        })}
      </ol>

      {backLink && (
        <Link
          to={backLink.href}
          className="sc-back-link"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.35rem',
            fontSize: '0.82rem',
            color: 'var(--sh-text-secondary)',
            textDecoration: 'none',
            padding: '0.25rem 0.5rem',
            borderRadius: 'var(--sh-radius-sm)',
            border: '1px solid var(--sh-border-default)',
            backgroundColor: 'var(--sh-bg-surface-elevated)',
          }}
        >
          {backLink.label}
        </Link>
      )}
    </nav>
  );
};
