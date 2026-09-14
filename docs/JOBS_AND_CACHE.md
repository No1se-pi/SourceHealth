# Фоновые задания, кэш и повторный анализ

## Lifecycle

```text
queued → collecting → analyzing → scoring → completed
                                  └───────→ partial
любой активный этап ──────────────────────→ failed
```

Terminal состояния не переоткрываются. Повторная попытка после failed — новый run.
queued_at при создании, started_at при collecting, completed_at для terminal.
Trigger: manual/scheduled/refresh/system. Partial означает полезный сохранённый
результат с ограничением данных, не плохую оценку проекта.

## Десять одновременных POST

1. `SELECT ... FOR UPDATE` repository сериализует решения application.
2. Активный run того же профиля → вернуть его UUID.
3. Иначе свежий completed/partial с нужным fingerprint → вернуть его UUID.
4. Иначе создать queued и commit. Partial UNIQUE repository/profile — дополнительный
   invariant, если другой писатель обошёл service.
5. Dispatcher enqueue UUID с `job_id=analysis_id, unique=True` в Redis/RQ.
6. Worker берёт session advisory lock PG по run UUID. Duplicate delivery выходит,
   если lock занят или status больше не queued.

Active dedupe сильнее snapshot key: один активный run профиля на repo даже при
неизвестном/изменившемся HEAD. Новый commit во время run попадёт в следующий запуск.
При подключении clone нужно сохранять фактически анализируемый SHA и сверять его с
запрошенным snapshot. Пока API-only профиль не обещает фиксацию code snapshot.

## Восстановление

Строки queued — durable outbox без отдельной таблицы. Сбой до enqueue оставляет
строку для команды dispatch. Потеря Redis восстанавливается из PG. Сбой после
enqueue закрывают RQ unique ID и DB lock. POST может вернуть 202 при недоступном
Redis: факт приёма уже сохранён, доставку повторит reconciliation.

Deadline = analysis_timeout + 60с. Recover ищет просроченные active runs и пробует
тот же advisory lock: живой держатель не объявляется failed. После смерти процесса
lock освобождается; run получает worker_interrupted. Новый run создаётся обычным
request/scheduler. Долгий неумирающий процесс требует операционной диагностики,
не запуска дубликата. PgBouncer transaction pooling несовместим с session advisory
locks: worker guard требует прямого/session-pooled подключения.

## Ключи и свежесть

| Уровень | Ключ | TTL / invalidation | Сейчас |
|---|---|---|---|
| Code | repo ID + HEAD + analyzer + version + configuration | 7 дней; новый HEAD/version меняет ключ | Примитив; фоновой code profile не подключён |
| Platform | repo ID + resource + authorization scope | 5 минут; HEAD не участвует | Public metadata |
| Finished run | repo ID + HEAD + profile + policy + report version | 5 минут | Реализован |
| Auth | HMAC opaque token | Session 24ч, pending 10мин | Реализован |

Cache failure = miss. Хранятся только очищенные versioned facts/results. Unknown
HEAD запрещён для code key. Ошибочные metadata не кэшируются как успех. CollectedFacts
содержит collected_at; source timestamps/ETag нужно подключать отдельно, если
официальный resource их предоставляет. Code timestamp и platform freshness — разные вещи.
Изменение issues/CI/AppSec должно обновлять результат без clone и без нового HEAD.

Private workflow требует scoped cache и актуальной проверки доступа перед выдачей
cached result. Пока он запрещён. Потеря Redis завершает сессии, но не теряет пользователей.

## Scheduler

```powershell
python -m sourcehealth.application enqueue-due
python -m sourcehealth.application dispatch
```

Enqueue-due выбирает до 100 due public repo, создаёт/reuses run, сдвигает next_analysis_at,
восстанавливает abandoned и отправляет queued. Анализ внутри команды не выполняется.
Начальный интервал repo — 24ч. Запуск команды раз в минуту cron также обеспечивает
dispatch recovery. Compose scheduler — one-shot profile, не скрытый loop в FastAPI.
Для большого каталога измерить throughput/batch size и drain нескольких страниц.

## Дальнейшая работа

Execution profiles, квоты/приоритеты, budget API, TTL ресурсов, code runtime/cache,
точный SHA. Наличие code_cache_key не означает, что worker уже переиспользует SAST.
