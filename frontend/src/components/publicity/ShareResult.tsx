import React, { useState } from 'react';
import type { components } from '../../api/generated';
import { Card } from '../common/Card';
import { CopyButton } from '../common/CopyButton';
import { Button } from '../common/Button';

type ShareInfo = components['schemas']['ShareInfo'];

export const ShareResult: React.FC<{ share: ShareInfo }> = ({ share }) => {
  const [badgeError, setBadgeError] = useState(false);
  const canNativeShare = typeof navigator !== 'undefined' && Boolean(navigator.share);

  const handleNativeShare = async () => {
    if (canNativeShare) {
      try {
        await navigator.share({
          title: `${share.organization_slug}/${share.repository_slug} — SourceHealth`,
          text: `Официальная оценка Health проекта ${share.organization_slug}/${share.repository_slug}`,
          url: share.repository_url,
        });
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          // fallback to clipboard handled by CopyButton
        }
      }
    }
  };

  return (
    <Card
      title="Поделиться результатом"
      subtitle="Публичные ссылки, значок Health для README и экспорт отчёта"
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-4)' }}>
        {/* Native share row */}
        {canNativeShare && (
          <div>
            <Button
              variant="brand"
              size="sm"
              onClick={handleNativeShare}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
            >
              <span>↗</span>
              <span>Поделиться через систему</span>
            </Button>
          </div>
        )}

        {/* Links Grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: 'var(--sh-space-3)',
          }}
        >
          {/* Public Repo URL */}
          <div
            style={{
              padding: 'var(--sh-space-3)',
              backgroundColor: 'var(--sh-bg-base)',
              borderRadius: 'var(--sh-radius-sm)',
              border: '1px solid var(--sh-border-subtle)',
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--sh-space-2)',
            }}
          >
            <span style={{ fontSize: '0.8rem', color: 'var(--sh-text-muted)', fontWeight: 600 }}>
              Публичная страница репозитория
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <input
                type="text"
                readOnly
                value={share.repository_url}
                aria-label="Публичная ссылка на репозиторий"
                style={{
                  flex: 1,
                  fontSize: '0.82rem',
                  fontFamily: 'var(--sh-font-mono)',
                  padding: '0.25rem 0.5rem',
                  borderRadius: 'var(--sh-radius-sm)',
                  border: '1px solid var(--sh-border-default)',
                  backgroundColor: 'var(--sh-bg-surface)',
                  color: 'var(--sh-text-primary)',
                }}
              />
              <CopyButton value={share.repository_url} label="Копировать" size="sm" />
            </div>
          </div>

          {/* Latest Analysis URL */}
          {share.latest_analysis_url && (
            <div
              style={{
                padding: 'var(--sh-space-3)',
                backgroundColor: 'var(--sh-bg-base)',
                borderRadius: 'var(--sh-radius-sm)',
                border: '1px solid var(--sh-border-subtle)',
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--sh-space-2)',
              }}
            >
              <span style={{ fontSize: '0.8rem', color: 'var(--sh-text-muted)', fontWeight: 600 }}>
                Последний анализ
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <input
                  type="text"
                  readOnly
                  value={share.latest_analysis_url}
                  aria-label="Ссылка на последний анализ"
                  style={{
                    flex: 1,
                    fontSize: '0.82rem',
                    fontFamily: 'var(--sh-font-mono)',
                    padding: '0.25rem 0.5rem',
                    borderRadius: 'var(--sh-radius-sm)',
                    border: '1px solid var(--sh-border-default)',
                    backgroundColor: 'var(--sh-bg-surface)',
                    color: 'var(--sh-text-primary)',
                  }}
                />
                <CopyButton value={share.latest_analysis_url} label="Копировать" size="sm" />
              </div>
            </div>
          )}

          {/* Markdown Report Link */}
          {share.markdown_report_url && (
            <div
              style={{
                padding: 'var(--sh-space-3)',
                backgroundColor: 'var(--sh-bg-base)',
                borderRadius: 'var(--sh-radius-sm)',
                border: '1px solid var(--sh-border-subtle)',
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--sh-space-2)',
              }}
            >
              <span style={{ fontSize: '0.8rem', color: 'var(--sh-text-muted)', fontWeight: 600 }}>
                Markdown-отчёт (API)
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <input
                  type="text"
                  readOnly
                  value={share.markdown_report_url}
                  aria-label="Ссылка на Markdown отчёт"
                  style={{
                    flex: 1,
                    fontSize: '0.82rem',
                    fontFamily: 'var(--sh-font-mono)',
                    padding: '0.25rem 0.5rem',
                    borderRadius: 'var(--sh-radius-sm)',
                    border: '1px solid var(--sh-border-default)',
                    backgroundColor: 'var(--sh-bg-surface)',
                    color: 'var(--sh-text-primary)',
                  }}
                />
                <CopyButton value={share.markdown_report_url} label="Копировать" size="sm" />
              </div>
            </div>
          )}
        </div>

        {/* Badge Section */}
        <div
          style={{
            padding: 'var(--sh-space-4)',
            backgroundColor: 'var(--sh-bg-base)',
            borderRadius: 'var(--sh-radius-sm)',
            border: '1px solid var(--sh-border-subtle)',
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--sh-space-3)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>
              Значок Health (Badge)
            </span>
            <span style={{ fontSize: '0.78rem', color: 'var(--sh-text-muted)' }}>
              Отображает только официальный Health (без предварительных оценок)
            </span>
          </div>

          {/* Badge Preview */}
          <div
            style={{
              padding: 'var(--sh-space-3)',
              backgroundColor: 'var(--sh-bg-surface)',
              borderRadius: 'var(--sh-radius-sm)',
              border: '1px solid var(--sh-border-subtle)',
              display: 'flex',
              alignItems: 'center',
              gap: '1rem',
            }}
          >
            {!badgeError ? (
              <img
                src={share.badge_url}
                alt="SourceHealth badge"
                onError={() => setBadgeError(true)}
                style={{ verticalAlign: 'middle', height: '20px' }}
              />
            ) : (
              <span style={{ fontSize: '0.8rem', color: 'var(--sh-health-danger, #ef4444)' }}>
                Не удалось загрузить предпросмотр бейджа
              </span>
            )}
            <a
              href={share.badge_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ fontSize: '0.8rem', color: 'var(--sh-brand)' }}
            >
              Открыть SVG ↗
            </a>
          </div>

          {/* Badge Code Formats */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-2)' }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.2rem' }}>
                <span style={{ fontSize: '0.78rem', color: 'var(--sh-text-muted)', fontWeight: 600 }}>
                  Markdown
                </span>
                <CopyButton value={share.badge_markdown} label="Скопировать Markdown" size="sm" />
              </div>
              <pre
                style={{
                  margin: 0,
                  padding: '0.4rem 0.6rem',
                  fontSize: '0.8rem',
                  backgroundColor: 'var(--sh-bg-surface)',
                  border: '1px solid var(--sh-border-default)',
                  borderRadius: 'var(--sh-radius-sm)',
                  overflowX: 'auto',
                }}
              >
                <code>{share.badge_markdown}</code>
              </pre>
            </div>

            {share.badge_html && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.2rem' }}>
                  <span style={{ fontSize: '0.78rem', color: 'var(--sh-text-muted)', fontWeight: 600 }}>
                    HTML
                  </span>
                  <CopyButton value={share.badge_html} label="Скопировать HTML" size="sm" />
                </div>
                <pre
                  style={{
                    margin: 0,
                    padding: '0.4rem 0.6rem',
                    fontSize: '0.8rem',
                    backgroundColor: 'var(--sh-bg-surface)',
                    border: '1px solid var(--sh-border-default)',
                    borderRadius: 'var(--sh-radius-sm)',
                    overflowX: 'auto',
                  }}
                >
                  <code>{share.badge_html}</code>
                </pre>
              </div>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
};
