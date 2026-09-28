import React, { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { CopyButton } from '../components/common/CopyButton';
import { getButtonStyles } from '../components/common/Button';
import { usePageTitle } from '../utils/usePageTitle';

export const CATEGORY_WEIGHTS: Record<string, number> = {
  documentation: 15,
  cicd: 15,
  security: 20,
  activity: 15,
  issues: 15,
  code_health: 20,
};

export const CATEGORY_LABELS: Record<string, string> = {
  documentation: 'Documentation',
  cicd: 'CI/CD',
  security: 'Security',
  activity: 'Activity',
  issues: 'Issues',
  code_health: 'Code Health',
};

export const CATEGORY_ORDER = [
  'documentation',
  'cicd',
  'security',
  'activity',
  'issues',
  'code_health',
];

const CATEGORY_DESCRIPTIONS: Record<string, string> = {
  documentation: 'README, установка, запуск, сборка, тесты, лицензия и быстрый старт.',
  cicd: 'Конфигурация CI/CD пайплайнов и процент успешных сборок (≥80%).',
  security: 'Дефекты официального SourceCraft AppSec по критичности через PAT.',
  activity: 'Коммиты за 30 дней, регулярность, давность последнего коммита и релизы.',
  issues: 'Доля закрытых задач, время реакции и отсутствие зависших багов.',
  code_health: 'Плотность TODO/FIXME маркеров, крупные файлы и локальный SAST.',
};

export interface DemoPreset {
  id: string;
  name: string;
  description: string;
  scores: Record<string, number | null>;
}

export const DEMO_PRESETS: DemoPreset[] = [
  {
    id: 'healthy',
    name: 'Здоровый проект',
    description: 'Все 6 категорий измерены, высокие показатели качества и безопасности.',
    scores: {
      documentation: 95,
      cicd: 90,
      security: 100,
      activity: 85,
      issues: 90,
      code_health: 95,
    },
  },
  {
    id: 'no_security',
    name: 'Нет Security данных',
    description: 'Анализ без AppSec токена: Security=NO_DATA. Балл ренормализуется без штрафа нулём.',
    scores: {
      documentation: 90,
      cicd: 85,
      security: null,
      activity: 80,
      issues: 85,
      code_health: 90,
    },
  },
  {
    id: 'broken_ci',
    name: 'Сломанный CI',
    description: 'Сбои в пайплайнах CI/CD снижают надежность автоматизации.',
    scores: {
      documentation: 85,
      cicd: 15,
      security: 90,
      activity: 75,
      issues: 80,
      code_health: 85,
    },
  },
  {
    id: 'poor_docs',
    name: 'Плохая документация',
    description: 'Отсутствуют инструкции по сборке, тестированию и быстрый старт.',
    scores: {
      documentation: 20,
      cicd: 85,
      security: 95,
      activity: 80,
      issues: 85,
      code_health: 90,
    },
  },
  {
    id: 'high_debt',
    name: 'Высокий техдолг',
    description: 'Много TODO/FIXME маркеров, замечания SAST и проблемный код.',
    scores: {
      documentation: 80,
      cicd: 80,
      security: 85,
      activity: 75,
      issues: 70,
      code_health: 25,
    },
  },
  {
    id: 'low_data',
    name: 'Мало данных (Source Soul)',
    description: '2 категории и 30% веса: Health=null, но активен предварительный Source Soul.',
    scores: {
      documentation: 70,
      cicd: 65,
      security: null,
      activity: null,
      issues: null,
      code_health: null,
    },
  },
];

interface CategoryState {
  score: number;
  available: boolean;
}

interface DemoRecommendation {
  id: string;
  category: string;
  priority: number;
  title: string;
  action: string;
  impact: string;
}

interface SimulationResult {
  policyVersion: string;
  healthScore: number | null;
  coverage: number;
  isEligible: boolean;
  measurableCount: number;
  activeWeight: number;
  totalNominalWeight: number;
  explanation: string;
  sourceSoulEligible: boolean;
  sourceSoulScore: number | null;
  sourceSoulExplanation: string;
  recommendations: DemoRecommendation[];
}

function getProjectedHealth(
  categories: Record<string, CategoryState>,
  targetCat: string,
  targetScore: number
): number | null {
  let activeWeight = 0;
  let weightedSum = 0;
  let count = 0;

  for (const [name, weight] of Object.entries(CATEGORY_WEIGHTS)) {
    const item = categories[name];
    if (name === targetCat) {
      activeWeight += weight;
      weightedSum += weight * targetScore;
      count += 1;
    } else if (item && item.available) {
      activeWeight += weight;
      weightedSum += weight * item.score;
      count += 1;
    }
  }

  if (count >= 3 && activeWeight >= 50) {
    return Math.round((weightedSum / activeWeight) * 100) / 100;
  }
  return null;
}

function calculateSimulation(categories: Record<string, CategoryState>): SimulationResult {
  let activeWeight = 0;
  let weightedSum = 0;
  let count = 0;

  for (const [name, weight] of Object.entries(CATEGORY_WEIGHTS)) {
    const item = categories[name];
    if (item && item.available) {
      activeWeight += weight;
      weightedSum += weight * item.score;
      count += 1;
    }
  }

  // Official Health: >= 3 categories AND >= 50% nominal weight
  const isEligible = count >= 3 && activeWeight >= 50;
  const healthScore = isEligible ? Math.round((weightedSum / activeWeight) * 100) / 100 : null;

  // Source Soul preview: >= 2 categories AND >= 30% nominal weight
  const sourceSoulEligible = count >= 2 && activeWeight >= 30;
  const sourceSoulScore = sourceSoulEligible ? Math.round((weightedSum / activeWeight) * 100) / 100 : null;

  const explanation = isEligible
    ? `Health Score = ${healthScore?.toFixed(1)}, рассчитан по ${count} доступным категориям с суммарным весом ${activeWeight}%. Формула: Σ(w_i × s_i) / Σ(w_i). Категории со статусом NO_DATA честно исключены из знаменателя и не штрафуют проект нулём.`
    : `Health не рассчитывается (null). Не выполнен обязательный порог допуска методики mvp-score-v1.2: требуется не менее 3 доступных категорий и не менее 50% нормативного веса. Сейчас доступно: ${count} категорий (${activeWeight}% веса). Отсутствие данных не превращается в 0.`;

  const sourceSoulExplanation = isEligible
    ? 'Официальный Health рассчитан. В соответствии с методологией платформы, предварительный Source Soul исчезает и уступает место официальному рейтингу качества.'
    : sourceSoulEligible
    ? `Предварительный Source Soul = ${sourceSoulScore?.toFixed(1)} (порог допуска: ≥2 категорий и ≥30% веса). Является предварительным ориентиром, не участвует в общем лидерборде и автоматически скрывается при появлении официального Health.`
    : `Недостаточно данных даже для предварительного Source Soul: доступно ${count} из требуемых 2 категорий (${activeWeight}% из 30% веса).`;

  // Dynamic simulation recommendations with truthful what-if calculation
  const getImpactText = (categoryKey: string): string => {
    if (healthScore === null) {
      return 'Поможет увеличить покрытие/качество категории; итоговое влияние зависит от доступности остальных данных.';
    }
    const projected = getProjectedHealth(categories, categoryKey, 100);
    if (projected !== null) {
      const delta = Math.round((projected - healthScore) * 10) / 10;
      if (delta > 0) {
        return `Потенциальный прирост Health: +${delta.toFixed(1)} б. (с ${healthScore.toFixed(1)} до ${projected.toFixed(1)})`;
      }
    }
    return 'Повысит надежность категории до 100 баллов.';
  };

  const recommendations: DemoRecommendation[] = [];

  if (categories.documentation?.available && categories.documentation.score < 70) {
    recommendations.push({
      id: 'rec_docs',
      category: 'Documentation',
      priority: 1,
      title: 'Улучшить сопроводительную документацию',
      action: 'Добавьте в README.md разделы Быстрый старт, Установка, Сборка, Тестирование и файл LICENSE.',
      impact: getImpactText('documentation'),
    });
  }

  if (categories.cicd?.available && categories.cicd.score < 70) {
    recommendations.push({
      id: 'rec_cicd',
      category: 'CI/CD',
      priority: 1,
      title: 'Стабилизировать автоматические пайплайны',
      action: 'Устраните сбои в тестах CI/CD, чтобы процент успешных прогонов превышал 80%.',
      impact: getImpactText('cicd'),
    });
  }

  if (categories.security?.available && categories.security.score < 70) {
    recommendations.push({
      id: 'rec_sec',
      category: 'Security',
      priority: 1,
      title: 'Устранить дефекты безопасности AppSec',
      action: 'Закройте критические и высокие уязвимости, обнаруженные сканером SourceCraft AppSec.',
      impact: getImpactText('security'),
    });
  }

  if (categories.code_health?.available && categories.code_health.score < 70) {
    recommendations.push({
      id: 'rec_code',
      category: 'Code Health',
      priority: 2,
      title: 'Снизить технический долг в кодовой базе',
      action: 'Устраните заброшенные TODO/FIXME маркеры, разбейте файлы объемом >1000 строк и исправьте замечания SAST.',
      impact: getImpactText('code_health'),
    });
  }

  if (categories.issues?.available && categories.issues.score < 70) {
    recommendations.push({
      id: 'rec_issues',
      category: 'Issues',
      priority: 2,
      title: 'Оптимизировать работу с баг-трекером',
      action: 'Закройте или актуализируйте зависшие issues старше 30 дней и сократите среднее время отклика.',
      impact: getImpactText('issues'),
    });
  }

  if (categories.activity?.available && categories.activity.score < 70) {
    recommendations.push({
      id: 'rec_activity',
      category: 'Activity',
      priority: 3,
      title: 'Поддерживать регулярный ритм разработки',
      action: 'Поддерживайте регулярную активность проекта, работу с изменениями и релизами; избегайте длительных периодов без активности.',
      impact: getImpactText('activity'),
    });
  }

  if (!categories.security?.available) {
    recommendations.push({
      id: 'rec_sec_nodata',
      category: 'Security',
      priority: 2,
      title: 'Подключить официальный SourceCraft AppSec',
      action: 'Подключите SourceCraft PAT в разделе «Мой SourceCraft» для сканирования уязвимостей без статуса NO_DATA.',
      impact: 'Добавит до 20 п.п. nominal coverage; итоговый Security score зависит от результатов official AppSec.',
    });
  }

  if (recommendations.length === 0) {
    recommendations.push({
      id: 'rec_perfect',
      category: 'Общий статус',
      priority: 3,
      title: 'Высокое инженерное качество',
      action: 'Все доступные категории находятся на высоком уровне. Поддерживайте регулярность аудитов.',
      impact: 'Проект готов к получению высших инженерных достижений.',
    });
  }

  return {
    policyVersion: 'mvp-score-v1.2',
    healthScore,
    coverage: activeWeight,
    isEligible,
    measurableCount: count,
    activeWeight,
    totalNominalWeight: 100,
    explanation,
    sourceSoulEligible,
    sourceSoulScore,
    sourceSoulExplanation,
    recommendations,
  };
}

export const DemoPage: React.FC = () => {
  usePageTitle('SourceHealth Lab — Интерактивный симулятор здоровья');

  const [categories, setCategories] = useState<Record<string, CategoryState>>({
    documentation: { score: 95, available: true },
    cicd: { score: 90, available: true },
    security: { score: 100, available: true },
    activity: { score: 85, available: true },
    issues: { score: 90, available: true },
    code_health: { score: 95, available: true },
  });

  const [activePreset, setActivePreset] = useState<string>('healthy');

  // Pure deterministic instant simulation on client side — ZERO network requests
  const simulation = useMemo(() => calculateSimulation(categories), [categories]);

  const handleScoreChange = (category: string, newScore: number) => {
    setActivePreset('');
    setCategories((prev) => ({
      ...prev,
      [category]: { ...prev[category], score: Math.max(0, Math.min(100, newScore)) },
    }));
  };

  const handleAvailabilityToggle = (category: string) => {
    setActivePreset('');
    setCategories((prev) => ({
      ...prev,
      [category]: { ...prev[category], available: !prev[category].available },
    }));
  };

  const handlePresetSelect = (preset: DemoPreset) => {
    setActivePreset(preset.id);
    const nextState: Record<string, CategoryState> = {};
    for (const key of CATEGORY_ORDER) {
      const score = preset.scores[key];
      if (score !== null && score !== undefined) {
        nextState[key] = { score, available: true };
      } else {
        nextState[key] = { score: 80, available: false };
      }
    }
    setCategories(nextState);
  };

  const healthScore = simulation.healthScore;
  const coveragePercent = simulation.coverage;
  const isEligible = simulation.isEligible;
  const sourceSoulScore = simulation.sourceSoulScore;
  const sourceSoulEligible = simulation.sourceSoulEligible;

  const demoReadmeSnippet = `[![SourceHealth](https://sourcehealth.tech/api/v1/badges/ORG/REPO.svg)](https://sourcehealth.tech/repositories/ORG/REPO)`;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-5)' }}>
      {/* 1. Header & Autonomous Offline Banner */}
      <div
        role="status"
        style={{
          padding: 'var(--sh-space-4)',
          backgroundColor: 'var(--sh-bg-surface)',
          border: '1px solid var(--sh-border-subtle)',
          borderRadius: 'var(--sh-radius-md)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
          <span style={{ fontSize: '1.8rem' }} aria-hidden="true">
            🔬
          </span>
          <div>
            <h1 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0, color: 'var(--sh-text-primary)' }}>
              SourceHealth Lab
            </h1>
            <p style={{ margin: '0.2rem 0 0', fontSize: '0.88rem', color: 'var(--sh-text-secondary)' }}>
              Интерактивная симуляция скоринга <strong>mvp-score-v1.2</strong>. Работает полностью автономно в браузере без обращения к серверу или базам данных.
            </p>
          </div>
        </div>

        <Link to="/" className="btn-link" style={getButtonStyles('primary', 'sm')}>
          Перейти к живому каталогу →
        </Link>
      </div>

      {/* 2. Interactive Health Score Widget & Summary */}
      <Card>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: 'var(--sh-space-4)',
            alignItems: 'center',
          }}
        >
          {/* Main Score Display */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <div style={{ fontSize: '0.85rem', color: 'var(--sh-text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
              Рассчитанный Health Score
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '1rem' }}>
              {isEligible && healthScore !== null ? (
                <div style={{ fontSize: '3rem', fontWeight: 800, color: healthScore >= 75 ? 'var(--sh-health-good)' : healthScore >= 50 ? 'var(--sh-health-warning)' : 'var(--sh-health-danger)' }}>
                  {healthScore.toFixed(1)}
                  <span style={{ fontSize: '1.2rem', color: 'var(--sh-text-muted)', fontWeight: 400 }}> / 100</span>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                  <span style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--sh-text-muted)' }}>
                    Health не рассчитывается
                  </span>
                  <Badge variant="warning">NO_DATA: недостаточный охват</Badge>
                </div>
              )}
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
              <Badge variant={isEligible ? 'success' : 'neutral'}>
                {isEligible ? 'Порог допуска пройден' : 'Порог допуска не пройден'}
              </Badge>
              <Badge variant="brand">
                Покрытие: {coveragePercent}%
              </Badge>
              <span style={{ fontSize: '0.82rem', color: 'var(--sh-text-muted)' }}>
                {`${simulation.measurableCount} из 6 категорий (${simulation.activeWeight}% веса)`}
              </span>
            </div>
          </div>

          {/* Formula explanation block */}
          <div
            style={{
              padding: 'var(--sh-space-3) var(--sh-space-4)',
              backgroundColor: 'var(--sh-bg-base)',
              borderRadius: 'var(--sh-radius-sm)',
              border: '1px solid var(--sh-border-subtle)',
              fontSize: '0.85rem',
              color: 'var(--sh-text-secondary)',
              lineHeight: 1.5,
            }}
          >
            <div style={{ fontWeight: 600, color: 'var(--sh-text-primary)', marginBottom: '0.25rem' }}>
              Математика ренормализации:
            </div>
            <p style={{ margin: 0 }}>
              {simulation.explanation}
            </p>
            <div style={{ marginTop: '0.4rem', fontSize: '0.8rem', color: 'var(--sh-brand)' }}>
              Инвариант: <strong>NO_DATA ≠ 0</strong>. Если категория недоступна, она исключается из знаменателя.
            </div>
          </div>
        </div>
      </Card>

      {/* 3. Source Soul Preview & Explanation Card */}
      <Card
        title="Предварительный Source Soul vs Официальный Health"
        subtitle="Разделение предварительного ориентира и официального рейтингового балла платформы"
      >
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: 'var(--sh-space-4)',
            alignItems: 'center',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ fontSize: '1.25rem' }}>👻</span>
              <span style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--sh-text-primary)' }}>
                Source Soul:
              </span>
              {isEligible ? (
                <span style={{ fontSize: '0.9rem', color: 'var(--sh-text-muted)', fontStyle: 'italic' }}>
                  Заменён официальным Health
                </span>
              ) : sourceSoulEligible && sourceSoulScore !== null ? (
                <span style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--sh-brand)' }}>
                  {sourceSoulScore.toFixed(1)} / 100
                </span>
              ) : (
                <Badge variant="neutral">Недоступен (&lt; 2 категорий)</Badge>
              )}
            </div>

            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {isEligible ? (
                <Badge variant="success">✓ Официальный Health активен (Source Soul скрыт)</Badge>
              ) : sourceSoulEligible ? (
                <Badge variant="brand">👻 Активен предварительный Source Soul ({sourceSoulScore?.toFixed(1)})</Badge>
              ) : (
                <Badge variant="neutral">Недостаточно данных (&lt; 2 категорий или &lt; 30% веса)</Badge>
              )}
            </div>
          </div>

          <div
            style={{
              padding: 'var(--sh-space-3) var(--sh-space-4)',
              backgroundColor: 'var(--sh-bg-base)',
              borderRadius: 'var(--sh-radius-sm)',
              border: '1px solid var(--sh-border-subtle)',
              fontSize: '0.82rem',
              color: 'var(--sh-text-secondary)',
              lineHeight: 1.45,
            }}
          >
            <p style={{ margin: 0 }}>
              {simulation.sourceSoulExplanation}
            </p>
            <div style={{ marginTop: '0.4rem', fontSize: '0.78rem', color: 'var(--sh-text-muted)' }}>
              Правила допуска: <strong>Официальный Health</strong> требует ≥3 категорий и ≥50% номинального веса. <strong>Source Soul</strong> включается раньше (≥2 категорий и ≥30% веса), не участвует в лидерборде и автоматически скрывается при появлении официального Health.
            </div>
          </div>
        </div>
      </Card>

      {/* 4. Presets Selector */}
      <Card title="Готовые пресеты сценариев" subtitle="Выберите типовую инженерную ситуацию в один клик">
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: 'var(--sh-space-3)',
          }}
        >
          {DEMO_PRESETS.map((preset) => {
            const isSelected = activePreset === preset.id;
            return (
              <button
                key={preset.id}
                type="button"
                onClick={() => handlePresetSelect(preset)}
                style={{
                  padding: 'var(--sh-space-3)',
                  backgroundColor: isSelected ? 'var(--sh-brand-surface, #eef2ff)' : 'var(--sh-bg-base)',
                  border: `1.5px solid ${isSelected ? 'var(--sh-brand)' : 'var(--sh-border-subtle)'}`,
                  borderRadius: 'var(--sh-radius-sm)',
                  textAlign: 'left',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.25rem',
                }}
              >
                <div style={{ fontWeight: 700, fontSize: '0.9rem', color: isSelected ? 'var(--sh-brand)' : 'var(--sh-text-primary)' }}>
                  {preset.name}
                </div>
                <div style={{ fontSize: '0.78rem', color: 'var(--sh-text-muted)', lineHeight: 1.35 }}>
                  {preset.description}
                </div>
              </button>
            );
          })}
        </div>
      </Card>

      {/* 5. Six Category Interactive Controls */}
      <Card
        title="Интерактивные контролы 6 категорий"
        subtitle="Перемещайте слайдеры баллов или переключайте категорию в NO_DATA, чтобы наблюдать мгновенный локальный перерасчёт"
      >
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
            gap: 'var(--sh-space-4)',
          }}
        >
          {CATEGORY_ORDER.map((category) => {
            const item = categories[category] ?? { score: 80, available: true };
            const weight = CATEGORY_WEIGHTS[category] ?? 15;
            const label = CATEGORY_LABELS[category] ?? category;
            const desc = CATEGORY_DESCRIPTIONS[category] ?? '';

            return (
              <div
                key={category}
                style={{
                  padding: 'var(--sh-space-4)',
                  backgroundColor: item.available ? 'var(--sh-bg-base)' : 'var(--sh-bg-surface)',
                  border: '1px solid var(--sh-border-subtle)',
                  borderRadius: 'var(--sh-radius-md)',
                  opacity: item.available ? 1 : 0.72,
                  transition: 'opacity 0.2s ease',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.75rem',
                }}
              >
                {/* Header row: Title + Weight + Toggle */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.5rem' }}>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--sh-text-primary)' }}>
                      {label}
                    </div>
                    <span style={{ fontSize: '0.78rem', color: 'var(--sh-text-muted)' }}>
                      Вес в формуле: <strong>{weight}%</strong>
                    </span>
                  </div>

                  <button
                    type="button"
                    role="switch"
                    aria-checked={item.available}
                    onClick={() => handleAvailabilityToggle(category)}
                    style={{
                      padding: '0.25rem 0.6rem',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      borderRadius: 'var(--sh-radius-sm)',
                      cursor: 'pointer',
                      border: '1px solid',
                      backgroundColor: item.available ? 'var(--sh-health-good-bg, #e8f5e9)' : 'var(--sh-bg-surface)',
                      borderColor: item.available ? 'var(--sh-health-good-border, #a5d6a7)' : 'var(--sh-border-subtle)',
                      color: item.available ? 'var(--sh-health-good, #2e7d32)' : 'var(--sh-text-muted)',
                    }}
                  >
                    {item.available ? '✓ AVAILABLE' : '∅ NO_DATA'}
                  </button>
                </div>

                <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--sh-text-secondary)', lineHeight: 1.35 }}>
                  {desc}
                </p>

                {/* Slider row */}
                {item.available ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', marginTop: '0.25rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '0.8rem', color: 'var(--sh-text-muted)' }}>Балл категории:</span>
                      <span style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--sh-brand)' }}>
                        {item.score} / 100
                      </span>
                    </div>

                    <input
                      type="range"
                      min={0}
                      max={100}
                      step={1}
                      value={item.score}
                      aria-label={`Балл категории ${label}`}
                      onChange={(e) => handleScoreChange(category, Number(e.target.value))}
                      style={{
                        width: '100%',
                        cursor: 'pointer',
                        accentColor: 'var(--sh-brand)',
                      }}
                    />
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', color: 'var(--sh-text-muted)' }}>
                      <span>0 (критично)</span>
                      <span>50 (средне)</span>
                      <span>100 (идеально)</span>
                    </div>
                  </div>
                ) : (
                  <div
                    style={{
                      padding: 'var(--sh-space-2) var(--sh-space-3)',
                      backgroundColor: 'var(--sh-bg-surface)',
                      borderRadius: 'var(--sh-radius-sm)',
                      fontSize: '0.82rem',
                      color: 'var(--sh-text-muted)',
                      fontStyle: 'italic',
                      textAlign: 'center',
                    }}
                  >
                    Категория отключена (NO_DATA). Не штрафует проект нулём.
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </Card>

      {/* 6. Dynamic Simulation Recommendations */}
      <Card
        title="Динамические рекомендации симуляции"
        subtitle="Рекомендации адаптируются в реальном времени при изменении баллов и доступности категорий"
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-3)' }}>
          <div
            style={{
              padding: 'var(--sh-space-2) var(--sh-space-3)',
              backgroundColor: 'var(--sh-bg-surface)',
              borderRadius: 'var(--sh-radius-sm)',
              border: '1px solid var(--sh-border-subtle)',
              fontSize: '0.78rem',
              color: 'var(--sh-text-muted)',
            }}
          >
            ℹ️ <strong>Примечание симулятора:</strong> Ниже представлены примеры рекомендаций симулятора (simulation/demo recommendations) с расчётом влияния (what-if) на итоговый балл. В реальном отчёте анализа рекомендации строго привязаны к подтверждённым свидетельствам (evidence) из исходного кода и API.
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
              gap: 'var(--sh-space-3)',
            }}
          >
            {simulation.recommendations.map((rec) => (
              <div
                key={rec.id}
                style={{
                  padding: 'var(--sh-space-3)',
                  backgroundColor: 'var(--sh-bg-base)',
                  border: '1px solid var(--sh-border-subtle)',
                  borderRadius: 'var(--sh-radius-sm)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.35rem',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 700, fontSize: '0.88rem', color: 'var(--sh-text-primary)' }}>
                    {rec.title}
                  </span>
                  <Badge variant={rec.priority === 1 ? 'danger' : rec.priority === 2 ? 'warning' : 'brand'}>
                    Приоритет {rec.priority}
                  </Badge>
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--sh-text-secondary)', lineHeight: 1.4 }}>
                  {rec.action}
                </div>
                <div style={{ fontSize: '0.76rem', color: 'var(--sh-brand)', fontWeight: 500, marginTop: '0.2rem' }}>
                  {rec.impact}
                </div>
              </div>
            ))}
          </div>
        </div>
      </Card>

      {/* 7. AI Teaser Card */}
      <Card
        title="Нейросетевое резюме (Yandex AI Teaser)"
        subtitle="Архитектура интеграции генеративного AI со строгим заземлением (Grounding)"
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-3)' }}>
          <p style={{ margin: 0, fontSize: '0.88rem', color: 'var(--sh-text-secondary)', lineHeight: 1.5 }}>
            В реальном анализе репозитория мейнтейнерам доступно структурированное AI-резюме на базе моделей <strong>Yandex AI</strong>. Генерация запускается по запросу и опирается исключительно на подтверждённые факты отчёта (evidence):
          </p>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: 'var(--sh-space-3)',
            }}
          >
            <div style={{ padding: 'var(--sh-space-3)', backgroundColor: 'var(--sh-bg-base)', borderRadius: 'var(--sh-radius-sm)', border: '1px solid var(--sh-border-subtle)' }}>
              <div style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--sh-brand)', marginBottom: '0.2rem' }}>
                ⚡ «Мозг»
              </div>
              <div style={{ fontSize: '0.78rem', color: 'var(--sh-text-muted)' }}>Alice AI Flash</div>
              <p style={{ margin: '0.3rem 0 0', fontSize: '0.82rem', color: 'var(--sh-text-secondary)' }}>
                Краткая экспресс-сводка по ключевым числовым метрикам для беглого ознакомления.
              </p>
            </div>

            <div style={{ padding: 'var(--sh-space-3)', backgroundColor: 'var(--sh-bg-base)', borderRadius: 'var(--sh-radius-sm)', border: '1px solid var(--sh-border-subtle)' }}>
              <div style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--sh-brand)', marginBottom: '0.2rem' }}>
                🎯 «Крутой мозг»
              </div>
              <div style={{ fontSize: '0.78rem', color: 'var(--sh-text-muted)' }}>YandexGPT 5 Lite</div>
              <p style={{ margin: '0.3rem 0 0', fontSize: '0.82rem', color: 'var(--sh-text-secondary)' }}>
                Сбалансированное инженерное резюме по метрикам и практикам разработки.
              </p>
            </div>

            <div style={{ padding: 'var(--sh-space-3)', backgroundColor: 'var(--sh-bg-base)', borderRadius: 'var(--sh-radius-sm)', border: '1px solid var(--sh-border-subtle)' }}>
              <div style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--sh-brand)', marginBottom: '0.2rem' }}>
                🧠 «Мегамозг»
              </div>
              <div style={{ fontSize: '0.78rem', color: 'var(--sh-text-muted)' }}>YandexGPT 5.1 Pro</div>
              <p style={{ margin: '0.3rem 0 0', fontSize: '0.82rem', color: 'var(--sh-text-secondary)' }}>
                Более подробное инженерное резюме по подтверждённым данным анализа, рискам и рекомендациям.
              </p>
            </div>
          </div>

          <div
            style={{
              padding: 'var(--sh-space-2) var(--sh-space-3)',
              backgroundColor: 'var(--sh-bg-base)',
              borderRadius: 'var(--sh-radius-sm)',
              border: '1px solid var(--sh-border-subtle)',
              fontSize: '0.82rem',
              color: 'var(--sh-text-muted)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '0.5rem',
            }}
          >
            <span>
              🛡️ <strong>Grounding Check:</strong> Нейросеть не анализирует исходники напрямую и не вычисляет баллы, а формирует резюме строго по проверенным фактам отчёта (evidence).
            </span>
            <Link to="/" style={{ color: 'var(--sh-brand)', fontWeight: 600, fontSize: '0.82rem' }}>
              Посмотреть реальный анализ в каталоге →
            </Link>
          </div>
        </div>
      </Card>

      {/* 8. Visible Badge Preview Section */}
      <Card
        title="Предпросмотр динамического бейджа качества"
        subtitle="Интерактивный предварительный просмотр бейджа для README.md в светлой и тёмной темах"
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-4)' }}>
          <div style={{ fontSize: '0.78rem', color: 'var(--sh-text-muted)', fontStyle: 'italic' }}>
            ℹ️ Визуальный preview симулятора с цветовой дифференциацией (green/yellow/red); production badge платформы в текущей версии использует лаконичный строгий стиль оформления.
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
              gap: 'var(--sh-space-4)',
            }}
          >
            {/* Light Preview Box */}
            <div
              style={{
                padding: 'var(--sh-space-4)',
                backgroundColor: '#ffffff',
                color: '#24292f',
                borderRadius: 'var(--sh-radius-md)',
                border: '1px solid #d0d7de',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.5rem',
                alignItems: 'center',
              }}
            >
              <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#57609a' }}>
                GitHub / SourceCraft Light Theme
              </div>
              <div style={{ padding: '0.5rem 0' }}>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width={healthScore !== null ? 118 : 142}
                  height={20}
                  role="img"
                  aria-label={`SourceHealth: ${healthScore !== null ? Math.round(healthScore) : 'no score'}`}
                >
                  <rect width={healthScore !== null ? 118 : 142} height={20} rx={3} fill="#555" />
                  <rect
                    x={88}
                    width={healthScore !== null ? 30 : 54}
                    height={20}
                    rx={3}
                    fill={healthScore === null ? '#888' : healthScore >= 75 ? '#2e7d32' : healthScore >= 50 ? '#f9a825' : '#e53935'}
                  />
                  <g fill="#fff" textAnchor="middle" fontFamily="Verdana,Arial,sans-serif" fontSize={11}>
                    <text x={44} y={14}>SourceHealth</text>
                    <text x={healthScore !== null ? 103 : 115} y={14}>
                      {healthScore !== null ? Math.round(healthScore) : 'no score'}
                    </text>
                  </g>
                </svg>
              </div>
            </div>

            {/* Dark Preview Box */}
            <div
              style={{
                padding: 'var(--sh-space-4)',
                backgroundColor: '#0d1117',
                color: '#c9d1d9',
                borderRadius: 'var(--sh-radius-md)',
                border: '1px solid #30363d',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.5rem',
                alignItems: 'center',
              }}
            >
              <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#8b949e' }}>
                GitHub / SourceCraft Dark Theme
              </div>
              <div style={{ padding: '0.5rem 0' }}>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width={healthScore !== null ? 118 : 142}
                  height={20}
                  role="img"
                  aria-label={`SourceHealth: ${healthScore !== null ? Math.round(healthScore) : 'no score'}`}
                >
                  <rect width={healthScore !== null ? 118 : 142} height={20} rx={3} fill="#333" />
                  <rect
                    x={88}
                    width={healthScore !== null ? 30 : 54}
                    height={20}
                    rx={3}
                    fill={healthScore === null ? '#888' : healthScore >= 75 ? '#2e7d32' : healthScore >= 50 ? '#f9a825' : '#e53935'}
                  />
                  <g fill="#fff" textAnchor="middle" fontFamily="Verdana,Arial,sans-serif" fontSize={11}>
                    <text x={44} y={14}>SourceHealth</text>
                    <text x={healthScore !== null ? 103 : 115} y={14}>
                      {healthScore !== null ? Math.round(healthScore) : 'no score'}
                    </text>
                  </g>
                </svg>
              </div>
            </div>
          </div>

          {/* Copyable Markdown Box */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--sh-text-primary)' }}>
              Код бейджа для вставки в README.md:
            </span>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: 'var(--sh-space-2) var(--sh-space-3)',
                backgroundColor: 'var(--sh-bg-base)',
                border: '1px solid var(--sh-border-subtle)',
                borderRadius: 'var(--sh-radius-sm)',
                fontFamily: 'monospace',
                fontSize: '0.82rem',
                overflowX: 'auto',
              }}
            >
              <code>{demoReadmeSnippet}</code>
              <CopyButton value={demoReadmeSnippet} />
            </div>
            <div style={{ fontSize: '0.78rem', color: 'var(--sh-text-muted)' }}>
              💡 Замените <code>ORG/REPO</code> на путь вашего публичного репозитория в SourceCraft.
            </div>
          </div>
        </div>
      </Card>

      {/* 9. Bottom Navigation */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 'var(--sh-space-2)' }}>
        <Link to="/" style={{ color: 'var(--sh-brand)', fontWeight: 500, fontSize: '0.9rem' }}>
          ← Вернуться к лидерборду репозиториев
        </Link>
      </div>
    </div>
  );
};
