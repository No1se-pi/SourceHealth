export interface PresentationCheck {
  category?: string | null;
  source: string;
  availability: string;
  metrics: Record<string, unknown>;
  findings: Array<Record<string, unknown>>;
}

export function hasDetectedCiConfiguration(
  checks: Record<string, PresentationCheck> | undefined,
  score: number | null | undefined,
): boolean {
  if (score != null) return false;
  return Object.values(checks ?? {}).some((check) => (
    check.category === 'cicd'
    && check.availability === 'source_unavailable'
    && check.metrics.configured === true
  ));
}

export interface LocalSastStatus {
  state: 'available' | 'partial';
  findings: number;
  label: string;
}

export function localSastStatus(
  checks: Record<string, PresentationCheck> | undefined,
): LocalSastStatus | null {
  const check = Object.values(checks ?? {}).find((item) => (
    item.category === 'code_health'
    && item.source === 'sourcehealth_local'
    && (item.availability === 'available' || item.availability === 'partial')
  ));
  if (!check) return null;
  const findings = check.findings.length;
  const state = check.availability as LocalSastStatus['state'];
  const result = findings === 0 ? 'находок нет'
    : state === 'partial' ? `${findings} подтверждённых находок`
      : `${findings} ${findings === 1 ? 'находка' : findings < 5 ? 'находки' : 'находок'}`;
  return { state, findings, label: `Local SAST · ${state === 'partial' ? 'частично' : 'выполнен'} · ${result}` };
}
