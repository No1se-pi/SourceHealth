# Закрытие foundation — 16 сентября 2026

## Изменения и статус

| Задача | Статус | Результат |
|---|---|---|
| Frontend contract CI | DONE | OpenAPI → TS без diff, build; прежний CI сохранён |
| FastAPI routers | DONE | health/auth/repositories/analyses; app.py — composition root |
| GitActivity в background pipeline | DONE | code-v1 → checks.git_activity → PostgreSQL → HTTP |
| DockerAnalysisRuntime integration | DONE | AnalysisRuntime, один clone/scan для Git+SAST, safe converter |
| Compose E2E | DONE | Реальный build/up/migrate/health/worker; изолированный cleanup; Ubuntu CI |
| Git workflow | DONE | feature/* → PR → Dev-No1se → release PR → main |
| Foundation baseline | DONE | Границы зафиксированы; следующая работа — продуктовая аналитика |

Основные файлы: `api/app.py`, `api/dependencies.py`, `api/routers/*`,
`application/{jobs,pipeline,__main__}.py`, `runtime.py`, `runtime_results.py`,
`settings.py`, `compose.yaml`, `.env.example`, `scripts/compose_smoke.py`,
`.github/workflows/tests.yml`, `tests/test_runtime_pipeline.py`, `tests/test_integration.py`.
Обновлены ARCHITECTURE/BACKEND/ANALYTICS/JOBS_AND_CACHE/SECURITY/DEPLOYMENT/TESTING,
DEVELOPMENT/ROADMAP и SourceCraft draft notes. Core, DTO, initial migration и legacy
CLI/SARIF/container формат не менялись. OpenAPI/generated.ts совпадают с baseline.

## Поток анализа

```text
POST → queued AnalysisRun → очередь по persisted profile
  platform-v1 → обычный worker → platform facts
  code-v1 → trusted worker-code → platform facts + AnalysisRuntime
    → DockerAnalysisRuntime → один временный clone → offline Git + SAST → cleanup
    → runtime_results → AnalyzerResult
→ общий AnalysisReport → ScoringEngine → PostgreSQL → HTTP / Markdown
```

Runtime exception/timeout/clone failure/невалидный check не удаляет platform report.
Cleanup failure не считается полным успехом. Local SAST = code_health/sourcehealth_local;
Security только sourcecraft_appsec. NO_DATA не становится 0; Health Score остаётся null.
Выполнение target code запрещено, прежние ограничения sandbox сохранены.

## Выполненные локальные проверки

Все Python команды выполнены в `.venv` с server/dev dependencies:

- `pip install -r requirements-server.lock`, `pip install -e '.[dev,server]'`, `pip check` — успешно.
- `python -B -m unittest discover -s tests -v` с настоящими PostgreSQL/Redis —
  132 tests: 130 успешно, 2 skip (Unix FIFO на Windows и live SourceCraft opt-in).
- `python -m ruff check .` — успешно.
- `python -m alembic upgrade head`, `python -m alembic check` на `_test` PostgreSQL — успешно, новых операций нет.
- `python scripts/export_openapi.py`, `npm ci --prefix frontend`, `npm run types --prefix frontend`,
  `git diff --exit-code -- docs/openapi.json frontend/src/api/generated.ts` — успешно, diff отсутствует.
- `npm run build --prefix frontend` — успешно.
- `docker compose config --quiet`, `python scripts/compose_smoke.py` — успешно:
  build, migration, PostgreSQL/Redis/backend healthy, HTTP health 200, зарегистрированный worker,
  удаление только временных smoke volumes через `down -v`.

9 новых unit tests покрывают runtime boundary; integration scenario дополнительно
проверяет success/partial/exception/disabled через настоящий RQ/PG/HTTP с fake runtime.
Статус GitHub CI и exact merge SHA следует смотреть в release PR и финальном отчёте.

## Границы приёмки

Блокеров для foundation closure нет. Runtime integration подтверждена fixtures и
реальными внутренними сервисами, **не live SourceCraft clone**. В этой задаче не выполнены
live Я ID/AppSec, визуальная приёмка и публичный cloud deployment. Trusted code worker
требует выделенной Linux машины; обычный Compose не получает Docker socket.
Точный SHA/pinning, code cache, disk quotas и cleanup после смерти хоста остаются
следующими операционными задачами, не обещанием готового массового публичного scanning.

Новый [SCS draft](SOURCECRAFT_SECURITY_DRAFT.md) уточняет маршруты Security API;
base URL/auth/полные схемы/live fixture ещё нужны. Это не блокирует frontend и остальные категории.

## Ручной baseline tag

Автоматически тег не создаётся. После зелёного release PR использовать exact проверенный
merge SHA из финального отчёта. Сначала убедиться, что `foundation-v1` ещё не существует
локально или на origin; существующий тег не менять.

```bash
git tag -a foundation-v1 <verified-merge-SHA> -m "SourceHealth foundation v1"
git push origin foundation-v1
```
