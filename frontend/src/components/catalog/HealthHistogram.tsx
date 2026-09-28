import React from 'react';
import type { HealthHistogramBucket } from '../../api/client';

interface HealthHistogramProps {
  buckets?: HealthHistogramBucket[];
  noDataCount?: number;
  totalAnalyzed?: number;
  selectedRange?: { min?: number; max?: number } | null;
  selectedNoData?: boolean;
  onSelectBucket: (min?: number, max?: number, isNoData?: boolean) => void;
}

export const HealthHistogram: React.FC<HealthHistogramProps> = ({
  buckets = [],
  noDataCount = 0,
  totalAnalyzed = 0,
  selectedRange,
  selectedNoData = false,
  onSelectBucket,
}) => {
  // Numeric buckets only for scaling, preventing NO_DATA from flattening score bars
  const maxBucketCount = Math.max(1, ...buckets.map((b) => b.count));

  return (
    <div
      className="sh-histogram-card"
      style={{
        background: 'var(--sh-bg-surface, #ffffff)',
        border: '1px solid var(--sh-border-default, #d0d7de)',
        borderRadius: 'var(--sh-radius-md, 8px)',
        padding: '16px 20px',
        marginBottom: '20px',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          marginBottom: '12px',
        }}
      >
        <span
          style={{
            fontSize: '0.875rem',
            fontWeight: 600,
            color: 'var(--sh-text-primary, #1f2328)',
          }}
        >
          Распределение Health (0–100)
        </span>
        <span
          style={{
            fontSize: '0.75rem',
            color: 'var(--sh-text-muted, #64748b)',
          }}
        >
          Нажмите на столбец диапазона для фильтрации
        </span>
      </div>

      {/* 10 Numeric Score Buckets */}
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          gap: '8px',
          height: '80px',
          paddingBottom: '4px',
        }}
      >
        {buckets.map((b, idx) => {
          const isSelected =
            !selectedNoData &&
            selectedRange?.min === b.min_score &&
            selectedRange?.max === b.max_score;
          const heightPercent = maxBucketCount > 0 ? (b.count / maxBucketCount) * 100 : 0;
          const percentOfAnalyzed =
            totalAnalyzed > 0 ? ((b.count / totalAnalyzed) * 100).toFixed(1) : '0';

          // Color based on score range
          let barColor = 'var(--sh-health-good, #1a7f37)';
          if (b.min_score < 50) {
            barColor = 'var(--sh-health-danger, #cf222e)';
          } else if (b.min_score < 80) {
            barColor = 'var(--sh-health-warning, #9a6700)';
          }

          return (
            <div
              key={b.range_label}
              className="sh-histogram-bar"
              data-testid={`histogram-bucket-${idx}`}
              onClick={() => onSelectBucket(b.min_score, b.max_score, false)}
              style={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'flex-end',
                alignItems: 'center',
                height: '100%',
                cursor: 'pointer',
                opacity: selectedRange && !isSelected ? 0.35 : 1,
                transition: 'opacity 0.15s ease',
              }}
              title={`${b.range_label}: ${b.count} проектов (${percentOfAnalyzed}% от оценённых)`}
            >
              <div
                style={{
                  width: '100%',
                  height: `${Math.max(4, heightPercent)}%`,
                  backgroundColor: barColor,
                  borderRadius: '3px 3px 0 0',
                  border: isSelected ? '2px solid var(--sh-text-primary, #1f2328)' : 'none',
                  transition: 'height 0.25s ease',
                }}
              />
              <span
                style={{
                  fontSize: '9px',
                  color: isSelected ? 'var(--sh-text-primary, #1f2328)' : 'var(--sh-text-muted, #64748b)',
                  fontWeight: isSelected ? 700 : 400,
                  marginTop: '4px',
                  whiteSpace: 'nowrap',
                }}
              >
                {idx === 0 ? '0' : idx === 9 ? '90+' : `${idx * 10}`}
              </span>
            </div>
          );
        })}
      </div>

      {/* Discrete Metadata Line: Evaluated vs NO_DATA */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginTop: '12px',
          paddingTop: '8px',
          borderTop: '1px solid var(--sh-border-subtle, #f0f2f5)',
          fontSize: '0.8rem',
        }}
      >
        <span style={{ color: 'var(--sh-text-muted, #64748b)' }}>
          С официальной оценкой: <strong style={{ color: 'var(--sh-text-primary, #1f2328)' }}>{totalAnalyzed}</strong>
        </span>

        {noDataCount > 0 && (
          <button
            type="button"
            className="sh-histogram-bar-nodata"
            data-testid="histogram-bucket-nodata"
            onClick={() => onSelectBucket(undefined, undefined, true)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '3px 10px',
              borderRadius: 'var(--sh-radius-sm, 6px)',
              cursor: 'pointer',
              fontSize: '0.78rem',
              fontWeight: selectedNoData ? 600 : 500,
              border: '1px solid',
              borderColor: selectedNoData ? 'var(--sh-text-primary, #1f2328)' : 'var(--sh-border-default, #d0d7de)',
              backgroundColor: selectedNoData ? 'var(--sh-bg-surface-hover, #f3f4f6)' : 'transparent',
              color: selectedNoData ? 'var(--sh-text-primary, #1f2328)' : 'var(--sh-text-muted, #64748b)',
              transition: 'all 0.15s ease',
            }}
            title="Показать репозитории без рассчитанной оценки Health"
          >
            <span>Без рассчитанного Health:</span>
            <strong>{noDataCount.toLocaleString('ru-RU')}</strong>
            {selectedNoData && <span style={{ color: 'var(--sh-brand, #f93333)' }}>●</span>}
          </button>
        )}
      </div>
    </div>
  );
};
