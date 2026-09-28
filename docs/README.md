# Документация SourceHealth

- [Руководство по продукту (PRODUCT_GUIDE)](PRODUCT_GUIDE.md) — исчерпывающее описание всех 34 разделов продукта
- [Чек-лист финальной сдачи (SUBMISSION_CHECKLIST)](SUBMISSION_CHECKLIST.md) — сводный контрольный список готовности
- [Сценарий демонстрации (DEMO)](DEMO.md) и [видеоскрипт (VIDEO_SCRIPT)](VIDEO_SCRIPT.md) — 14-шаговый маршрут приёмки
- [Синхронизация каталога и адаптивный планировщик](CATALOG_SYNC.md)
- [Достоверность анализа: фаза 1](ANALYSIS_CORRECTNESS_PHASE1.md)
- [Углублённая аналитика репозитория](DEEP_ANALYTICS.md)
- [Publicity, Compare и Integrity](BONUS_STARS_CORE.md)
- [Профиль, отслеживание и хранение PAT](PROFILE.md)
- [Yandex AI: grounded-отчёты](YANDEX_AI.md)
- [Публичный API и README badge](DEVELOPERS_API.md)
- [Масштабирование и concurrency](SCALING.md)

SourceHealth — сервис здоровья репозиториев SourceCraft для ЛЦТ 2026.
Текущий этап: **Final Release Product** — official AppSec для запуска с пользовательским PAT;
детерминированный численный scoring `mvp-score-v1.2` (6 категорий), рекомендации, Yandex AI (Flash, Lite, Pro),
глубокая Git-аналитика, Bus-фактор, Integrity, сравнение репозиториев (/compare), профиль (/profile), достижения,
динамические SVG-бейджи и поддержка репозиториев до 10 000 файлов.
Ни `null` Score, ни успешный сбор metadata не означают «проект здоров».

## Начать работу

1. Прочитать [руководство по продукту](PRODUCT_GUIDE.md) и [требования](REQUIREMENTS.md).
2. Прочитать [архитектуру](ARCHITECTURE.md) и [методологию скоринга](SCORING.md).
3. Запустить проект по [DEPLOYMENT.md](DEPLOYMENT.md), выполнить [TESTING.md](TESTING.md).
4. Ознакомиться со сценарием демонстрации [DEMO.md](DEMO.md) и [чек-листом сдачи](SUBMISSION_CHECKLIST.md).
5. Перед изменением публичной границы прочитать соответствующий [ADR](adr/README.md).

## Полный каталог

- [PRODUCT_GUIDE](PRODUCT_GUIDE.md) — единое руководство по всей функциональности платформы.
- [SUBMISSION_CHECKLIST](SUBMISSION_CHECKLIST.md) — официальный чек-лист готовности к сдаче.
- [REQUIREMENTS](REQUIREMENTS.md) — ТЗ → компоненты → критерии приёмки.
- [ARCHITECTURE](ARCHITECTURE.md) — границы модулей, data flow, composition roots.
- [DOMAIN_MODEL](DOMAIN_MODEL.md) — identity, run, availability, evidence, versioning.
- [API](API.md) — HTTP, DTO, сортировка, pagination, ошибки.
- [DEVELOPERS_API](DEVELOPERS_API.md) — интеграция по REST API и генерация README SVG-бейджей.
- [BACKEND](BACKEND.md) — точки расширения и правила application layer.
- [DATABASE](DATABASE.md) — таблицы, связи, транзакции, миграции и retention.
- [SOURCECRAFT](SOURCECRAFT.md) — проверенные методы и интерфейсы интеграции.
- [AUTH](AUTH.md) — Я ID, сессии, CSRF, отдельные права SourceCraft.
- [ANALYTICS](ANALYTICS.md) — шесть категорий и контракт анализатора.
- [SCORING](SCORING.md) — детерминизм, evidence, отсутствующие данные.
- [DEEP_ANALYTICS](DEEP_ANALYTICS.md) — глубокая аналитика коммитов, владения и Bus-фактора.
- [YANDEX_AI](YANDEX_AI.md) — интеграция с моделями Yandex AI и grounding validation.
- [BONUS_STARS_CORE](BONUS_STARS_CORE.md) — сравнение репозиториев, integrity-аудит, publicity.
- [PROFILE](PROFILE.md) — профиль разработчика, сессионный PAT и достижения.
- [JOBS_AND_CACHE](JOBS_AND_CACHE.md) — lifecycle, дедупликация, восстановление, scheduler.
- [SECURITY](SECURITY.md) — sandbox, доступ, недоверенные данные и секреты.
- [FRONTEND](FRONTEND.md) — React, API boundary, типы, сценарии разработки.
- [REPORTING](REPORTING.md) — детерминированный Markdown и аудит.
- [SCALING](SCALING.md) — модель безопасной конкурентности и масштабирования воркеров.
- [TESTING](TESTING.md) — unit, PostgreSQL/Redis, контракты, большие репозитории.
- [DEPLOYMENT](DEPLOYMENT.md) — воспроизводимый локальный запуск и эксплуатация.
- [DEVELOPMENT](DEVELOPMENT.md) — совместная работа, ownership, review и примеры.
- [ROADMAP](ROADMAP.md) — последовательность этапов развития и дорожная карта.
- [LIVE_ACCEPTANCE](LIVE_ACCEPTANCE.md) — probe, полный live pipeline, коды выхода и чек-лист приёмки.
- [DEMO](DEMO.md) — полный 14-шаговый сценарий показа и операторские правила.
- [VIDEO_SCRIPT](VIDEO_SCRIPT.md) — покадровый сценарий для видеодемонстрации.
- [FINAL_RELEASE_ACCEPTANCE](FINAL_RELEASE_ACCEPTANCE.md) — сводный статус release gates.
- [METRICS](METRICS.md) — сохранённый точный справочник Git-метрик.
- [ADR](adr/README.md) — принятые архитектурные решения.

## Как читать статусы

**Работает** — реализованная функция с указанной проверкой. **Foundation** — рабочая
граница, на которую ещё нужно добавить бизнес-логику. **Planned** — кода функции нет.
**OPEN INTEGRATION QUESTION** — внешний механизм ещё не подтверждён.

Документация обновляется в том же PR, что и поведение. Актуальный статус всех проверок
фиксируется в [FINAL_RELEASE_ACCEPTANCE](FINAL_RELEASE_ACCEPTANCE.md) и [MANDATORY_ACCEPTANCE_MATRIX](MANDATORY_ACCEPTANCE_MATRIX.md).
