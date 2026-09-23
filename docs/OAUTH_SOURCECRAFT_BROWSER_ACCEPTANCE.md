# Реальная browser-приёмка Yandex ID → SourceCraft

Этот журнал отделяет ручную live-приёмку от mock browser fixtures. Пароли, OAuth query string, PAT, cookies и персональные данные сюда не записываются.

## Статус

**BLOCKED — нужен ручной вход владельца через реальный Yandex ID и настоящий SourceCraft PAT.** В текущем окружении OAuth client id/secret и production callback не настроены; mock callback не считается PASS.

## Чек-лист владельца

1. Запустить локальный стенд с `PUBLIC_ORIGIN=http://127.0.0.1:5173`, `COOKIE_SECURE=false`, callback `http://127.0.0.1:5173/api/v1/auth/yandex/callback`, случайными `SESSION_SECRET` (≥32 символа) и независимым `SOURCECRAFT_CREDENTIAL_KEY`.
2. Анонимно открыть приложение: `GET /api/v1/me` возвращает 401, показывается кнопка входа.
3. Нажать «Войти через Яндекс ID», убедиться в переходе на `oauth.yandex.ru`, выполнить вход вручную и вернуться на `/auth/callback`.
4. Проверить `GET /api/v1/me` → 200 и UUID пользователя.
5. На `/sourcecraft` вручную вставить PAT. Проверить `POST /api/v1/sourcecraft/connection` → 200, очищенное поле, `connected=true`, `expires_in>0`. PAT не должен быть в URL, storage, console или логах.
6. Загрузить организации, выбрать собственный public repository, запустить анализ и дождаться `queued → collecting → analyzing → scoring → terminal`.
7. Проверить шесть категорий, честные `NO_DATA`/`partial`, evidence, recommendations, history и скачивание Markdown.
8. Выйти: logout успешен, затем `/api/v1/me` → 401 и connection текущей сессии недействительна.
9. Повторить использованный OAuth callback/state: replay должен быть отклонён и не создавать новую сессию.

## Evidence после ручного прогона

Записать только дату, безопасные HTTP статусы, analysis id и публичный URL репозитория. Не сохранять credential, callback URL, cookies, email или screenshots с секретами.
