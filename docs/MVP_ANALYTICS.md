# Поставка MVP analytics: 19–20 сентября 2026

## Поправки по review 20 сентября

Базовый протокол ниже относится к `23bcd5a` и последующему docs-коммиту `f6acd36`.
После review дополнительно исправлено:

- Issues collector schema/analyzer v2: первый внешний автор вместо self-comment;
  author.id сравнивается только в памяти. Unanswered count и response rate отдельные,
  неизвестная история не превращается в отсутствие ответов.
- `mvp-score-v1.1`: response-компонент учитывает долю ответивших; остальные пороги
  не перекалиброваны без реальных данных. Старые отчёты не переписываются.
- Documentation/Debt имеют независимую полноту. Ошибка code file не обнуляет охват README.
- Backend `score_coverage`, новый OpenAPI/TS contract; рядом со Score на страницах
  repository/analysis видны номинальный процент, missing и partial категории.
  Markdown показывает тот же backend расчёт. Unknown policy — неизвестный coverage.
- Ubuntu CI job `mvp-snapshot-smoke` собирает scanner и выполняет новый Docker smoke.

Проверки после поправок: **161 tests, 159 passed, 2 expected skips**, включая 11
настоящих PostgreSQL/Redis/RQ integration tests; Ruff, OpenAPI/TS generation и frontend
build прошли. Scanner image пересобран, offline Docker MVP smoke повторно прошёл.
GitHub [run #23](https://github.com/No1se-pi/SourceHealth/actions/runs/35482813353)
для b66cb2e завершён успешно, включая новый mvp-snapshot-smoke, integration,
frontend-contract, Compose и Python 3.11/3.13 Windows/Linux. Browser-проверка не состоялась: подключение
инструмента отклонено ошибкой `missing field sandboxPolicy` до открытия страницы.
Поэтому проверка UI пока ограничена контрактом/TypeScript/build, не visual acceptance.

Ссылки на этот файл уже были исправлены в f6acd36. Следующий приоритет — рабочий
SourceCraft read доступ и live chain, затем калибровка на 5–10 разных проектах.
Дополнительный maintainability signal (например, длина Python-функций) остаётся
отдельной задачей перед финалом; в этой поправке не реализован. AppSec/private блокеры
не сняты. Никаких guessed endpoints или fake production findings не добавлено.

## Базовая поставка

Перед PR дополнительно разделены byte budgets: по 64 MiB для Documentation и Debt,
без взаимного расходования. Provenance теперь различает entire_collected_set,
recent_window_days и stale_threshold_days. Регрессии проверяют оба направления
исчерпания бюджета и all-time counts вне recent окна. После этих правок: **164 tests,
162 passed, 2 expected skips**, Ruff, diff check и пересобранный Docker MVP smoke прошли.
CI #23 выше подтверждает b66cb2e; новый commit должен пройти собственные checks в PR.

Ветка `feature/mvp-analytics`, база `Dev-No1se` на
`98662373b42a69e83c7eb3cf7ce490a284950c88`. Основная реализация сохранена в
`23bcd5aab62ea989efc0c663a6471f4ef636769c` (`precommit(analyz)`). PR и merge не выполнялись
в рамках этого batch. Foundation/старые CLI и профили сохранены.

## Что реализовано

- Allowlisted collectors Issues/comments, CI runs, pull requests, contributors,
  published releases. Pagination, deduplication, budgets, empty/partial/outage.
- Documentation по tracked snapshot: README/license/run/build/test/contributing/
  codeowners/docs, relative-path evidence и фактический HEAD.
- Issues counts/stale/latency; CI configuration/success/failure/duration/latest;
  Activity из существующего Git и новых platform facts.
- Code Health: прежний local SAST + TODO/FIXME density, bounded Git blame age,
  large files. Target repository code не исполняется.
- `mvp-score-v1`: шесть category slots, веса 15/15/20/15/15/20, overall только
  при ≥3 рассчитанных категориях и ≥50 номинальных весов. Missing не равно 0.
- Детерминированные рекомендации docs/CI/issues/debt/local findings с evidence refs
  и qualitative impact; official AppSec boundary остаётся отдельно.
- `mvp-v1` в trusted очереди `analysis-code`, один clone/scan; persist checks,
  category scores, policy, coverage, recommendations, Health и HEAD. Повторный
  запрос использует cache также после первого определения HEAD.
- Public URL import: session + Origin + API visibility verification + idempotent
  upsert. Маленькая форма в существующем React leaderboard. OpenAPI/TS обновлены.
- Ограниченное global/org discovery, проверка каждого repo и постановка на анализ.
- Markdown и leaderboard используют сохранённые численные результаты.

Формулы: [SCORING](SCORING.md). Метрики и budgets: [ANALYTICS](ANALYTICS.md).
API: [API](API.md). Запуск mvp-v1 и worker: [DEPLOYMENT](DEPLOYMENT.md).
Решение общей границы: [ADR 0008](adr/0008-mvp-analytics-policy.md).

## Фактически выполненные проверки

| Проверка | Результат и предел доказательства |
|---|---|
| `python -B -m unittest discover -s tests -v` с test PG/Redis | 156 tests, 154 passed, 2 skipped: Unix-only FIFO и opt-in live SourceCraft |
| PostgreSQL/Redis/RQ integration | Все 11 тестов прошли; отдельные sourcehealth_test и Redis DB 15, включая HTTP import → queue → collect → score → persist → GET/Markdown/leaderboard/cache |
| Snapshot fixtures | Настоящие локальные Git repositories, blame age, partial budget, symlink, scanner roundtrip; platform fixtures не являются live ответами |
| Ruff и pip check | Passed, зависимости согласованы |
| Alembic upgrade head + check | Applied/current 0001, новых migrations и drift нет |
| OpenAPI export + TypeScript generation | Diff содержит только новый POST import и RepositoryImport; CI подтверждает воспроизводимость |
| npm ci / types / build | Passed; npm audit в ходе ci: 0 vulnerabilities; browser flow этим не проверен |
| docker compose config --quiet | Passed |
| scripts/compose_smoke.py | Реальный build/up/migrate/PG/Redis/API health/HTTP 200/RQ worker; изолированный project очищен |
| Scanner Docker build + scripts/mvp_snapshot_smoke.py | Реальный контейнер без сети с synthetic Git snapshot: Git/docs/debt/SAST/HEAD, target code не исполняется, cleanup выполнен |
| GitHub CI для 23bcd5a | [Run 35468264499](https://github.com/No1se-pi/SourceHealth/actions/runs/35468264499) completed/success: Linux/Windows Python 3.11/3.13, integration, frontend contract, Compose |
| git diff --check | Passed |

При возобновлении 20 сентября первая локальная integration попытка получила
ConnectionRefused от остановленного Redis. После `docker compose up -d postgres redis`
полный suite и migration checks повторно прошли. Это исправление среды, не скрытый skip.

## Live и внешние блокеры

19 сентября скачана актуальная официальная Swagger, проверены поля/enum/endpoints;
точный hash и источники — [SOURCECRAFT](SOURCECRAFT.md). Семь live GET попыток
(metadata/issues/runs/pulls/contributors/releases/global repos) дали HTTP 401,
`authentication_required`, успешных items 0. Поэтому **успешный live сбор не заявляется**.

- Public platform: нужен рабочий read API доступ/PAT и сверка fixtures с реальными
  ответами; затем public import, first/repeat run и наполнение leaderboard.
- Security: `NO_DATA / appsec_interface_unconfirmed`. Нужны официальный base URL,
  auth, полная schema/enums, repository mapping и sanitized real fixture. Local SAST
  не даёт Security score. Synthetic official fixture проверяет только внутреннюю policy.
- Private: отсутствует подтверждённый Я ID → SourceCraft permissions bridge,
  поэтому private disabled. Реальный OAuth browser flow отдельно не принят.
- Global discovery: endpoint GET /repos **подтверждён и реализован**; неизвестный
  endpoint больше не blocker. Live доступ и полный каталог не подтверждены.

## Реально оставшаяся обязательная работа

Успешная live SourceCraft/OAuth приёмка, official AppSec и private permission bridge,
проверка большого SourceCraft repo по порогу исходного ТЗ, mapping likes, deployment
и материалы демонстрации. Детали/владельцы в [ROADMAP](ROADMAP.md).
Browser acceptance не заменена build или HTTP tests. Новый foundation, ML/LLM,
микросервисы и повторная реализация пяти готовых категорий для этого не нужны.
