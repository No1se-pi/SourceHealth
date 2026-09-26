# Yandex ID → SourceCraft browser acceptance

## Procedure

1. Открыть production `https://sourcehealth.tech`; anonymous `/api/v1/me` должен вернуть 401.
2. Нажать Yandex ID и выполнить вход вручную; пароль и callback query не записывать.
3. Проверить `/api/v1/me` → 200, затем подключить SourceCraft PAT вручную.
4. Проверить connection status, organization listing, собственный public repository, analysis,
   history, evidence/recommendations, Markdown download и logout.
5. После logout `/api/v1/me` должен вернуть 401; callback/state replay должен быть отклонён.

PAT не должен попадать в URL, local/session storage, console, logs или screenshots.

## Last verified

Заполняется владельцем после ручного browser run: дата, безопасные HTTP статусы, public URL
и analysis id. Credentials и персональные данные сюда не записываются.
