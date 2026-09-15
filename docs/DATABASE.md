# PostgreSQL и миграции

PostgreSQL — единственный persistent source of truth. Redis можно потерять: finished
reports остаются, queued runs повторно доставляются. SQLAlchemy 2.x + psycopg 3;
`create_all()` не используется для запуска приложения.

## Таблицы и связи

| Таблица | Стабильные поля | Назначение |
|---|---|---|
| users | id UUID PK, yandex_id UNIQUE, created_at | Идентичность пользователя нашего сервиса |
| repositories | id UUID PK, sourcecraft_id UNIQUE, org/repo UNIQUE, canonical_url UNIQUE, visibility, default_branch, head_sha | Идентичность и метаданные платформы |
| repositories: проекция рейтинга | language, likes, last_activity_at, health_score, latest_analysis_id, next_analysis_at | Индексируемые поля чтения/расписания |
| analysis_runs | id UUID PK, repository_id FK, status, trigger, profile, fingerprint, timestamps, head_sha, versions, health_score, error_code | История выполнения |
| analysis_runs: JSONB | category_scores, data_coverage, recommendations, results | Версионированный аналитический payload |

Связь `repositories 1 → N analysis_runs`; FK с CASCADE означает, что **удаление repo
удаляет всю историю**, поэтому endpoint удаления не предоставляется. `latest_analysis_id`
указывает на последний законченный run; FK SET NULL. Циклический FK добавляется после
создания обеих таблиц. Application обеспечивает, что latest принадлежит тому же repo.

User пока не связан с repository ownership: нельзя выдать существование такой связи
за подтверждённое право SourceCraft. Серверные сессии находятся в Redis с TTL,
OAuth/PAT в таблицах отсутствуют.

## Индексы и ограничения

- `(visibility, health_score DESC NULLS LAST, id)` — default leaderboard.
- `language` — фильтрация; `next_analysis_at` — due repositories.
- `(repository_id, queued_at DESC)` — история.
- `(fingerprint, completed_at)` — свежий результат нужного профиля/snapshot.
- `(status, queued_at)` — dispatcher.
- Partial UNIQUE `(repository_id, profile)` для queued/collecting/analyzing/scoring:
  один активный анализ профиля даже при неизвестном HEAD.
- CHECK допустимых status/trigger/visibility, nullable Score 0–100 и связи terminal
  status ↔ completed_at. Неправильный lifecycle дополнительно запрещён application.

## JSONB и воспроизводимость

`results` хранит полный public report 3.0; остальные JSONB поля — проекции для API.
Запись результата и обновление leaderboard выполняются в одной транзакции. Состояния
без готового report имеют `{}`/`[]`, а не fake результат. Точное время сбора и входы
policy должны храниться в report. Collector facts должны быть достаточны для
повторного расчёта используемых метрик, но не содержать исходный код/секреты.

Для новой метрики добавить поле в `metrics` и увеличить analyzer version при изменении
смысла. Миграция нужна лишь для стабильной domain/storage структуры, индексов или
новых требований согласованности. Не добавлять columns per analyzer/finding.

## Работа с Alembic

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic check
python -m alembic upgrade head --sql
```

Единственная начальная ревизия — `0001`. В production миграция — отдельный шаг
deployment перед запуском API/worker; Compose предоставляет сервис `migrate`.
Autogenerate создаёт предложение, не готовую миграцию. Review проверяет downgrade,
блокировки, backfill и совместимость старого процесса с новой схемой.
Предпочитать additive changes. Не переписывать применённую общую миграцию; initial
можно дорабатывать только до первого общего deployment команды.

## Retention и lifecycle данных

Source workspace не сохраняется в БД. Законченные reports пока сохраняются без
автоматического удаления: история нужна для сравнения и разработки policy.
План после оценки объёма: 90 дней полных reports, более долгие агрегаты только по
согласованной политике. Это **план**, не скрытый cleanup job. Перед включением retention
решить, как сохраняются evidence refs, latest pointer и воспроизводимость старых оценок.

Миграционный downgrade уничтожает историю. Перед операциями удаления/миграцией
production — `pg_dump`, проверка восстановления, окно и явно выбранный target.
Интеграционные тесты работают только с отдельной БД `*_test`; никогда с production URL.
