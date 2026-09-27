import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { ScoreDisplay } from '../components/common/ScoreDisplay';
import { CopyButton } from '../components/common/CopyButton';
import { getButtonStyles } from '../components/common/Button';
import { usePageTitle } from '../utils/usePageTitle';
import { CATEGORY_ORDER, CATEGORY_LABELS } from '../utils/analysis';
import { api, type DemoPreset, type DemoSimulateResponse } from '../api/client';

const CATEGORY_WEIGHTS: Record<string, number> = {
  documentation: 15,
  cicd: 15,
  security: 20,
  activity: 15,
  issues: 15,
  code_health: 20,
};

const CATEGORY_DESCRIPTIONS: Record<string, string> = {
  documentation: 'README, установка, запуск, сборка, тесты, лицензия и быстрый старт.',
  cicd: 'Конфигурация CI/CD пайплайнов и процент успешных сборок (≥80%).',
  security: 'Дефекты официального SourceCraft AppSec по критичности через PAT.',
  activity: 'Коммиты за 30 дней, регулярность, давность последнего коммита и релизы.',
  issues: 'Доля закрытых задач, время реакции и отсутствие зависших багов.',
  code_health: 'Плотность TODO/FIXME маркеров, крупные файлы и локальный SAST.',
};

interface CategoryState {
  score: number;
  available: boolean;
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

  const [simulation, setSimulation] = useState<DemoSimulateResponse | null>(null);
  const [presets, setPresets] = useState<DemoPreset[]>([]);
  const [activePreset, setActivePreset] = useState<string>('healthy');
  const [isSimulating, setIsSimulating] = useState<boolean>(false);

  // Load presets on mount
  useEffect(() => {
    api.demoPresets().then((data) => {
      if (Array.isArray(data) && data.length > 0) {
        setPresets(data);
      }
    }).catch(() => {
      // Fallback presets if offline
    });
  }, []);

  // Run simulation whenever category state changes
  const runSimulation = useCallback(async (state: Record<string, CategoryState>) => {
    setIsSimulating(true);
    const scoresPayload: Record<string, number | null> = {};
    for (const [key, val] of Object.entries(state)) {
      scoresPayload[key] = val.available ? val.score : null;
    }

    try {
      const res = await api.demoSimulate(scoresPayload);
      setSimulation(res);
    } catch {
      // Deterministic client fallback strictly matching mvp-score-v1.2 semantics
      let activeWeight = 0;
      let weightedSum = 0;
      let count = 0;
      const breakdown: DemoSimulateResponse['categories'] = {};

      for (const [name, weight] of Object.entries(CATEGORY_WEIGHTS)) {
        const item = state[name];
        if (item && item.available) {
          activeWeight += weight;
          weightedSum += weight * item.score;
          count += 1;
          breakdown[name] = { score: item.score, weight, available: true };
        } else {
          breakdown[name] = { score: null, weight, available: false };
        }
      }

      const eligible = count >= 3 && activeWeight >= 50;
      const healthScore = eligible ? Math.round((weightedSum / activeWeight) * 100) / 100 : null;

      setSimulation({
        policy_version: 'mvp-score-v1.2',
        health_score: healthScore,
        coverage: activeWeight,
        eligible,
        measurable_count: count,
        active_weight: activeWeight,
        total_nominal_weight: 100,
        categories: breakdown,
        explanation: eligible
          ? `Health Score = ${healthScore?.toFixed(2)}, рассчитан по ${count} доступным категориям с весом ${activeWeight}%.`
          : `Health не рассчитывается (null). Не выполнен порог допуска: требуется ≥3 категорий и ≥50% веса. Сейчас: ${count} категорий (${activeWeight}%).`,
      });
    } finally {
      setIsSimulating(false);
    }
  }, []);

