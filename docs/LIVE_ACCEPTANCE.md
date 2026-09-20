# Live Integration & Acceptance

Эта процедура отделяет проверку нашего кода на fixtures от работы с настоящим публичным
SourceCraft repository. Целевой репозиторий задаётся явно; discovery не выполняется.
PAT хранится только в локальном `.env` или окружении, не передаётся в аргументах, логи,
скриншоты и отчёты.

## 1. Preflight без инфраструктуры

```powershell
$env:SOURCECRAFT_PAT = '<local secret>'
python -m sourcehealth.application probe-sourcecraft `
  https://sourcecraft.dev/lct-hackaton-2026/case-18-repo-health-score-team-41
```

Команда не подключается к PostgreSQL, Redis или Docker. Она выполняет GET metadata и пяти
MVP resources через те же collectors, что worker, и печатает один JSON object. В нём нет
raw response, имён, email, descriptions, comments, release notes или значения PAT.

Коды завершения:

- `0`: metadata и все resources прочитаны полностью; пустой список считается полным ответом;
- `1`: metadata подтверждена, но ресурс partial, rate-limited или временно недоступен;
- `2`: не настроен PAT, неверен URL, metadata не подтверждена, отказано в доступе либо нарушен schema/pagination contract.

`authenticated=true` означает только успешный metadata GET с настроенным PAT. Это не
подтверждение private access или SourceCraft AppSec.

## 2. Инфраструктура и полный pipeline

В `.env` нужны `SOURCECRAFT_PAT`, `ANALYSIS_PROFILE=mvp-v1` и
`CODE_RUNTIME_ENABLED=true`. PostgreSQL, Redis, API и trusted `worker-code` должны быть
запущены по [DEPLOYMENT](DEPLOYMENT.md). Быстрая безопасная диагностика:

На Windows команда `worker-code` автоматически использует RQ `SimpleWorker`, поскольку
операционная система не предоставляет `fork`; на Linux используется обычный RQ Worker.

```powershell
python -m sourcehealth.application doctor
```

Диагностика показывает только наличие конфигурации и доступность DB/Redis. DSN, OAuth
identifiers и secrets не печатаются.

Полная приёмка использует существующие import/service, durable run, RQ dispatch, worker,
collectors, Docker runtime, scoring и persistence:

```powershell
python -m sourcehealth.application accept-public `
  https://sourcecraft.dev/lct-hackaton-2026/case-18-repo-health-score-team-41 `
  --timeout 900
```

Команда сама не поднимает контейнеры. Она ждёт только заданное время. Таймаут возвращает
exit 1 и оставляет durable run в текущем состоянии: оператор может проверить worker и
повторить наблюдение, не превращая живую задачу в failed. Exit 0 означает, что сохранённый
terminal run прошёл проверку инвариантов. Exit 1 означает partial/outage/failed/timeout или
нарушение acceptance invariant. Exit 2 означает configuration/auth/repository/DB/Redis error.

Проверяются профиль `mvp-v1`, фактический HEAD, ровно шесть category slots, пересчёт той же
score policy, связь repository/latest run, persisted JSON, Markdown, recommendations/evidence,
coverage и источник Security. `sourcecraft_appsec=NO_DATA` допустим и не заменяется local
SAST; local SAST остаётся `code_health`.

## 3. Opt-in тест живого контракта

```powershell
$env:SOURCEHEALTH_LIVE_REPO_URL = 'https://sourcecraft.dev/lct-hackaton-2026/case-18-repo-health-score-team-41'
python -m unittest tests.test_live_sourcecraft -v
```

Без обеих переменных тест пропускается. Он не проверяет точные counts: они меняются между
запусками. Он проверяет parse, availability, complete/partial semantics, даты и отсутствие
запрещённых полей в нормализованных facts.

## 4. UI и OAuth

Локальная конфигурация из `.env.example` использует один origin и callback
`http://127.0.0.1:5173`; для неё `COOKIE_SECURE=false`. Production использует HTTPS,
точный HTTPS callback/origin и `COOKIE_SECURE=true`.

OAuth не автоматизируется операторской командой. В браузере вручную проверить login,
callback, `/me`, import public URL, переход к analysis, историю последних запусков,
evidence/recommendations, Markdown download и logout. Повтор callback должен быть отклонён.
Build или mocked OAuth не считается browser acceptance.

## 5. Что сохранить в отчёте команды

Сохранить время, commit SHA, публичный URL, exit code и безопасный JSON summary. Не сохранять
PAT, `.env`, raw HTTP bodies, callback query, source snippets и персональные данные. Если PAT
не предоставлен, итоговая запись должна быть точной: `LIVE SOURCECRAFT: NOT RUN — credentials not provided`.
