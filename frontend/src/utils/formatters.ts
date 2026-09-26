/**
 * Shared formatting utilities for SourceHealth frontend.
 * Provides consistent presentation of numbers, dates, TTLs, and error messages.
 */

export function formatScore(value: number | null | undefined, precision: number = 1): string {
  if (value === null || value === undefined || isNaN(value)) {
    return '—';
  }
  return value.toFixed(precision);
}

export function formatLikes(count: number | null | undefined): string {
  if (count === null || count === undefined) {
    return '—';
  }
  return new Intl.NumberFormat('ru-RU').format(count);
}

export function formatDateTime(isoDate: string | null | undefined): string {
  if (!isoDate) return '—';
  try {
    const date = new Date(isoDate);
    if (isNaN(date.getTime())) return '—';
    return new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    }).format(date);
  } catch {
    return '—';
  }
}

export function formatRelativeTime(isoDate: string | null | undefined): string {
  if (!isoDate) return '—';
  try {
    const date = new Date(isoDate);
    const now = new Date();
    const diffSec = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (diffSec < 0) return 'в будущем';
    if (diffSec < 60) return 'только что';
    if (diffSec < 3600) {
      const minutes = Math.floor(diffSec / 60);
      return `${minutes} ${pluralize(minutes, 'минуту', 'минуты', 'минут')} назад`;
    }
    if (diffSec < 86400) {
      const hours = Math.floor(diffSec / 3600);
      return `${hours} ${pluralize(hours, 'час', 'часа', 'часов')} назад`;
    }
    if (diffSec < 604800) {
      const days = Math.floor(diffSec / 86400);
      return `${days} ${pluralize(days, 'день', 'дня', 'дней')} назад`;
    }

    return new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    }).format(date);
  } catch {
    return '—';
  }
}

function pluralize(n: number, one: string, two: string, five: string): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 19) return five;
  if (mod10 === 1) return one;
  if (mod10 >= 2 && mod10 <= 4) return two;
  return five;
}

export function formatTtl(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || seconds <= 0) {
    return 'истёк';
  }
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;

  if (hours > 0) {
    return minutes > 0 ? `${hours} ч ${minutes} мин` : `${hours} ч`;
  }
  if (minutes > 0) {
    return `${minutes} мин`;
  }
  return `${secs} сек.`;
}

export function formatDurationSeconds(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '—';
  if (seconds < 1) return `${(seconds * 1000).toFixed(0)} мс`;
  if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 1 : 0)} сек.`;
  const mins = Math.floor(seconds / 60);
  const remainingSecs = Math.round(seconds % 60);
  return `${mins} мин ${remainingSecs} сек.`;
}

export function humanizeErrorCode(rawError: string | null | undefined): string {
  if (!rawError) return 'Произошла непредвиденная ошибка';
  const lower = rawError.toLowerCase();

  if (lower.includes('network') || lower.includes('failed to fetch') || lower.includes('connection refused')) {
    return 'Не удалось связаться с сервером SourceHealth. Проверьте сетевое подключение.';
  }
  if (lower.includes('authentication_required') || lower.includes('401') || lower.includes('unauthorized')) {
    return 'Для доступа к этой странице необходима авторизация через Яндекс ID.';
  }
  if (lower.includes('sourcecraft_connection_required')) {
    return 'Требуется подключение персонального токена SourceCraft (PAT).';
  }
  if (lower.includes('repository_not_found') || (lower.includes('404') && lower.includes('repo'))) {
    return 'Запрашиваемый репозиторий не найден в каталоге SourceHealth.';
  }
  if (lower.includes('analysis_not_found') || (lower.includes('404') && lower.includes('analy'))) {
    return 'Запрашиваемый запуск анализа не найден.';
  }
  if (lower.includes('rate_limit') || lower.includes('429')) {
    return 'Превышен лимит запросов. Пожалуйста, подождите немного перед повторной попыткой.';
  }

  return rawError;
}

export const STATUS_RUSSIAN_MAP: Record<string, { label: string; icon: string; title: string }> = {
  queued: { label: 'В очереди', icon: '⏳', title: 'Задача ожидает свободного обработчика' },
  collecting: { label: 'Сбор данных', icon: '🔄', title: 'Получение метаданных и исходного кода' },
  analyzing: { label: 'Анализ', icon: '⚡', title: 'Выполнение локальных анализаторов и проверок' },
  scoring: { label: 'Расчёт', icon: '📊', title: 'Расчёт взвешенных оценок категорий' },
  completed: { label: 'Готово', icon: '✓', title: 'Анализ успешно завершён' },
  partial: { label: 'Частично', icon: '⚠', title: 'Анализ завершён с неполными данными от внешних источников' },
  failed: { label: 'Ошибка', icon: '✕', title: 'Не удалось завершить анализ' },
};
