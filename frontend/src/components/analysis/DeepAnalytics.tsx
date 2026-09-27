import type { AnalyzerResult } from '../../api/client';

type Props = { check?: AnalyzerResult };
type Ownership = { path_group: string; contributors: number; dominant_alias: string; dominant_share: number };

const flag = (value: unknown) => value === true ? 'Есть' : value === false ? 'Не найдено' : 'Нельзя определить';
const number = (value: unknown): number | null => typeof value === 'number' && Number.isFinite(value) ? value : null;

export function DeepAnalytics({ check }: Props) {
  if (!check) return null;
  const metrics = check.metrics ?? {};
  const busFactor = number(metrics.bus_factor_proxy);
  const topShare = number(metrics.top_contributor_share);
  const contributors = number(metrics.contributors_count);
  const commits = number(metrics.sampled_commits);
  const ownership = Array.isArray(metrics.ownership_groups)
    ? metrics.ownership_groups.filter((item): item is Ownership => Boolean(item) && typeof item === 'object'
      && typeof item.path_group === 'string' && typeof item.contributors === 'number'
      && typeof item.dominant_alias === 'string' && typeof item.dominant_share === 'number').slice(0, 20)
    : [];
  const rows: Array<[string, unknown]> = [
    ['SECURITY.md', metrics.security_policy_present], ['CODEOWNERS', metrics.codeowners_present],
    ['CONTRIBUTING', metrics.contributing_present], ['Политика веток', metrics.branch_policy_present],
    ['Политика review', metrics.review_policy_present], ['Автообновление зависимостей', metrics.dependency_update_automation],
    ['Политика лицензий', metrics.license_policy_present],
  ];
  const lockCoverage = number(metrics.lockfile_coverage);
  return (
    <section aria-labelledby="deep-analytics-title">
      <h3 id="deep-analytics-title" style={{ marginBottom: 'var(--sh-space-3)' }}>Углублённая аналитика</h3>
      <p style={{ color: 'var(--sh-text-secondary)', fontSize: '0.88rem' }}>
        Bus Factor — приближённая оценка концентрации изменений по Git, а не оценка знаний команды.
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 'var(--sh-space-3)' }}>
        {[
          ['Bus Factor proxy', busFactor ?? 'NO_DATA'],
          ['Доля ведущего участника', topShare === null ? 'NO_DATA' : `${(topShare * 100).toFixed(1)}%`],
          ['Участников наблюдается', contributors ?? 'NO_DATA'],
          ['Коммитов в выборке', commits ?? 'NO_DATA'],
        ].map(([label, value]) => <div key={label} style={{ padding: 'var(--sh-space-3)', border: '1px solid var(--sh-border-subtle)', borderRadius: 'var(--sh-radius-sm)' }}>
          <div style={{ color: 'var(--sh-text-muted)', fontSize: '0.78rem' }}>{label}</div><strong>{value}</strong>
        </div>)}
      </div>
      <p style={{ color: 'var(--sh-text-muted)', fontSize: '0.82rem' }}>
        История: {metrics.history_complete === true ? 'полная' : 'ограниченная выборка или NO_DATA'}.
      </p>
      <h4>Концентрация по областям</h4>
      {ownership.length ? <div style={{ overflowX: 'auto' }}><table style={{ width: '100%', fontSize: '0.84rem' }}>
        <thead><tr><th>Область</th><th>Участников</th><th>Доминирующий alias</th><th>Доля</th></tr></thead>
        <tbody>{ownership.map(item => <tr key={item.path_group}><td>{item.path_group}</td><td>{item.contributors}</td>
          <td>{item.dominant_alias}</td><td>{(item.dominant_share * 100).toFixed(1)}%</td></tr>)}</tbody>
      </table></div> : <p style={{ color: 'var(--sh-text-muted)' }}>NO_DATA — нельзя определить.</p>}
      <h4>Гигиена репозитория</h4>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '0.5rem' }}>
        {rows.map(([label, value]) => <div key={label}><strong>{label}:</strong> {flag(value)}</div>)}
        <div><strong>Lockfiles:</strong> {lockCoverage === null ? 'Нельзя определить' : `${(lockCoverage * 100).toFixed(0)}% экосистем`}</div>
      </div>
    </section>
  );
}
