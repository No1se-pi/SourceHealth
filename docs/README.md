# Документация SourceHealth

SourceHealth — сервис здоровья репозиториев SourceCraft для ЛЦТ 2026.
Текущий этап: **архитектурный фундамент**, а не готовый продукт с шестью оценками.
Ни `null` Score, ни успешный сбор metadata не означают «проект здоров».

## Начать работу

1. Прочитать [требования и статус](REQUIREMENTS.md): что обязано попасть в итоговый продукт.
2. Прочитать [архитектуру](ARCHITECTURE.md) и [модель предметной области](DOMAIN_MODEL.md).
3. Запустить проект по [DEPLOYMENT.md](DEPLOYMENT.md), выполнить [TESTING.md](TESTING.md).
4. Выбрать свою зону из [DEVELOPMENT.md](DEVELOPMENT.md) и задачу из [ROADMAP.md](ROADMAP.md).
5. Перед изменением публичной границы прочитать соответствующий [ADR](adr/README.md).

## Маршруты для команды

| Участник | Читать в первую очередь | Первая независимая задача |
|---|---|---|
| Frontend | [FRONTEND](FRONTEND.md), [API](API.md), [DOMAIN_MODEL](DOMAIN_MODEL.md) | Экран категорий, evidence и состояний по существующим DTO |
| Анализаторы | [ANALYTICS](ANALYTICS.md), [DEVELOPMENT](DEVELOPMENT.md), [METRICS](METRICS.md) | IssuesCollector + IssuesAnalyzer на fixture, без HTTP/router/БД изменений |
| Backend / интеграция / ML | [BACKEND](BACKEND.md), [SOURCECRAFT](SOURCECRAFT.md), [DATABASE](DATABASE.md), [JOBS_AND_CACHE](JOBS_AND_CACHE.md) | Подтвердить AppSec API и SourceCraft authorization, подключить новую пару collector/analyzer |

## Полный каталог

- [REQUIREMENTS](REQUIREMENTS.md) — ТЗ → компоненты → критерии приёмки.
- [ARCHITECTURE](ARCHITECTURE.md) — границы модулей, data flow, composition roots.
- [DOMAIN_MODEL](DOMAIN_MODEL.md) — identity, run, availability, evidence, versioning.
- [API](API.md) — HTTP, DTO, сортировка, pagination, ошибки.
- [BACKEND](BACKEND.md) — точки расширения и правила application layer.
- [DATABASE](DATABASE.md) — таблицы, связи, транзакции, миграции и retention.
- [SOURCECRAFT](SOURCECRAFT.md) — проверенные методы и открытые вопросы интеграции.
- [AUTH](AUTH.md) — Я ID, сессии, CSRF, отдельные права SourceCraft.
- [ANALYTICS](ANALYTICS.md) — шесть категорий и контракт анализатора.
- [SCORING](SCORING.md) — детерминизм, evidence, отсутствующие данные.
- [JOBS_AND_CACHE](JOBS_AND_CACHE.md) — lifecycle, дедупликация, восстановление, scheduler.
- [SECURITY](SECURITY.md) — sandbox, доступ, недоверенные данные и секреты.
- [FRONTEND](FRONTEND.md) — React, API boundary, типы, сценарии разработки.
- [REPORTING](REPORTING.md) — детерминированный Markdown и будущий PDF.
- [ML](ML.md) — план экспериментов и границы ML/LLM.
- [TESTING](TESTING.md) — unit, PostgreSQL/Redis, контракты, большие репозитории.
- [DEPLOYMENT](DEPLOYMENT.md) — воспроизводимый локальный запуск и эксплуатация.
- [DEVELOPMENT](DEVELOPMENT.md) — совместная работа, ownership, review и примеры.
- [ROADMAP](ROADMAP.md) — последовательность P0/P1/P2 и зависимые решения.
- [METRICS](METRICS.md) — сохранённый точный справочник Git-метрик.
- [ADR](adr/README.md) — принятые архитектурные решения.

## Как читать статусы

**Работает** — реализованная функция с указанной проверкой. **Foundation** — рабочая
граница, на которую ещё нужно добавить бизнес-логику. **Planned** — кода функции нет.
**OPEN INTEGRATION QUESTION** — внешний механизм ещё не подтверждён; это не задача
«догадаться об endpoint». Проверка с mock подтверждает наш код, не доступность внешнего сервиса.

Документация обновляется в том же PR, что и поведение. Точные результаты последней
проверки фиксируются в [FOUNDATION_CLOSURE](FOUNDATION_CLOSURE.md); исходная поставка
15 сентября — [DELIVERY.md](DELIVERY.md). Это результаты конкретных проверок,
а не постоянная гарантия или подтверждение готовности всех продуктовых категорий.
