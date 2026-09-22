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
  authentication_required: 'Требуется вход через Яндекс ID для выполнения этого действия.',
  invalid_sourcecraft_url: 'Укажите корректную ссылку вида https://sourcecraft.dev/org/repo.',
  public_repository_unverified: 'Не удалось подтвердить публичный статус репозитория в SourceCraft.',
  repository_not_found: 'Репозиторий не найден в реестре платформы.',
  analysis_not_found: 'Запись анализа не найдена.',
  report_not_ready: 'Отчёт ещё формируется или анализ завершился с ошибкой.',
  unauthorized: 'Требуется авторизация.',
  forbidden: 'Недостаточно прав для выполнения действия.',
  rate_limited: 'Слишком много запросов. Пожалуйста, подождите минуту.',
  service_unavailable: 'Сервис временно недоступен. Попробуйте обновить через пару минут.',
  request_failed: 'Не удалось получить ответ от сервиса. Проверьте соединение.',
};

export const ErrorState: React.FC<ErrorStateProps> = ({
  error,
  title = 'Внимание',
  onRetry,
  className = '',
}) => {
  let userMessage = 'Не удалось загрузить данные. Повторите попытку позже.';
  let requestId: string | null = null;
  let status: number | null = null;

  if (error instanceof ApiError) {
    requestId = error.requestId || null;
    status = error.status;
    userMessage = ERROR_MESSAGES[error.code] || 'Не удалось выполнить запрос к платформе. Попробуйте повторить операцию.';
  }

  return (
    <div
      role="alert"
      className={`sc-inline-error ${className}`.trim()}
    >
      <div className="sc-error-content">
        <span className="sc-error-icon" aria-hidden="true">
          !
        </span>
        <div className="sc-error-text-block">
          <div className="sc-error-title-row">
            <span className="sc-error-title">{title}</span>
            {requestId && (
              <span className="sc-error-req-id" title="Идентификатор запроса для службы поддержки">
                ID: {requestId}
              </span>
            )}
            {status && status !== 500 && (
              <span className="sc-error-status-badge">HTTP {status}</span>
            )}
          </div>
          <p className="sc-error-msg">{userMessage}</p>
        </div>
      </div>
      {onRetry && (
        <div className="sc-error-actions">
          <Button size="sm" variant="secondary" onClick={onRetry}>
            Повторить
          </Button>
        </div>
      )}
    </div>
  );
};
