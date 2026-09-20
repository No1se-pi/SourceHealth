# Архитектура SourceHealth

Модульный монолит для трёх разработчиков. Один Python package, один HTTP API,
одна PostgreSQL БД. API и worker — разные процессы одного приложения. Frontend
общается только по HTTP. Анализаторы не знают о БД и UI.

## Data flow

```text
RepositoryRef
  ├─ SourceCraftClient → collectors → очищенные platform facts
  └─ AnalysisRuntime → временный clone → локальные collectors/analyzers
                       (только для профилей, которым нужны файлы)
                              ↓
                       AnalysisContext
                              ↓
                Analyzers → AnalyzerResult + Evidence
                              ↓
               ScoringEngine ← versioned ScoringPolicy
                              ↓
           Recommendation rules / optional ContextModel
                              ↓
                 AnalysisReport public JSON 3.0
                              ↓
             PostgreSQL AnalysisRun + leaderboard projection
                              ↓
                FastAPI /api/v1 → React / Markdown
```

Фоновый профиль `platform-v1` использует API metadata и availability AppSec.
Профиль `code-v1` дополнительно вызывает `AnalysisRuntime` один раз для Git и SAST:
`DockerAnalysisRuntime` → прежний clone/scan workflow → `runtime_results` → общие checks.
Он доставляется в отдельную очередь `analysis-code`, которую обслуживает trusted
`worker-code`. Обычный Compose worker не получает доступ к Docker. Runtime error
оставляет platform checks и переводит code checks в NO_DATA; отчёт сохраняется partial.
`mvp-v1` расширяет тот же pipeline collectors Issues/CI/PR/contributors/releases и
snapshot documentation/debt. `MVPPolicy` рассчитывает шесть category slots, overall
при достаточном coverage и рекомендации. Security остаётся nullable AppSec boundary.

## Дерево

```text
sourcehealth/
  core/                 identity, context, result, evidence, lifecycle
  git/                  прежние collector, models, чистый activity analyzer
  sast/                 прежний local scanner, rules, SARIF, Docker workflow
  analyzers/            адаптеры и независимые анализаторы
  integrations/
    sourcecraft/        HTTP client, Collector, AppSec boundary
  scoring/              policy contract, validation, nullable baseline
  recommendations/      rule contract и проверка evidence refs
  ml/                   ContextModel / EvidenceExplainer interfaces
  application/          commands, lifecycle, queue, cache, scheduler
  storage/              SQLAlchemy модели и session factory
  auth/                 Я ID / PKCE / server sessions
  api/                  composition root, dependencies, routers/, HTTP DTO, errors
  runtime.py            AnalysisRuntime и Docker adapter
  runtime_results.py    безопасный legacy 1.0 → AnalyzerResult converter
  markdown.py           public report → Markdown
  runner.py             execution независимых analyzers
  reporting.py          сохранённый CLI/SARIF compatibility layer
  settings.py           typed process settings
frontend/               React + TypeScript + Vite, generated HTTP types
migrations/             Alembic initial schema
tests/                  прежние unit + foundation + opt-in integration
scripts/                экспорт OpenAPI
docs/                   общий источник договорённостей и ADR
examples/legacy/        сохранённые исторические прототипы
```

## Границы зависимостей

- Core использует стандартную библиотеку и Git-модель Commit; не импортирует runtime,
  HTTP/ORM/cache. Settings доступны composition roots.
- Collectors имеют I/O, analyzers интерпретируют готовые факты либо читают разрешённый
  read-only workspace; запуск кода проекта запрещён.
- Scoring детерминирован, без HTTP/БД/Docker и popularity-подмены Health.
- Application соединяет инструменты и управляет транзакциями/status.
- Storage не вызывает analyzers. Router не рассчитывает метрики.
- Runtime изолирует Docker-specific operations; AnalyzerResult не содержит Docker state.
- ML/LLM получают numeric features/evidence, не имеют полномочий на I/O или Score.

## Сохранённая основа

Цепочка `Collectors → AnalysisContext → Analyzers → AnalyzerResult → AnalysisRunner →
AnalysisReport` сохранена. GitCollector собирает историю один раз. Git adapter
передаёт commits прежнему чистому анализатору. SAST adapter сохраняет counters,
findings, configuration, rules digest; `complete=false` становится partial.

Runner проверяет уникальность имён, matching result.analyzer и сериализуемость,
копирует результаты и изолирует ошибки анализаторов. KeyboardInterrupt/SystemExit
не поглощаются. `analyze(path)` сохранён, `analyze_context(context)` добавлен для
API-only и смешанных сценариев. Пустой набор checks означает отсутствие проверок,
а не хорошее здоровье, даже если прежний CLI complete равен true.

## Версии и совместимость

Локальный JSON 2.0 сохраняет repository.path и не передаётся frontend. Public JSON
3.0 требует RepositoryRef и дополняет report scoring/recommendations. SAST JSON 1.0
и SARIF используют прежний to_legacy_report. CLI exit codes 0/1/2 сохранены.
Standalone rules не загружаются из анализируемого репозитория автоматически.

В текущем checkout пакет sourcehealth.sast lowercase; прежний rename с
sourcehealth.SAST выполнен раньше. Alias не вводится из-за конфликтов на Windows.
examples/legacy сохранён, но не является точкой расширения продукта.

## Persistence и delivery

POST создаёт/reuses run в транзакции. PostgreSQL row lock + partial unique index
дают single-flight repository/profile. queued — durable outbox. Dispatcher
отправляет UUID в RQ; worker берёт advisory lock и проводит lifecycle. Повторная
доставка не повторяет законченный run. Подробнее: [JOBS_AND_CACHE](JOBS_AND_CACHE.md).

## Ограничения

Не подключены official AppSec, private permissions, полный live каталог
SourceCraft repo, ML/LLM, PDF и production deployment. AppSec API и Я ID → SourceCraft
authorization bridge открыты. GitCollector собирает список истории в память;
streaming/incremental путь нужен после измерений, shallow clone не подменяет историю.
Масштабирование начинается с workers, rate limits и индексов. Выделение микросервисов
или смена executor требует доказанной необходимости и ADR.
