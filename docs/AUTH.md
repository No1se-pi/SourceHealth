# Я ID и права SourceCraft

Это две разные задачи: **аутентификация пользователя SourceHealth** и
**авторизация к ресурсам SourceCraft**. OAuth token Я ID не является SourceCraft PAT.

## Реализованный Я ID flow

Использован официальный [Authorization Code flow с PKCE](https://yandex.ru/dev/id/doc/ru/codes/code-url).
В приложении Я ID настроить точный Redirect URI и разрешения получения identity.

1. Backend создаёт случайные state, verifier и browser token.
2. Redis хранит state/verifier 10 минут под HMAC browser token. Браузер получает
   только HttpOnly opaque cookie sh_oauth; verifier остаётся серверным.
3. Redirect на oauth.yandex.ru/authorize с response_type=code и PKCE S256.
4. Callback атомарно GETDEL потребляет pending record и constant-time проверяет state.
5. Backend обменивает code на token и читает identity через login.yandex.ru/info.
6. PostgreSQL upsert users.yandex_id. Новый случайный session token хранится в
   Redis под HMAC, browser получает sh_session. Старый session token инвалидируется.
7. OAuth token не сохраняется в БД, Redis session или браузере. Refresh token не нужен
   текущему use case: после получения identity продолжает жить наша session.
8. Logout удаляет server session и cookie. Потеря Redis завершает сессии, не теряет user.

Cookie: Secure по умолчанию, HttpOnly, SameSite=Lax, Path=/, без Domain. Lax нужен
для top-level возврата от внешнего OAuth. Mutating POST требует exact Origin ==
PUBLIC_ORIGIN; неправильный/отсутствующий Origin → 403. CORS по умолчанию закрыт.
Callback имеет фиксированный путь и перенаправляет только на /auth/callback, пользовательский
redirect URL не принимается. Просроченный/replayed state и второй callback отклоняются.

## Настройка

YANDEX_CLIENT_ID, YANDEX_CLIENT_SECRET, YANDEX_REDIRECT_URI, PUBLIC_ORIGIN,
SESSION_SECRET (случайная строка ≥32 символов), COOKIE_SECURE=true.
Незаполненная конфигурация даёт 503 auth_not_configured, не fake login.
Secret хранить в .env/secret manager; не коммитить. Rotation SESSION_SECRET
инвалидирует существующие сессии/pending state.

Для локального HTTP допустимы только localhost/127.0.0.1 и явный COOKIE_SECURE=false.
Готовый dev-набор в `.env.example` использует `http://127.0.0.1:5173` одновременно для
PUBLIC_ORIGIN и YANDEX_REDIRECT_URI; менять один адрес без второго нельзя.
Origin frontend и redirect backend должны совпадать через Vite proxy. См.
[DEPLOYMENT](DEPLOYMENT.md). Для публичного стенда только HTTPS Secure cookies.
Access logs reverse proxy должны исключать callback query: code/state не логировать.
Docker command Uvicorn запускается с --no-access-log.

## OPEN INTEGRATION QUESTION: SourceCraft bridge

Подтверждён официальный PAT/Bearer механизм SourceCraft API. **Не подтверждён**
официальный способ превратить Я ID identity/session в полномочия на список доступных
репозиториев конкретного пользователя. Нельзя выводить это из совпадающего email,
имени, slug или наличия token Я ID. Нельзя применять service PAT как права любого
вошедшего пользователя.

Нужно подтвердить у организаторов: supported delegated auth/token exchange, scopes,
mapping identity, list accessible repositories, проверки права читать/анализировать,
отзыв доступа. Если разрешён отдельный ввод PAT, это отдельное продуктово-безопасностное
решение: encrypted storage, scopes, revoke, audit и user consent. Сейчас такой flow не создан.

## Текущее ограничение доступа

API показывает только сохранённые verified-public repositories. Authenticated user
может запросить их анализ. Private/unknown repository и его report → 404. Force refresh
через HTTP запрещён. Это **не реализация анализа собственного закрытого repo из ТЗ**.
До bridge нельзя включать private clone/cache/evidence даже ради демо.

## Проверки

Контрактные тесты проверяют конфигурацию, cookies, state replay, PKCE, session и logout.
Интеграционные используют настоящий PostgreSQL/Redis и mocked Я ID HTTP. Они не
подтверждают реальную регистрацию приложения, scopes и успешный login пользователя.
Live acceptance: войти в браузере, проверить redirect, /me, logout, повтор callback,
затем пройти чек-лист [LIVE_ACCEPTANCE](LIVE_ACCEPTANCE.md). Операторские probe/accept
не автоматизируют браузерный OAuth и не являются доказательством этого сценария.
неверный Origin и отсутствие токенов в logs/network payload приложения.
