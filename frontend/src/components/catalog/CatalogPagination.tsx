import React, { useState } from 'react';

interface CatalogPaginationProps {
  currentPage: number;
  totalPages: number;
  totalItems: number;
  pageSize: number;
  onPageChange: (newPage: number) => void;
  onPageSizeChange: (newPageSize: number) => void;
}

export const CatalogPagination: React.FC<CatalogPaginationProps> = ({
  currentPage,
  totalPages,
  totalItems,
  pageSize,
  onPageChange,
  onPageSizeChange,
}) => {
  const [jumpPage, setJumpPage] = useState('');

  if (totalItems === 0) return null;

  const startItem = Math.min(totalItems, (currentPage - 1) * pageSize + 1);
  const endItem = Math.min(totalItems, currentPage * pageSize);

  const handleJump = (e: React.FormEvent) => {
    e.preventDefault();
    const pageNum = parseInt(jumpPage, 10);
    if (!isNaN(pageNum) && pageNum >= 1 && pageNum <= totalPages) {
      onPageChange(pageNum);
      setJumpPage('');
    }
  };

  // Generate page numbers with ellipsis
  const getVisiblePages = () => {
    const delta = 2;
    const range: number[] = [];
    for (
      let i = Math.max(2, currentPage - delta);
      i <= Math.min(totalPages - 1, currentPage + delta);
      i++
    ) {
      range.push(i);
    }

    const pages: Array<number | string> = [1];
    if (range.length > 0 && range[0] > 2) {
      pages.push('...');
    }
    pages.push(...range);
    if (range.length > 0 && range[range.length - 1] < totalPages - 1) {
      pages.push('...');
    }
    if (totalPages > 1) {
      pages.push(totalPages);
    }
    return pages;
  };

  return (
    <div
      className="sh-catalog-pagination"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '16px',
        padding: '16px 0',
        marginTop: '16px',
        borderTop: '1px solid var(--sh-border-subtle, #e1e4e8)',
        fontSize: '0.8125rem',
        color: 'var(--sh-text-secondary, #475569)',
      }}
    >
      {/* Items range display */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span>
          Показано <strong>{startItem}</strong>–<strong>{endItem}</strong> из{' '}
          <strong>{totalItems.toLocaleString('ru-RU')}</strong>
        </span>

        {/* Page size dropdown */}
        <select
          value={pageSize}
          onChange={(e) => onPageSizeChange(Number(e.target.value))}
          style={{
            padding: '4px 8px',
            borderRadius: 'var(--sh-radius-sm, 6px)',
            border: '1px solid var(--sh-border-default, #d0d7de)',
            backgroundColor: 'var(--sh-bg-surface, #ffffff)',
            color: 'var(--sh-text-primary, #1f2328)',
            fontSize: '0.75rem',
            marginLeft: '8px',
          }}
        >
          <option value={20}>20 на странице</option>
          <option value={50}>50 на странице</option>
          <option value={100}>100 на странице</option>
        </select>
      </div>

      {/* Page navigation controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
        <button
          type="button"
          disabled={currentPage <= 1}
          onClick={() => onPageChange(1)}
          title="Первая страница"
          style={{
            padding: '6px 10px',
            borderRadius: 'var(--sh-radius-sm, 6px)',
            border: '1px solid var(--sh-border-default, #d0d7de)',
            background: 'var(--sh-bg-surface, #ffffff)',
            color: 'var(--sh-text-primary, #1f2328)',
            cursor: currentPage <= 1 ? 'not-allowed' : 'pointer',
            opacity: currentPage <= 1 ? 0.4 : 1,
          }}
        >
          «
        </button>

        <button
          type="button"
          disabled={currentPage <= 1}
          onClick={() => onPageChange(currentPage - 1)}
          title="Предыдущая страница"
          style={{
            padding: '6px 10px',
            borderRadius: 'var(--sh-radius-sm, 6px)',
            border: '1px solid var(--sh-border-default, #d0d7de)',
            background: 'var(--sh-bg-surface, #ffffff)',
            color: 'var(--sh-text-primary, #1f2328)',
            cursor: currentPage <= 1 ? 'not-allowed' : 'pointer',
            opacity: currentPage <= 1 ? 0.4 : 1,
          }}
        >
          ‹
        </button>

        {getVisiblePages().map((p, idx) => {
          if (p === '...') {
            return (
              <span key={`dots-${idx}`} style={{ padding: '0 4px', color: 'var(--sh-text-muted, #64748b)' }}>
                …
              </span>
            );
          }

          const pageNum = Number(p);
          const isCurrent = pageNum === currentPage;

          return (
            <button
              key={`page-${pageNum}`}
              type="button"
              onClick={() => onPageChange(pageNum)}
              style={{
                minWidth: '32px',
                height: '32px',
                padding: '0 8px',
                borderRadius: 'var(--sh-radius-sm, 6px)',
                border: '1px solid',
                borderColor: isCurrent
                  ? 'var(--sh-brand, #f93333)'
                  : 'var(--sh-border-default, #d0d7de)',
                backgroundColor: isCurrent
                  ? 'var(--sh-brand-subtle, rgba(249, 51, 51, 0.08))'
                  : 'var(--sh-bg-surface, #ffffff)',
                color: isCurrent
                  ? 'var(--sh-brand-text, #dc2626)'
                  : 'var(--sh-text-primary, #1f2328)',
                fontWeight: isCurrent ? 700 : 500,
                cursor: 'pointer',
              }}
            >
              {pageNum}
            </button>
          );
        })}

        <button
          type="button"
          disabled={currentPage >= totalPages}
          onClick={() => onPageChange(currentPage + 1)}
          title="Следующая страница"
          style={{
            padding: '6px 10px',
            borderRadius: 'var(--sh-radius-sm, 6px)',
            border: '1px solid var(--sh-border-default, #d0d7de)',
            background: 'var(--sh-bg-surface, #ffffff)',
            color: 'var(--sh-text-primary, #1f2328)',
            cursor: currentPage >= totalPages ? 'not-allowed' : 'pointer',
            opacity: currentPage >= totalPages ? 0.4 : 1,
          }}
        >
          ›
        </button>

        <button
          type="button"
          disabled={currentPage >= totalPages}
          onClick={() => onPageChange(totalPages)}
          title="Последняя страница"
          style={{
            padding: '6px 10px',
            borderRadius: 'var(--sh-radius-sm, 6px)',
            border: '1px solid var(--sh-border-default, #d0d7de)',
            background: 'var(--sh-bg-surface, #ffffff)',
            color: 'var(--sh-text-primary, #1f2328)',
            cursor: currentPage >= totalPages ? 'not-allowed' : 'pointer',
            opacity: currentPage >= totalPages ? 0.4 : 1,
          }}
        >
          »
        </button>
      </div>

      {/* Jump to page form */}
      <form onSubmit={handleJump} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span>Стр:</span>
        <input
          type="number"
          min={1}
          max={totalPages}
          value={jumpPage}
          onChange={(e) => setJumpPage(e.target.value)}
          placeholder={String(currentPage)}
          style={{
            width: '54px',
            padding: '4px 6px',
            borderRadius: 'var(--sh-radius-sm, 6px)',
            border: '1px solid var(--sh-border-default, #d0d7de)',
            backgroundColor: 'var(--sh-bg-surface, #ffffff)',
            color: 'var(--sh-text-primary, #1f2328)',
            fontSize: '0.75rem',
            textAlign: 'center',
          }}
        />
        <button
          type="submit"
          style={{
            padding: '4px 8px',
            borderRadius: 'var(--sh-radius-sm, 6px)',
            border: '1px solid var(--sh-border-default, #d0d7de)',
            background: 'var(--sh-bg-surface-elevated, #f1f3f5)',
            color: 'var(--sh-text-primary, #1f2328)',
            fontSize: '0.75rem',
            cursor: 'pointer',
          }}
        >
          Перейти
        </button>
      </form>
    </div>
  );
};
