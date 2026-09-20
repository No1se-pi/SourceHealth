# Проверки и критерии достоверности

Тестовый framework — unittest. Прежние Git/scanner/runner тесты сохранены.
Foundation добавляет identity/context/availability/scoring/cache/HTTP/pagination tests.
Новые функции проверяются по поведению, не только по совпадению с implementation.

## Быстрые проверки

В активированной .venv из [DEPLOYMENT](DEPLOYMENT.md):

```powershell
python -B -m unittest discover -s tests -v
python -m ruff check .
python scripts/export_openapi.py
npm ci --prefix frontend
npm run types --prefix frontend
git diff --exit-code -- docs/openapi.json frontend/src/api/generated.ts
npm run build --prefix frontend
git diff --check
```

CLI-only `pip install -e ".[dev]"` не устанавливает HTTP/БД зависимости; server tests
в таком окружении пропускаются явно. Для полной foundation проверки устанавливать
`requirements-server.lock` и `.[dev,server]`. На Windows Unix-only FIFO test пропущен.
FastAPI/Starlette текущего lock может выдавать deprecation warning TestClient/httpx;
это не ошибка теста, migration test transport следует планировать при обновлении stack.

## PostgreSQL/Redis integration

Никакой SQLite подмены. Используется отдельная PostgreSQL БД с суффиксом `_test` и
Redis DB 15; тесты отказываются работать с другими target. PostgreSQL migration
применяется заранее, create_all не используется.

```powershell
docker compose up -d postgres redis
# Только один раз; если test DB существует, повторять createdb не нужно.
docker compose exec -T postgres createdb -U sourcehealth sourcehealth_test
$env:TEST_DATABASE_URL='postgresql+psycopg://sourcehealth:sourcehealth@127.0.0.1:15432/sourcehealth_test'
$env:TEST_REDIS_URL='redis://127.0.0.1:6379/15'
$env:DATABASE_URL=$env:TEST_DATABASE_URL
python -m alembic upgrade head
python -m alembic check
python -m unittest tests.test_integration -v
Remove-Item Env:DATABASE_URL, Env:TEST_DATABASE_URL, Env:TEST_REDIS_URL
```

Тесты создают уникальные repo и удаляют собственные записи. Проверяют десять
конкурентных запросов/пять dispatchers, DB unique constraint, недоставленный queued,
RQ execution, сохранение report, cached/force поведение, recovery guard, private
report deny, Markdown и Я ID state/PKCE/session/logout. Я ID и collection HTTP в этих
тестах mocked: real persistence не означает live внешнюю acceptance.

Для Linux переменные задавать `export`, после — `unset`. Интеграционный CI job
поднимает PostgreSQL/Redis services отдельно от fast unit matrix.

## Runtime integration и Compose smoke

`tests/test_runtime_pipeline.py` проверяет одно sandbox-обращение для Git/SAST,
partial/failure/malformed payload/cleanup, сохранение platform facts, классификацию
local SAST и отсутствие raw error/snippet в public JSON. Fixture runtime — не live clone.
`test_code_queue_runtime_persistence_and_http` в integration suite использует настоящие
PostgreSQL/RQ/HTTP с fake runtime: отдельная code очередь, success/partial/exception/
disabled, persistence и HTTP/Markdown. Обычный worker не получает code jobs.

```powershell
python -m unittest tests.test_runtime_pipeline -v
docker compose config --quiet
python scripts/compose_smoke.py
```

Compose smoke — настоящий build/up/migrate/health/worker и обязательный down -v в
изолированном project. Он не обращается к SourceCraft или Я ID. Ubuntu CI выполняет
его отдельным job; детали изоляции в [DEPLOYMENT](DEPLOYMENT.md).

## Проверка миграции

Upgrade/`alembic check` обязательны. Downgrade/upgrade проверять только на disposable
`*_test` БД: downgrade удаляет таблицы и историю. Offline SQL `upgrade head --sql`
показывает DDL, но не доказывает успешное применение на настоящем PostgreSQL.

## MVP analytics: воспроизводимая проверка

`tests/test_mvp_collectors.py` проверяет официальный shape, allowlist, pagination,
пустые/partial/invalid/outage ответы, comment budget и ограниченное discovery.
`tests/test_mvp_snapshot.py` создаёт настоящие Git repositories: документация, debt,
blame age, partial budget, symlink и полный scanner → normalizer roundtrip.
`tests/test_mvp_analytics.py` проверяет метрики, шесть slots, монотонность, coverage,
replay, Security boundary и валидность evidence recommendations.

`test_mvp_import_queue_report_leaderboard_and_cache` в integration suite выполняет
HTTP import → настоящий RQ worker → collectors → analyzers → score → PostgreSQL →
GET AnalysisDetails/Markdown/leaderboard и повтор из кэша. SourceCraft transport и
code runtime — fixtures; DB/Redis/RQ/HTTP настоящие. Дополнительно проверяются
неверный URL, Origin, отсутствие сессии, private/unverified repository.

```powershell
python -m unittest tests.test_mvp_collectors tests.test_mvp_analytics tests.test_mvp_snapshot -v
docker build -f sourcehealth/sast/Dockerfile -t sourcehealth-sast .
python scripts/mvp_snapshot_smoke.py
```

Результаты поставки и live blockers: [MVP_ANALYTICS](MVP_ANALYTICS.md).
Snapshot smoke использует настоящий offline Docker scanner и synthetic Git repository,
проверяет HEAD/docs/debt/Git/SAST и отсутствие исполнения target code. Собственный
unique volume удаляется в finally. Это не live clone SourceCraft.
Отдельный Ubuntu job `mvp-snapshot-smoke` в `.github/workflows/tests.yml` собирает scanner
image и выполняет этот smoke. Review regressions покрывают self-comments, unanswered,
unknown authors, независимую полноту docs/debt и backend weighted coverage.

## Live SourceCraft opt-in

```powershell
$env:SOURCEHEALTH_LIVE_REPO_URL='https://sourcecraft.dev/org/repo'
python -m unittest tests.test_live_sourcecraft -v
```

PAT задаётся отдельно environment. Обычный CI не имеет настоящих credentials. После
запуска удалить обе переменные из текущей shell session.
Successful live metadata не подтверждает AppSec или права закрытых repo.
Тест запускается только при одновременном наличии `SOURCECRAFT_PAT` и
`SOURCEHEALTH_LIVE_REPO_URL`, не выполняет discovery и не сохраняет raw payload.
Полная операторская процедура и формат доказательств: [LIVE_ACCEPTANCE](LIVE_ACCEPTANCE.md).

## Большие репозитории и runtime

Обязательная финальная проверка ТЗ: настоящий SourceCraft repo ≥10 000 tracked files,
или ≥20 000 commits, или ≥500 МБ рабочей копии. Зафиксировать подготовку fixture,
commit SHA, число tracked files/commits/размер, memory/time, coverage, повтор/cache
и cleanup после timeout. Существующий local synthetic benchmark полезен для
производительности scanner, но не заменяет этот сценарий на платформе.

Не повторять дорогие benchmarks без изменения/регрессии. Browser acceptance отдельно:
loading/error/empty/no-data/partial, navigation, auth, report download. Build и HTTP
200 не означают проверку пикселей или полного пользовательского пути.
