import React from 'react';
import type { components } from '../../api/generated';

type ShareInfo = components['schemas']['ShareInfo'];

export const ShareResult: React.FC<{ share: ShareInfo }> = ({ share }) => (
  <section aria-labelledby="share-result-title">
    <h2 id="share-result-title">Поделиться результатом</h2>
    <p><a href={share.repository_url}>Публичная страница репозитория</a></p>
    <p><a href={share.badge_url}>Health badge</a></p>
    <pre><code>{share.badge_markdown}</code></pre>
    {share.markdown_report_url && <p><a href={share.markdown_report_url}>Markdown-отчёт</a></p>}
  </section>
);
