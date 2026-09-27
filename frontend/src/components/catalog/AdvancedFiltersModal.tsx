import React from 'react';
import type { ActiveFiltersState } from './ActiveFilterChips';

interface AdvancedFiltersModalProps {
  isOpen: boolean;
  filters: ActiveFiltersState;
  onClose: () => void;
  onApply: (updated: Partial<ActiveFiltersState>) => void;
  onReset: () => void;
}

const CATEGORIES_CONFIG = [
  { id: 'security', name: 'Безопасность (официальный AppSec)' },
  { id: 'cicd', name: 'CI/CD' },
  { id: 'activity', name: 'Активность разработки' },
  { id: 'documentation', name: 'Документация' },
  { id: 'issues', name: 'Задачи и дефекты (Issues)' },
  { id: 'code_health', name: 'Качество кода (Code Health)' },
] as const;

export const AdvancedFiltersModal: React.FC<AdvancedFiltersModalProps> = ({
  isOpen,
  filters,
  onClose,
  onApply,
  onReset,
}) => {
  const [local, setLocal] = React.useState<ActiveFiltersState>(filters);

  React.useEffect(() => {
    setLocal(filters);
  }, [filters, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onApply(local);
    onClose();
  };

  return (
    <div
      className="sh-modal-backdrop"
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.45)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: '16px',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="sh-modal-content"
        style={{
          backgroundColor: 'var(--sh-bg-surface, #ffffff)',
          border: '1px solid var(--sh-border-default, #d0d7de)',
          borderRadius: 'var(--sh-radius-lg, 12px)',
          width: '100%',
          maxWidth: '580px',
          maxHeight: '90vh',
          overflowY: 'auto',
          boxShadow: 'var(--sh-shadow-lg, 0 10px 25px rgba(0,0,0,0.15))',
          padding: '24px',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '20px',
            borderBottom: '1px solid var(--sh-border-subtle, #e1e4e8)',
            paddingBottom: '12px',
          }}
        >
          <h2 style={{ margin: 0, fontSize: '1.15rem' }}>Расширенные фильтры</h2>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '18px',
              cursor: 'pointer',
              color: 'var(--sh-text-muted, #64748b)',
            }}
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '16px' }}>
          {/* Health Status */}
          <div>
            <label style={{ display: 'block', fontWeight: 600, fontSize: '0.8125rem', marginBottom: '6px' }}>
              Статус Health
            </label>
            <select
              value={local.health_status ?? ''}
              onChange={(e) => setLocal({ ...local, health_status: e.target.value || undefined })}
              style={{
                width: '100%',
                padding: '8px',
                borderRadius: 'var(--sh-radius-sm, 6px)',
                border: '1px solid var(--sh-border-default, #d0d7de)',
                backgroundColor: 'var(--sh-bg-surface, #ffffff)',
                color: 'var(--sh-text-primary, #1f2328)',
              }}
            >
              <option value="">Все проекты</option>
              <option value="available">Только с рассчитанным Health</option>
              <option value="no_data">Только NO_DATA (без оценки)</option>
            </select>
          </div>

          {/* Health Score Range */}
          <div>
            <label style={{ display: 'block', fontWeight: 600, fontSize: '0.8125rem', marginBottom: '6px' }}>
              Диапазон Health (0 – 100)
            </label>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <input
                type="number"
                min="0"
                max="100"
                placeholder="Мин"
                value={local.health_min ?? ''}
                onChange={(e) =>
                  setLocal({
                    ...local,
                    health_min: e.target.value !== '' ? Number(e.target.value) : undefined,
                  })
                }
                style={{
                  flex: 1,
                  padding: '8px',
                  borderRadius: 'var(--sh-radius-sm, 6px)',
                  border: '1px solid var(--sh-border-default, #d0d7de)',
                }}
              />
              <span>—</span>
              <input
                type="number"
                min="0"
                max="100"
                placeholder="Макс"
                value={local.health_max ?? ''}
                onChange={(e) =>
                  setLocal({
                    ...local,
                    health_max: e.target.value !== '' ? Number(e.target.value) : undefined,
                  })
                }
                style={{
                  flex: 1,
                  padding: '8px',
                  borderRadius: 'var(--sh-radius-sm, 6px)',
                  border: '1px solid var(--sh-border-default, #d0d7de)',
                }}
              />
            </div>
          </div>

          {/* Health Data Coverage Minimum */}
          <div>
            <label style={{ display: 'block', fontWeight: 600, fontSize: '0.8125rem', marginBottom: '6px' }}>
              Минимальный охват данных для Health (%)
            </label>
            <input
              type="number"
              min="0"
              max="100"
              placeholder="Например, 50"
              value={local.coverage_min ?? ''}
              onChange={(e) =>
                setLocal({
                  ...local,
                  coverage_min: e.target.value !== '' ? Number(e.target.value) : undefined,
                })
              }
              style={{
                width: '100%',
                padding: '8px',
                borderRadius: 'var(--sh-radius-sm, 6px)',
                border: '1px solid var(--sh-border-default, #d0d7de)',
              }}
            />
          </div>

          {/* All Six Category Filters */}
          <div style={{ borderTop: '1px solid var(--sh-border-subtle, #e1e4e8)', paddingTop: '12px' }}>
            <h3 style={{ margin: '0 0 12px 0', fontSize: '0.9375rem', fontWeight: 600 }}>
              Фильтры по категориям
            </h3>
            <div style={{ display: 'grid', gap: '14px' }}>
              {CATEGORIES_CONFIG.map(({ id, name }) => {
                const statusKey = `${id}_status` as keyof ActiveFiltersState;
                const minKey = `${id}_min` as keyof ActiveFiltersState;
                const maxKey = `${id}_max` as keyof ActiveFiltersState;

                return (
                  <div key={id} style={{ display: 'grid', gap: '4px' }}>
                    <label style={{ fontWeight: 500, fontSize: '0.8125rem' }}>{name}</label>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      <select
                        value={(local[statusKey] as string) ?? ''}
                        onChange={(e) =>
                          setLocal({
                            ...local,
                            [statusKey]: e.target.value || undefined,
                          })
                        }
                        style={{
                          width: '140px',
                          padding: '6px 8px',
                          borderRadius: 'var(--sh-radius-sm, 6px)',
                          border: '1px solid var(--sh-border-default, #d0d7de)',
                          fontSize: '0.8125rem',
                        }}
                      >
                        <option value="">Любой</option>
                        <option value="available">Есть оценка</option>
                        <option value="no_data">NO_DATA</option>
                      </select>
                      <input
                        type="number"
                        min="0"
                        max="100"
                        placeholder="Мин"
                        value={(local[minKey] as number) ?? ''}
                        onChange={(e) =>
                          setLocal({
                            ...local,
                            [minKey]: e.target.value !== '' ? Number(e.target.value) : undefined,
                          })
                        }
                        style={{
                          flex: 1,
                          padding: '6px 8px',
                          borderRadius: 'var(--sh-radius-sm, 6px)',
                          border: '1px solid var(--sh-border-default, #d0d7de)',
                          fontSize: '0.8125rem',
                        }}
                      />
                      <span>—</span>
                      <input
                        type="number"
                        min="0"
                        max="100"
                        placeholder="Макс"
                        value={(local[maxKey] as number) ?? ''}
                        onChange={(e) =>
                          setLocal({
                            ...local,
                            [maxKey]: e.target.value !== '' ? Number(e.target.value) : undefined,
                          })
                        }
                        style={{
                          flex: 1,
                          padding: '6px 8px',
                          borderRadius: 'var(--sh-radius-sm, 6px)',
                          border: '1px solid var(--sh-border-default, #d0d7de)',
                          fontSize: '0.8125rem',
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Origin */}
          <div style={{ borderTop: '1px solid var(--sh-border-subtle, #e1e4e8)', paddingTop: '12px' }}>
            <label style={{ display: 'block', fontWeight: 600, fontSize: '0.8125rem', marginBottom: '6px' }}>
              Происхождение проекта (Origin)
            </label>
            <select
              value={local.origin ?? ''}
              onChange={(e) => setLocal({ ...local, origin: e.target.value || undefined })}
              style={{
                width: '100%',
                padding: '8px',
                borderRadius: 'var(--sh-radius-sm, 6px)',
                border: '1px solid var(--sh-border-default, #d0d7de)',
                backgroundColor: 'var(--sh-bg-surface, #ffffff)',
                color: 'var(--sh-text-primary, #1f2328)',
              }}
            >
              <option value="">Все источники</option>
              <option value="native">Native SourceCraft</option>
              <option value="fork">Fork</option>
              <option value="migrated">Migrated</option>
              <option value="unknown">Unknown</option>
            </select>
          </div>

          {/* Activity Days */}
          <div>
            <label style={{ display: 'block', fontWeight: 600, fontSize: '0.8125rem', marginBottom: '6px' }}>
              Свежесть активности
            </label>
            <select
              value={local.activity_days ?? ''}
              onChange={(e) =>
                setLocal({
                  ...local,
                  activity_days: e.target.value !== '' ? Number(e.target.value) : undefined,
                })
              }
              style={{
                width: '100%',
                padding: '8px',
                borderRadius: 'var(--sh-radius-sm, 6px)',
                border: '1px solid var(--sh-border-default, #d0d7de)',
              }}
            >
              <option value="">За всё время</option>
              <option value="30">Активность за последние 30 дней</option>
              <option value="90">Активность за последние 90 дней</option>
              <option value="180">Активность за последние 180 дней</option>
              <option value="365">Активность за последний год</option>
            </select>
          </div>

          {/* Actions */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginTop: '12px',
              paddingTop: '16px',
              borderTop: '1px solid var(--sh-border-subtle, #e1e4e8)',
            }}
          >
            <button
              type="button"
              onClick={() => {
                onReset();
                onClose();
              }}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--sh-text-muted, #64748b)',
                cursor: 'pointer',
                fontSize: '0.875rem',
              }}
            >
              Сбросить
            </button>

            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                type="button"
                onClick={onClose}
                style={{
                  padding: '8px 16px',
                  borderRadius: 'var(--sh-radius-sm, 6px)',
                  border: '1px solid var(--sh-border-default, #d0d7de)',
                  background: 'var(--sh-bg-surface, #ffffff)',
                  cursor: 'pointer',
                }}
              >
                Отмена
              </button>
              <button
                type="submit"
                style={{
                  padding: '8px 16px',
                  borderRadius: 'var(--sh-radius-sm, 6px)',
                  border: '1px solid var(--sh-btn-primary-border, #1f2328)',
                  background: 'var(--sh-btn-primary-bg, #1f2328)',
                  color: 'var(--sh-btn-primary-text, #ffffff)',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Применить
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};
