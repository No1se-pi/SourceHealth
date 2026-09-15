# Результат архитектурного этапа

Дата проверки: 15 сентября 2026. Рабочая ветка foundation: Dev-No1se.
Этот документ описывает поставленный фундамент и границы приёмки, не заменяет roadmap.

## A. Исходное состояние

Существовали core context/result/protocol, AnalysisRunner, GitCollector и чистый
GitActivityAnalyzer, адаптеры, local SAST со standalone JSON rules, CLI/SARIF/container
workflow, Ruff/CI, 97 тестов, ARCHITECTURE/METRICS и examples/legacy. Они сохранены.

## B. Найденные ограничения

Runner требовал существующую папку; repository identity была локальным path; не было
публичного API/DB/queue/frontend и lifecycle. Исполнение ok/partial/error не объясняло
доступность данных. Для Security требовалось отделить SourceCraft AppSec от local SAST.
Команде не хватало общего API/DB/ownership контракта и интеграционного checklist.

При заключительной проверке также устранены незавершённые conflict markers LICENSE
(сохранён подготовленный в рабочей копии список трёх авторов), CRLF в генерируемом
OpenAPI/lock и одновременное отображение error/loading на странице repo.

## C–D. Дерево и изменения

Полное назначение каталогов — [ARCHITECTURE](ARCHITECTURE.md). Добавлены:
core/domain; application services/jobs/cache/connections/CLI; storage models/database;
integrations/sourcecraft client/collectors; auth; api DTO/routes; scoring engine;
recommendation/ML interfaces; runtime adapter; Markdown; typed settings/logging.
Добавлены migrations/0001, Dockerfile/Compose/.env.example/locks, React frontend,
OpenAPI export, foundation/integration/live-opt-in tests, docs и семь ADR.

Изменены context/result/runner и адаптеры с сохранением старых API; единая проверка
SourceCraft URL используется runtime и identity. Обновлены README, CI, pyproject и
git attributes/ignore. Старую APPLY_CHANGES памятку пометили исторической.
Исходные Git/scanner engines, JSON rules и examples/legacy не удалены.

## E. Зависимости

Server extras: FastAPI/uvicorn для HTTP, SQLAlchemy/psycopg/Alembic для PostgreSQL,
redis/RQ для очереди и cache/session, httpx для external HTTP, pydantic-settings для
typed config. CLI-only по-прежнему обходится без server extras. Runtime snapshot
зафиксирован requirements-server.lock; frontend React/React Router/TypeScript/Vite
и openapi-typescript зафиксированы npm lock. ML/LLM/PDF SDK не добавлены.

## F. Data flow

RepositoryRef → collectors/API или явно выбранный временный runtime → AnalysisContext
→ analyzers + evidence → scoring/recommendation boundaries → public report 3.0
→ PostgreSQL → FastAPI → React/Markdown. Рабочий фоновый профиль API-only;
code runtime пока используется отдельно через сохранённый workflow.

## G–I. DB, HTTP и lifecycle

Три таблицы: users, repositories, analysis_runs; стабильные поля relational,
изменяемая аналитика JSONB, partial unique active run index и leaderboard indexes.
Одна Alembic initial revision. Детали — [DATABASE](DATABASE.md).

Реализованы health, repositories list/detail/latest, POST analysis, analysis detail,
Markdown, Я ID login/callback/logout и me — [API](API.md). API отдаёт только public repo.
Lifecycle: queued → collecting → analyzing → scoring → completed/partial;
любой active → failed. Terminal run не переоткрывается.

## J. Дедупликация и кэш

PG row lock + partial UNIQUE repository/profile, durable queued rows и RQ unique job ID.
Worker PG advisory lock предотвращает duplicate execution. Dispatcher/recovery
обрабатывают Redis/process failures. Platform cache отдельно от code fingerprint;
готовый report имеет ограниченную freshness. Code cache primitive есть, подключение
фонового code profile ещё предстоит. Подробности — [JOBS_AND_CACHE](JOBS_AND_CACHE.md).

## K–L. SourceCraft и auth

Официальная Swagger проверена, реализованы GET client, bounded retries/pagination и
public metadata collector. AppSec результатов в изученной публичной спецификации не
найдено: отдельная boundary возвращает NO_DATA. /secrets не используется как scanning API.
SourceCraft [checklist](SOURCECRAFT.md) содержит точные методы и открытые вопросы.

Я ID Authorization Code/PKCE/state/server sessions реализованы. HTTP Я ID в тестах
mocked. Реальный вход после регистрации OAuth приложения не проверен. Подтверждённый
Я ID → SourceCraft authorization bridge отсутствует; private/own-repository flow
не заявлен готовым. Service PAT не подменяет пользовательские права — [AUTH](AUTH.md).

## M. Сознательно не реализовано

Полная бизнес-аналитика шести категорий, финальная численная policy/weights,
recommendation rules, private access bridge, массовый discovery каталога, code worker
с точным SHA/disk quota/cache, ML/LLM, PDF, финальный дизайн и cloud deployment.
Без формулы Score остаётся null, не fake 0/100. Это объём foundation, согласованный
архитектурным промптом; обязательные будущие сценарии ТЗ перечислены в ROADMAP.

## N. Проверки

- Полный unittest набор с настоящими PostgreSQL/Redis: 122 теста, 120 выполнены,
  2 ожидаемых skip — Unix-only FIFO на Windows и live SourceCraft opt-in.
- 8 integration scenarios: concurrency/dedupe, DB constraint, durable delivery,
  RQ execution, persisted report/cache, recovery guard, private deny/Markdown, OAuth session flow.
- Ruff, editable server install и pip check; TypeScript/Vite build и генерация types.
- Alembic upgrade/check на настоящем PostgreSQL и downgrade/upgrade на отдельной test DB.
- Compose config/build/up, HTTP health и пустой public list.
- Ссылки документации и diff whitespace/conflict checks проверяются перед merge.

В начале повторной проверки Docker Desktop был выключен: integration setup получил
connection refused. После запуска сервисов полный набор прошёл повторно; первый запуск
не считается успешным. Browser automation недоступна из-за ошибки sandboxPolicy:
визуальная приёмка не выполнена. Live SourceCraft/Я ID, крупный repo на платформе и
cloud deployment не проверены. GitHub CI статус следует смотреть в PR отдельно от local checks.

## O. Что команда может делать независимо

Frontend — category/evidence/recommendation UI по generated DTO. Analyzer developer —
documentation/issues/CI collectors/analyzers с fixtures и метриками. Backend —
AppSec/auth bridge, versioned policy, runtime/profile/cache и операционная устойчивость.
Точки синхронизации: core, HTTP DTO, DB schema и ADR. Начало работы —
[docs/README](README.md) и [DEVELOPMENT](DEVELOPMENT.md).
