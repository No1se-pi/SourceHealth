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

## Подтверждённый прогон 20.09.2026

На commit `8516317` проверен публичный repository
`https://sourcecraft.dev/lct-hackaton-2026/case-18-repo-health-score-team-41`:

- `probe-sourcecraft`: exit 0, authenticated=true, все шесть collectors complete;
- `tests.test_live_sourcecraft`: passed на настоящем API;
- `accept-public`: exit 0, overall=ok, analysis `2e7e495a-92c5-47fd-9383-fa029e70405e`;
- persisted HEAD `0f801b94b3ec4023dc540cd815367608df3f8568`, Score 51.83,
  nominal coverage 60%, четыре scored categories;
- worker-code завершил job успешно через реальный Docker Git/SAST runtime.

Terminal status остаётся `partial`: официальный SourceCraft AppSec не подключён, а в snapshot
этого repository не найдено поддерживаемых code files для числового Code Health. Это не
ошибка transport или worker. Raw responses и PAT не сохранялись. Browser OAuth этим
прогоном не проверялся.

## Повторная приёмка policy v1.2 — 21.09.2026

На SourceCraft HEAD `aa225141a057fb0ad28c49e6bc37409f8d8903fd` выполнены настоящий
`probe-sourcecraft`, opt-in contract test и полный `accept-public` через PostgreSQL,
Redis/RQ, Docker Git/SAST runtime и persisted report. Итоговый analysis
`bf27205e-899f-4a22-902d-dacfe9860a5b`: `overall=ok`, terminal status `partial`,
Health 69.35, nominal coverage 65%, policy `mvp-score-v1.2`. Категории: Documentation
90, CI/CD 25, Activity 55.24, Code Health 97.72; Issues — наблюдаемый пустой набор и
score=null, Security — NO_DATA. Это оценка настоящего SourceHealth mirror.

Во время запуска обнаружен реальный RQ shutdown race: job сохранял статус `queued`, но
отсутствовал в очереди. Dispatcher теперь проверяет фактическое присутствие ID и под
per-run Redis lock восстанавливает доставку из durable DB row. Тот же зависший run был
восстановлен (`enqueued=1`) и успешно завершил acceptance; добавлен integration regression.

Bounded global discovery был ограничен десятью элементами: 9 repositories импортированы,
одна ошибка изолирована, batch вернул partial. Девять jobs затем завершились на trusted
worker; calibration record находится в [MANDATORY_100_CLOSURE](MANDATORY_100_CLOSURE.md).
