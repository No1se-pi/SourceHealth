import React, { useEffect, useState, useRef } from 'react';

export interface AppearanceModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export type ThemeOption = 'system' | 'light' | 'dark';
export type AccentOption =
  | 'default'
  | 'red'
  | 'orange'
  | 'yellow'
  | 'green'
  | 'cyan'
  | 'blue'
  | 'pink'
  | 'purple';
export type TempOption = 'warm' | 'neutral' | 'cool';

const ACCENT_COLORS: { id: AccentOption; label: string; color: string }[] = [
  { id: 'default', label: 'По умолчанию', color: 'split' },
  { id: 'red', label: 'Красный', color: '#ff3333' },
  { id: 'orange', label: 'Оранжевый', color: '#f6821e' },
  { id: 'yellow', label: 'Жёлтый', color: '#ffc728' },
  { id: 'green', label: 'Зелёный', color: '#60ba47' },
  { id: 'cyan', label: 'Голубой', color: '#04c0ff' },
  { id: 'blue', label: 'Синий', color: '#047aff' },
  { id: 'pink', label: 'Розовый', color: '#f74f9e' },
  { id: 'purple', label: 'Фиолетовый', color: '#953d96' },
];

export const AppearanceModal: React.FC<AppearanceModalProps> = ({ isOpen, onClose }) => {
  const [theme, setTheme] = useState<ThemeOption>('system');
  const [accent, setAccent] = useState<AccentOption>('default');
  const [temp, setTemp] = useState<TempOption>('neutral');
  const modalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      const storedTheme = (localStorage.getItem('sourcehealth_theme') as ThemeOption) || 'system';
      const storedAccent = (localStorage.getItem('sourcehealth_accent') as AccentOption) || 'default';
      const storedTemp = (localStorage.getItem('sourcehealth_temp') as TempOption) || 'neutral';
      setTheme(storedTheme);
      setAccent(storedAccent);
      setTemp(storedTemp);
    } catch {
      // ignore
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const handleSelectTheme = (newTheme: ThemeOption) => {
    setTheme(newTheme);
    try {
      localStorage.setItem('sourcehealth_theme', newTheme);
    } catch {
      // ignore
    }

    let effectiveTheme = newTheme;
    if (newTheme === 'system') {
      const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      effectiveTheme = prefersDark ? 'dark' : 'light';
    }
    document.documentElement.setAttribute('data-theme', effectiveTheme);
  };

  const handleSelectAccent = (newAccent: AccentOption) => {
    setAccent(newAccent);
    try {
      localStorage.setItem('sourcehealth_accent', newAccent);
    } catch {
      // ignore
    }
    document.documentElement.setAttribute('data-accent', newAccent);
  };

  const handleSelectTemp = (newTemp: TempOption) => {
    setTemp(newTemp);
    try {
      localStorage.setItem('sourcehealth_temp', newTemp);
    } catch {
      // ignore
    }
    document.documentElement.setAttribute('data-temperature', newTemp);
  };

  if (!isOpen) return null;

  return (
    <div className="sc-modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="appearance-title">
      <div className="sc-modal-container" ref={modalRef} onClick={(e) => e.stopPropagation()}>
        <div className="sc-modal-header">
          <h2 id="appearance-title" className="sc-modal-title">Внешний вид</h2>
          <button
            type="button"
            className="sc-modal-close-btn"
            onClick={onClose}
            aria-label="Закрыть настройки внешнего вида"
          >
            ✕
          </button>
        </div>

        <div className="sc-modal-body">
          {/* 1. Theme Option */}
          <div className="sc-settings-row">
            <span className="sc-settings-label">Тема интерфейса</span>
            <div className="sc-segmented-pill-control" role="group" aria-label="Тема интерфейса">
              <button
                type="button"
                className={`sc-pill-btn ${theme === 'system' ? 'active' : ''}`}
                onClick={() => handleSelectTheme('system')}
              >
                Системная
              </button>
              <button
                type="button"
                className={`sc-pill-btn ${theme === 'light' ? 'active' : ''}`}
                onClick={() => handleSelectTheme('light')}
              >
                Светлая
              </button>
              <button
                type="button"
                className={`sc-pill-btn ${theme === 'dark' ? 'active' : ''}`}
                onClick={() => handleSelectTheme('dark')}
              >
                Тёмная
              </button>
            </div>
          </div>

          {/* 2. Accent Colors */}
          <div className="sc-settings-row">
            <span className="sc-settings-label">Акцентный цвет</span>
            <div className="sc-accent-swatches" role="radiogroup" aria-label="Акцентный цвет">
              {ACCENT_COLORS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  role="radio"
                  aria-checked={accent === item.id}
                  aria-label={item.label}
                  className={`sc-accent-circle ${item.id === 'default' ? 'split' : ''} ${accent === item.id ? 'selected' : ''}`}
                  style={item.color !== 'split' ? { backgroundColor: item.color } : undefined}
                  onClick={() => handleSelectAccent(item.id)}
                  title={item.label}
                />
              ))}
            </div>
          </div>

          {/* 3. Gray Temperature */}
          <div className="sc-settings-row">
            <span className="sc-settings-label">Температура серого</span>
            <div className="sc-segmented-pill-control" role="group" aria-label="Температура серого">
              <button
                type="button"
                className={`sc-pill-btn ${temp === 'warm' ? 'active' : ''}`}
                onClick={() => handleSelectTemp('warm')}
              >
                Тёплый
              </button>
              <button
                type="button"
                className={`sc-pill-btn ${temp === 'neutral' ? 'active' : ''}`}
                onClick={() => handleSelectTemp('neutral')}
              >
                Нейтральный
              </button>
              <button
                type="button"
                className={`sc-pill-btn ${temp === 'cool' ? 'active' : ''}`}
                onClick={() => handleSelectTemp('cool')}
              >
                Холодный
              </button>
            </div>
          </div>

          {/* 4. Language */}
          <div className="sc-settings-row">
            <span className="sc-settings-label">Язык</span>
            <div className="sc-segmented-pill-control" role="group" aria-label="Язык интерфейса">
              <button type="button" className="sc-pill-btn active">
                Русский
              </button>
              <button type="button" className="sc-pill-btn" disabled title="English coming soon">
                English
              </button>
            </div>
          </div>
        </div>

        <div className="sc-modal-footer">
          <button type="button" className="sc-btn-secondary" onClick={onClose}>
            Готово
          </button>
        </div>
      </div>
    </div>
  );
};
