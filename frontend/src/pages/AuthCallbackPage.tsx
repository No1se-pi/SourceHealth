import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, type User } from '../api/client';
import { Card } from '../components/common/Card';
import { getButtonStyles } from '../components/common/Button';
import { LoadingState } from '../components/common/LoadingState';

export const AuthCallbackPage: React.FC = () => {
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    let active = true;
    api
      .me()
      .then((data) => {
        if (active) {
          setUser(data);
          setStatus('success');
        }
      })
      .catch(() => {
        if (active) {
          setStatus('error');
        }
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div style={{ maxWidth: '520px', margin: 'var(--sh-space-8) auto' }}>
      <Card title="Авторизация через Яндекс ID">
        {status === 'loading' && (
          <LoadingState message="Проверяем статус сессии…" />
        )}

        {status === 'success' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-4)' }}>
            <div
              style={{
                padding: 'var(--sh-space-3) var(--sh-space-4)',
                backgroundColor: 'var(--sh-health-good-bg)',
                border: '1px solid var(--sh-health-good-border)',
                borderRadius: 'var(--sh-radius-sm)',
                color: 'var(--sh-health-good)',
                fontWeight: 500,
              }}
            >
              ✓ Вход успешно выполнен. Сессия активна.
            </div>
            {user && (
              <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--sh-text-secondary)' }}>
                ID пользователя: <code style={{ color: 'var(--sh-text-primary)' }}>{user.id}</code>
              </p>
            )}
            <p style={{ margin: 0, fontSize: '0.9rem' }}>
              Теперь вы можете запускать анализ открытых репозиториев SourceCraft.
            </p>
            <div>
              <Link to="/" className="btn-link" style={getButtonStyles('primary', 'md')}>
                К списку репозиториев
              </Link>
            </div>
          </div>
        )}

        {status === 'error' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sh-space-4)' }}>
            <div
              style={{
                padding: 'var(--sh-space-3) var(--sh-space-4)',
                backgroundColor: 'var(--sh-health-danger-bg)',
                border: '1px solid var(--sh-health-danger-border)',
                borderRadius: 'var(--sh-radius-sm)',
                color: 'var(--sh-health-danger)',
                fontWeight: 500,
              }}
            >
              ⚠ Сессия недоступна или произошла ошибка входа.
            </div>
            <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--sh-text-secondary)' }}>
              Возможно, время сессии истекло или cookies заблокированы браузером.
            </p>
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
              <a href="/api/v1/auth/yandex/login" className="btn-link" style={getButtonStyles('primary', 'md')}>
                Повторить вход
              </a>
              <Link to="/" className="btn-link" style={getButtonStyles('secondary', 'md')}>
                На главную
              </Link>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
};
