# Аналитика MVP: факты, определения и границы

Профиль `mvp-v1` реализован 19.09.2026. Collectors выполняют I/O; analyzers получают
facts и возвращают метрики/evidence; policy отдельно рассчитывает оценку. Проверки
на контрактных fixtures и настоящих PostgreSQL/Redis описаны в [TESTING](TESTING.md).
Успешный live сбор SourceCraft пока не принят: доступные запросы вернули 401.

| Категория | Check / источник | Измерения |
|---|---|---|
| documentation | documentation / git_snapshot | README, LICENSE, run/build/test, CONTRIBUTING, CODEOWNERS, docs |
| cicd | cicd / sourcecraft + snapshot | Конфигурация, запуски, success/failure, duration, последний статус |
| security | sourcecraft_appsec / sourcecraft_appsec | Пока NO_DATA: appsec_interface_unconfirmed |
| activity | git_activity / git + platform_activity / sourcecraft | Git windows/recency, PR, contributors, releases |
| issues | issues / sourcecraft | Open/closed, stale, response/closure medians, последние 30 дней |
| code_health | sast / sourcehealth_local + technical_debt / git_snapshot | Локальные findings, TODO/FIXME, возраст строк, большие файлы |

`platform-v1` и `code-v1` сохраняют прежнее поведение и `unconfigured-v1`.
`mvp-v1` проходит через `analysis-code`: один clone и один sandbox scan с `--with-mvp`.
Analyzer не обращается к DB, Redis или frontend. Сбой sandbox не удаляет platform facts.

## Общая семантика

Временные окна новых pure analyzers считаются от `context.started_at` в UTC; recent —
замкнутый интервал `[started_at − 30 дней, started_at]`. Старый GitActivity не переписан:
его определения в [METRICS](METRICS.md). Snapshot получает reference time своего
scanner context. В report остаются timestamps наблюдений и фактический HEAD SHA.

Полный пустой ответ API — `available`, известные counts равны 0. Отсутствующий
collector — `no_data`, ошибка до первого item — `source_unavailable`, ошибка после
получения части items — `partial`. При partial итоговые counts/ratios равны `null`;
`observed_count`/`runs_observed` обозначают только размер реально полученной части.
Дубли id исключаются. Неизвестное значение никогда не подменяется нулём.

Evidence содержит источник, тип, время, repository reference/URL; snapshot evidence —
HEAD и относительный путь признака. Это агрегированное наблюдение, а не публикация
issue/comment body или исходного кода. Проверки хранят inputs для replay policy;
исходные тела HTTP не сохраняются. References проверяет ScoringEngine.

## Documentation

`SnapshotCollector` читает tracked файлы текущего HEAD в изолированном свежем clone.
Исключаются `.git`, `node_modules`, `vendor`, `.venv`, `venv`, `dist`, `build`,
`__pycache__`. Symlink/junction, hardlink и специальные файлы не читаются. Target code,
install/build/tests/hooks не исполняются.

Детерминированные признаки:

- README в корне: без расширения или `.md/.rst/.txt`; сохраняются byte size и Markdown headings.
- LICENSE/LICENCE/COPYING в корне; проверяется присутствие, не юридическая корректность лицензии.
- CONTRIBUTING в корне, CODEOWNERS в корне/`.github`/`.sourcecraft`/`docs`.
- `docs_directory`: хотя бы один безопасный tracked файл внутри `docs`.
- Run/build/test: совпадения команд или заголовков в README и `.md/.rst/.txt` внутри `docs`.
  Run: Quick Start, Getting Started, «запуск», npm run dev/start, docker compose up,
  uvicorn, python -m. Build: заголовок build/«сборк», npm run build, docker build,
  cargo build, go build. Test: заголовок test/«тест», pytest, unittest, npm/go/cargo test.

Это проверка наличия признаков, не качества текста и не успешности команды. Регулярные
выражения версионируются вместе с analyzer; LLM не используется. Лимиты: 10 000 tracked
файлов, 1 MiB на читаемый файл, 64 MiB суммарно, общий бюджет 30с плюс начальные Git
операции с timeout 10с каждая. Полнота разделена на `documentation_complete` и
`debt_complete`: большой или не-UTF8 code file делает partial только Debt, а ошибка
чтения README — только Documentation. Общий обрыв обхода/лимит файлов сохраняет
консервативный partial обоих наборов. Не найденные при неполном documentation обходе
признаки — `null`, оценка Documentation не рассчитывается. Analyzer version — 2.

## Issues

