import React from 'react';
import { ApiError } from '../../api/client';
import { Button } from './Button';

interface ErrorStateProps {
  error: unknown;
  title?: string;
  onRetry?: () => void;
  className?: string;
}

const ERROR_MESSAGES: Record<string, string> = {
  repository_not_found: 'Репозиторий не найден или к нему нет доступа.',
  analysis_not_found: 'Сессия анализа не найдена.',
  report_not_ready: 'Отчёт ещё формируется или анализ завершился с ошибкой.',
  unauthorized: 'Требуется авторизация через Яндекс ID.',
  forbidden: 'Действие запрещено или сессия недействительна.',
  rate_limited: 'Слишком много запросов. Пожалуйста, подождите.',
  service_unavailable: 'Сервер временно недоступен. Попробуйте позже.',
  request_failed: 'Не удалось выполнить запрос к серверу.',
};

export const ErrorState: React.FC<ErrorStateProps> = ({
  error,
  title = 'Произошла ошибка',
  onRetry,
  className = '',
}) => {
  let userMessage = 'Сервис временно недоступен. Пожалуйста, повторите попытку позже.';
  let errorCode: string | null = null;
  let requestId: string | null = null;
  let status: number | null = null;

  if (error instanceof ApiError) {
    errorCode = error.code;
    requestId = error.requestId || null;
    status = error.status;
    userMessage = ERROR_MESSAGES[error.code] || `Ошибка запроса (${error.code})`;
  } else if (error instanceof Error) {
    // Only use message if it doesn't leak stack/internals
    if (error.message && !error.message.includes('at ') && !error.message.includes('\n')) {
      userMessage = error.message;
    }
  }

  return (
    <div
      role="alert"
      className={className}
      style={{
        padding: 'var(--sh-space-5)',
        border: '1px solid var(--sh-health-danger-border)',
        borderRadius: 'var(--sh-radius-md)',
        backgroundColor: 'var(--sh-health-danger-bg)',
        color: 'var(--sh-text-primary)',
        margin: 'var(--sh-space-4) 0',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--sh-space-3)' }}>
        <span
          style={{
            fontSize: '1.2rem',
            lineHeight: 1,
            color: 'var(--sh-health-danger)',
          }}
          aria-hidden="true"
        >
          ⚠
        </span>
        <div style={{ flex: 1 }}>
          <h4
            style={{
              margin: '0 0 var(--sh-space-1) 0',
              color: 'var(--sh-health-danger)',
              fontSize: '1rem',
              fontWeight: 600,
            }}
          >
            {title}
          </h4>
          <p style={{ margin: 0, fontSize: '0.92rem', color: 'var(--sh-text-primary)' }}>
            {userMessage}
          </p>
          {(errorCode || requestId || status) && (
            <div
              style={{
                marginTop: 'var(--sh-space-2)',
                fontSize: '0.78rem',
                color: 'var(--sh-text-muted)',
                fontFamily: 'var(--sh-font-mono)',
              }}
            >
              {status && <span>HTTP {status} · </span>}
              {errorCode && <span>Код: {errorCode}</span>}
              {requestId && <span> · Request ID: {requestId}</span>}
            </div>
          )}
          {onRetry && (
            <div style={{ marginTop: 'var(--sh-space-3)' }}>
              <Button size="sm" variant="outline" onClick={onRetry}>
                Повторить попытку
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
