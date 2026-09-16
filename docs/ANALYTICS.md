# Аналитика: категории, факты и расширение

Анализатор возвращает измерения и evidence, а не окончательный Health Score.
Collectors отвечают за I/O и availability. Scoring отдельно интерпретирует метрики.

| Категория | Источники | План метрик | Evidence |
|---|---|---|---|
| documentation | Git snapshot | README/license, run/build/test instructions, CONTRIBUTING/CODEOWNERS | file + HEAD + relative path |
| cicd | SourceCraft runs + CI config | Success rate, duration, recent failures, configuration presence | ci_run/config file |
| security | Только SourceCraft AppSec | Open/resolved по SAST/SCA/secrets и severity | vulnerability/scan reference + timestamps |
| activity | Git, MR, contributors, releases | Commit windows/gaps, last activity, contributors, releases | commit/platform references |
| issues | SourceCraft issues/comments | Open/closed, stale, response/closure times | issue/comment references |
| code_health | Snapshot + Git history, local scanner | TODO/FIXME, complexity/debt, local findings | file/line/commit, без source snippets |

## Что работает сейчас

GitActivityAnalyzer и GitActivityAnalyzerAdapter сохраняют прежние расчёты, точные
определения в [METRICS](METRICS.md). GitCollector возвращает список истории HEAD,
API pure analyzer не менялся. Local SAST сохраняет JSON rules, AST/regex/lexical
engines, budgets, redaction и SARIF. Его id остаётся `sast`, но source явно
sourcehealth_local и category code_health.

В фоне RepositoryMetadataAnalyzer публикует безопасные metadata/evidence, без category
score. SourceCraftSecurityAnalyzer сообщает недоступность неподключённого AppSec.
Не считать эти два анализатора реализацией всех шести категорий.

В `code-v1` background job добавляет `checks.git_activity` (activity/git) и
`checks.sast` (code_health/sourcehealth_local) через один sandbox запуск.
Legacy JSON 1.0 остаётся прежним; converter переносит counters/findings в общий
контракт 3.0. Ошибка/невалидный check не удаляет второй check или platform facts.
SAST partial сохраняет измеренные counters и причины неполного охвата; runtime failure
даёт NO_DATA, а не нулевые метрики/Score. Cleanup failure помечается отдельным safe code.

## Добавить IssuesAnalyzer

Collector получает issues через client.iter_items и хранит необходимые временные поля,
статусы и references. Не сохранять весь body/comment: он может содержать секреты.
Analyzer принимает context.sourcecraft_facts['issues']; время анализа берёт из
context.started_at, не datetime.now(). Результат:

```python
return AnalyzerResult(
    analyzer="issues", category="issues", source="sourcecraft",
    analyzer_version="1", availability=availability,
    status="ok" if availability == DataAvailability.AVAILABLE else "partial",
    metrics={"open_count": open_count, "window_days": 30},
    evidence=evidence,
)
```

Это пример формы, не готовая методика. `open_count=None` при неизвестных данных;
0 допустим только при полном наблюдении пустого набора. Частичная pagination не
равна полному count. Новый analyzer добавляется обычным списком в profile; plugin
framework, новый router и таблица per analyzer не нужны.

## Договориться о смысле метрик

До реализации указать unit, окно времени, timezone, включение границ, scope ветки,
фильтр bots/private issues, empty vs unavailable, sampling/partial semantics.
Фиксировать analyzer_version при изменении смысла. Для code facts хранить HEAD и
configuration digest. Rolling Git метрики зависят не только от SHA, но и от reference
time: нельзя бессрочно кэшировать готовый `days_since_last_commit` по HEAD.

## Большие репозитории

Текущий GitCollector хранит весь stdout/list[Commit] в памяти. Его compatibility API
сохранён. Будущие collectors могут добавлять streaming, ограниченные окна, агрегаты
или incremental storage, не меняя Analyzer Protocol. Shallow clone запрещён как
скрытый default для исторических метрик; partial clone/blob filtering допустим только
если анализу не нужны отсутствующие blobs. Лимиты и partial coverage показываются явно.