Только публичные issues; `initial/in_progress/paused` — open,
`completed/cancelled` — closed. `closed_at` соответствует официальному `completed_at`
(последний переход в завершённое состояние). Stale: open issue не обновлялся ≥30 дней.
`stale_ratio = stale_open_count/open_count`, при полном отсутствии open — 0.
`recent_created/recent_closed` используют соответствующие timestamps и окно 30 дней.

Issues analyzer version 2: `first_external_response_at` — первый публичный комментарий
с `comment.author.id != issue.author.id`. ID сравниваются только в памяти collector
и удаляются из facts перед возвратом; имена/email/body не сохраняются. Другой бот
считается внешним автором: это не метрика исключительно человеческого ответа.
Отсутствующий/невалидный author.id делает response history неизвестной.
Budget — первые 10 issues, не более 2000 comments на issue.

`median_first_external_response_hours` — медиана **среди ответивших**; одновременно
публикуются `unanswered_count`, `external_response_rate` и `response_observed_count`.
Все итоговые response metrics требуют полностью просмотренной comments истории
каждого issue. Неответившие не получают нулевую latency: при полном наборе они входят
в unanswered_count, а их доля уменьшает response-компонент score. Если никто не
ответил: median=null, rate=0; если issues вообще нет: unanswered=0, median/rate=null.
При превышении budget median/rate/unanswered неизвестны, но counts/stale сохранены.
Старое имя `median_first_response_hours` осталось только в сохранённых v1 reports.
Median close использует только closed и требует известного времени закрытия каждого.
Отрицательные durations отвергаются collector. Даты вне окна не попадают в recent.

## CI/CD

Состояния success и failed/timeout/rejected образуют знаменатель success rate.
Canceled/skipped и незавершённые состояния не считаются ни успехом, ни failure.
Duration — `finished_at − started_at`, медиана только при известной длительности всех
этих завершённых runs. Recent failures считаются по created_at, latest — по created_at.

`configured=false / not_configured` требует одновременно **полного пустого API списка**
и полного snapshot без `.sourcecraft/ci.yaml`. Это отсутствие нативной SourceCraft CI,
не утверждение об отсутствии внешних CI-систем. Наличие файла или наблюдённых runs
подтверждает configured=true. API outage/partial остаётся outage/partial даже при
наличии файла. Пустой список без знания snapshot даёт configured=null.

## Activity

GitActivityAdapter сохраняет прежние commits/windows/gaps/last commit. Дополнительный
PlatformActivityAnalyzer считает все PR, merged PR, PR с updated_at в последние 30 дней,
уникальных contributors и **опубликованные** releases, timestamp последнего release.
Draft/discarded releases исключены, emails/names/notes не сохраняются. Bots и aliases
contributors не объединяются: это число id, возвращённых платформой.
Каждый ресурс имеет собственную availability; неполные counts равны null. Отсутствие
release при полном списке — 0, а не outage. Git и известные platform компоненты могут
давать частичную оценку Activity по правилам [SCORING](SCORING.md).

## Code Health и technical debt

Local SAST сохраняет rules, engines, redaction, budgets и SARIF. Он не даёт Security score.
Debt использует безопасные UTF-8 code files: py/js/jsx/ts/tsx/java/go/rs/c/h/cpp/hpp/cs/
php/rb/swift/kt/scala/sh/sql. Лексические слова `TODO` и `FIXME` регистрозависимы,
учитываются также внутри строк; это прозрачная эвристика, не parser комментариев.
Сохраняются counts маркеров, files_with_debt, code_files и `(TODO+FIXME)/code_files`.
Large file — более 1000 строк. Complexity/длина функций в v1 не заявляются.

Возраст — максимальное число дней с **последнего изменения текущей строки маркера**
по `git blame --line-porcelain --no-textconv HEAD`. Это не дата первого появления TODO.
Не более 10 файлов с маркерами и 5с на blame в пределах общего budget. При неполном
blame `age_complete=false`, возраст null; density может оставаться известной.
Чистый полный набор без маркеров имеет age=null и age_complete=true. Partial snapshot
сохраняет наблюдённые counts, но density=null и весь debt исключается из score.

## Расширение

Новый analyzer подключается списком в профиль, без plugin framework и таблицы per check.
При изменении смысла метрики обновлять analyzer/policy version, fixtures и эту страницу.
Готовые rolling metrics нельзя бессрочно кэшировать по SHA: TTL запуска ограничивает
возраст всей observation; platform facts повторно собираются при новом запуске даже
без изменения Git. Большая Git-история пока использует совместимый list[Commit].
