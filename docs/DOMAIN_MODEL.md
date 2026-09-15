# Предметная модель и стабильные контракты

## RepositoryRef

`sourcehealth/core/domain.py`: frozen dataclass, независимый от локального диска.
Поля: внутренний UUID `id`, `sourcecraft_id`, `organization_slug`, `repository_slug`,
`canonical_url`, `visibility`, `default_branch`, `head_sha`. Неизвестные значения —
`null`/`unknown`, а не пустые строки и не предположения.

`from_url()` принимает только проверяемый формат SourceCraft HTTPS. Канонический web
URL не содержит credentials/query/fragment; clone URL не является пользовательским
fetch endpoint. При повторном чтении repo используется сохранённый ID. `from_url()`
сам по себе создаёт новый UUID, поэтому не используется как lookup существующего repo.
Переименование платформы должно обновлять slug при сохранении internal/sourcecraft ID;
автоматическая reconciliation rename пока не реализована.

## AnalysisContext

`repository` — identity; `workspace` — property поверх прежнего `repo_path: Path | None`.
Так старые вызовы `AnalysisContext(path, commits=...)` остаются совместимыми.
`commits=None` означает недоступную историю, `commits=()` — прочитанную пустую историю.
`sourcecraft_facts` содержит очищенные данные, `collection_statuses` — доступность
по имени коллектора. `started_at` всегда timezone-aware. `metadata` и
`collection_errors` сохранены для прежних адаптеров.

Frozen dataclass не делает вложенные dict неизменяемыми: анализаторы обязаны считать
контекст read-only. Контекст не содержит HTTP clients, DB sessions, PAT или Docker handle.

## AnalyzerResult

Стабильные поля: `analyzer`, `status`, `metrics`, `findings`, `metadata`, `error`.
Добавлены `availability`, `category`, `source`, `analyzer_version`, `contract_version`,
`evidence`. `metrics` и analyzer-specific finding fields могут эволюционировать
внутри versioned JSON, не создавая столбцы PostgreSQL.

`status=ok|partial|error` описывает исполнение. Наличие находок не делает исполнение
ошибочным. Ошибка runner даёт безопасный код `analyzer_failed`; произвольный exception
text не возвращается. `NaN`, `Infinity`, не-JSON объекты отклоняются при `to_dict()`.

| availability | Смысл | Можно автоматически считать score=0? |
|---|---|---|
| available | Проверка выполнена, факты доступны | Нет: качество выводится из фактов |
| not_configured | Доказано отсутствие настройки, например CI | Только явным правилом утверждённой policy |
| no_data | Нет достаточных наблюдений/подключённого источника | Нет |
| source_unavailable | Источник временно недоступен / отказал в доступе | Нет |
| partial | Часть данных собрана, охват ограничен | Только с явным правилом и объяснением |
| error | Анализатор не выполнил свою работу | Нет |
| not_applicable | Проверка обоснованно неприменима | Нет |

Плохой результат выражается facts/findings, а не дополнительным enum.
`source=sourcehealth_local, category=code_health` закреплены за локальным SAST.
`source=sourcecraft_appsec, category=security` предназначены для настоящих AppSec facts.

## Evidence и Recommendation

Evidence: `id`, `source`, `type`, `reference`, `summary`, optional `url`, `location`,
`timestamp`. ID уникален внутри report. `location` — относительное расположение,
никогда абсолютный workspace. `summary` не включает найденный секрет/исходную строку.
Возможные type: repository_metadata, file, vulnerability, issue, ci_run, commit, pull_request.

Recommendation: `id`, `category`, `title`, `description`, `priority=1..3`, непустые
`evidence_refs`, `suggested_action`, nullable `expected_impact`. P1 — наиболее срочно.
`validate_recommendations()` проверяет уникальность ID и существование evidence refs.
Влияние в баллах не обещается без воспроизводимой policy.

## AnalysisRun и AnalysisReport

Run — persistence entity: UUID, repository FK, trigger, lifecycle, snapshot/profile,
времена, версии, результаты и safe error. Report — результат вычисления, пригодный
для хранения/рендеринга. Их не следует объединять: queued run ещё не имеет report.

`AnalysisReport.to_dict()` остаётся JSON 2.0 для локального CLI. В нём сохраняется
локальная repository.path; этот формат **не HTTP DTO**. `to_public_dict()` требует
валидный RepositoryRef, возвращает JSON 3.0, включает scoring/categories/recommendations.
Старый JSON 1.0 обслуживает SAST/SARIF/container workflow через `to_legacy_report()`.
Добавленные поля AnalyzerResult аддитивны; старые имена/checks не переименованы.

Версии независимы: REST `/api/v1`, public report `3.0`, analyzer version, policy version.
Изменение формулы требует новой policy version; изменение численного смысла метрики —
новой analyzer version и cache configuration/profile version.