  useEffect(() => {
    runSimulation(categories);
  }, [categories, runSimulation]);

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
    for (const [key, defaultWeight] of Object.entries(CATEGORY_WEIGHTS)) {
      void defaultWeight;
      const score = preset.scores[key];
      if (score !== null && score !== undefined) {
        nextState[key] = { score, available: true };
      } else {
        nextState[key] = { score: 80, available: false };
      }
    }
    setCategories(nextState);
  };

  const healthScore = simulation?.health_score ?? null;
  const coveragePercent = simulation?.coverage ?? 0;
  const isEligible = simulation?.eligible ?? false;

  const demoReadmeSnippet = `[![SourceHealth](https://sourcehealth.tech/api/v1/badges/demo-org/demo-repo.svg)](https://sourcehealth.tech/repositories/demo-org/demo-repo)`;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-5)' }}>
      {/* 1. Header & Banner */}
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
              Это интерактивная симуляция методики <strong>mvp-score-v1.2</strong>, а не анализ реального репозитория.
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
                {simulation ? `${simulation.measurable_count} из 6 категорий (${simulation.active_weight} веса)` : ''}
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
              {simulation?.explanation ?? 'Загрузка симуляции...'}
            </p>
            <div style={{ marginTop: '0.4rem', fontSize: '0.8rem', color: 'var(--sh-brand)' }}>
              Инвариант: <strong>NO_DATA ≠ 0</strong>. Если категория недоступна, она исключается из знаменателя.
            </div>
          </div>
        </div>
      </Card>

      {/* 3. Presets Selector */}
      <Card title="Готовые пресеты сценариев" subtitle="Выберите типовую инженерную ситуацию в один клик">
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: 'var(--sh-space-3)',
          }}
        >
          {presets.map((preset) => {
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

      {/* 4. Six Category Interactive Controls */}
      <Card
        title="Интерактивные контролы 6 категорий"
        subtitle="Перемещайте слайдеры баллов или переключайте категорию в NO_DATA, чтобы наблюдать мгновенный перерасчёт Health Score"
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

      {/* 5. Visible Badge Preview Section */}
      <Card
        title="Как выглядит badge в README"
        subtitle="Динамический SVG-бейдж обновляется в зависимости от текущего расчетного балла"
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-4)' }}>
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
                  <linearGradient id="demo-light-grad" x2="0" y2="100%">
                    <stop offset="0" stopColor="#bbb" />
                    <stop offset="1" stopColor="#999" />
                  </linearGradient>
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
              Код для вставки в README.md:
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
          </div>
        </div>
      </Card>

      {/* 6. What Happens in Real Analysis */}
      <Card title="Как устроен реальный анализ SourceHealth">
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: 'var(--sh-space-3)',
          }}
        >
          <div
            style={{
              padding: 'var(--sh-space-3)',
              backgroundColor: 'var(--sh-bg-base)',
              borderRadius: 'var(--sh-radius-sm)',
              border: '1px solid var(--sh-border-subtle)',
            }}
          >
            <div style={{ fontWeight: 700, color: 'var(--sh-brand)', marginBottom: '0.2rem' }}>
              1. Безопасный сбор фактов
            </div>
            <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--sh-text-secondary)', lineHeight: 1.4 }}>
              Код репозитория никогда не исполняется. Анализ проводится статически в эфемерных контейнерах с ограничениями ресурсов.
            </p>
          </div>

          <div
            style={{
              padding: 'var(--sh-space-3)',
              backgroundColor: 'var(--sh-bg-base)',
              borderRadius: 'var(--sh-radius-sm)',
              border: '1px solid var(--sh-border-subtle)',
            }}
          >
            <div style={{ fontWeight: 700, color: 'var(--sh-brand)', marginBottom: '0.2rem' }}>
              2. Детерминированный скоринг
            </div>
            <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--sh-text-secondary)', lineHeight: 1.4 }}>
              Шесть категорий оцениваются по математической формуле `mvp-score-v1.2`. Исключены субъективность и нейросетевые галлюцинации в баллах.
            </p>
          </div>

          <div
            style={{
              padding: 'var(--sh-space-3)',
              backgroundColor: 'var(--sh-bg-base)',
              borderRadius: 'var(--sh-radius-sm)',
              border: '1px solid var(--sh-border-subtle)',
            }}
          >
            <div style={{ fontWeight: 700, color: 'var(--sh-brand)', marginBottom: '0.2rem' }}>
              3. Свидетельства (Evidence)
            </div>
            <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--sh-text-secondary)', lineHeight: 1.4 }}>
              Каждый балл подкреплён ссылками на проверенные факты: файлы, коммиты, маркеры техдолга и уязвимости AppSec.
            </p>
          </div>

          <div
            style={{
              padding: 'var(--sh-space-3)',
              backgroundColor: 'var(--sh-bg-base)',
              borderRadius: 'var(--sh-radius-sm)',
              border: '1px solid var(--sh-border-subtle)',
            }}
          >
            <div style={{ fontWeight: 700, color: 'var(--sh-brand)', marginBottom: '0.2rem' }}>
              4. План улучшений
            </div>
            <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--sh-text-secondary)', lineHeight: 1.4 }}>
              Мейнтейнер получает четкий список рекомендаций по приоритетам с прямыми инструкциями по исправлению.
            </p>
          </div>
        </div>
      </Card>

      {/* 7. Bottom Navigation */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 'var(--sh-space-2)' }}>
        <Link to="/" style={{ color: 'var(--sh-brand)', fontWeight: 500, fontSize: '0.9rem' }}>
          ← Вернуться к лидерборду репозиториев
        </Link>
      </div>
    </div>
  );
};
