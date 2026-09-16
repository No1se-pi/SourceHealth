import type { Category, RunStatus, AnalyzerResult, Evidence } from '../api/client';
import type { BadgeVariant } from '../components/common/Badge';

export const CATEGORY_ORDER: Category[] = [
  'documentation',
  'cicd',
  'security',
  'activity',
  'issues',
  'code_health',
];

export const CATEGORY_LABELS: Record<Category, string> = {
  documentation: 'Документация',
  cicd: 'CI/CD',
  security: 'Безопасность',
  activity: 'Активность',
  issues: 'Issues',
  code_health: 'Состояние кода',
};

export const STATUS_CONFIG: Record<RunStatus, { label: string; variant: BadgeVariant; inProgress: boolean }> = {
  queued: { label: 'В очереди', variant: 'brand', inProgress: true },
  collecting: { label: 'Сбор данных', variant: 'brand', inProgress: true },
  analyzing: { label: 'Анализ репозитория', variant: 'brand', inProgress: true },
  scoring: { label: 'Подготовка оценки', variant: 'brand', inProgress: true },
  completed: { label: 'Завершён', variant: 'success', inProgress: false },
  partial: { label: 'Завершён с неполными данными', variant: 'warning', inProgress: false },
  failed: { label: 'Не удалось завершить', variant: 'danger', inProgress: false },
};

export function getPriorityMeta(priority: number): { label: string; variant: BadgeVariant } {
  switch (priority) {
    case 1:
      return { label: 'P1 · Высокий', variant: 'danger' };
    case 2:
      return { label: 'P2 · Средний', variant: 'warning' };
    case 3:
      return { label: 'P3 · Низкий', variant: 'brand' };
    default:
      return { label: `P${priority}`, variant: 'neutral' };
  }
}

export function resolveEvidence(
  refs: string[],
  checks?: Record<string, AnalyzerResult>,
): Evidence[] {
  if (!checks || !refs || refs.length === 0) return [];
  const map = new Map<string, Evidence>();

  for (const check of Object.values(checks)) {
    if (Array.isArray(check.evidence)) {
      for (const item of check.evidence) {
        map.set(item.id, item);
      }
    }
  }

  return refs.map((ref) => map.get(ref)).filter((ev): ev is Evidence => Boolean(ev));
}
