# Финальная release-приёмка (Final Release Acceptance)

Этот документ содержит сводный статус release gates проекта SourceHealth.
Полная матрица обязательных требований M-01 — M-18 и ворот A — W зафиксирована в [MANDATORY_ACCEPTANCE_MATRIX](MANDATORY_ACCEPTANCE_MATRIX.md).
Контрольные сценарии скоринга зафиксированы в [SCORING_CONTROL_SCENARIOS](SCORING_CONTROL_SCENARIOS.md).

| Gate | Status | Evidence |
|---|---|---|
| **Large repository ($\ge 10\,000$ files)** | PASS | Live-приёмка репозитория на 10 000 файлов зафиксирована в [LARGE_REPO_ACCEPTANCE](LARGE_REPO_ACCEPTANCE.md). Локальный бенчмарк `python -m scripts.large_repository_benchmark` на 120, 10 000 и 10 001 файлах подтверждает сохранение resource bounds: на 10 000 файлов Health 82.31 (SAST bounded таймаутом 30 с); на 10 001 файле статус `partial`, coverage 15%, Health = null (не 0) |
| **Fixture boundary 10 001** | PASS | При 10 001 файле категории переходят в `partial`, Health = null (не превращается в 0), coverage падает до 15%. В локальном бенчмарке `file_limit` не фиксируется из-за предшествующего таймаута SAST (FILE-LIMIT PRECEDENCE: NOT PROVEN BY LOCAL 10K BENCHMARK DUE TO TIMEOUT PRECEDENCE); лимит файлов SAST протестирован детерминированно в `tests/test_sast.py` и `tests/test_large_fixture.py` |
| **Official SourceCraft AppSec** | PASS / LIVE | Реализован клиент `SourceCraftAppSecClient`; парсинг severity без утечек SARIF/кода: `docs/APPSEC_ACCEPTANCE.md` |
| **Documentation Quick Start (RU)** | PASS | Поддержан заголовок «Быстрый старт» в README без шелл-команд; регрессионный тест в `tests/test_mvp_snapshot.py` |
| **Production Caddy routing** | PASS | Взаимоисключающие `handle /api/*` (reverse_proxy) и `handle` (SPA `try_files` + static files) в `deploy/Caddyfile` |
| **Caddy syntax validation** | PASS | Реально выполнено `caddy validate --config deploy/Caddyfile` (exit code 0, `Valid configuration`) |
| **Caddy behavioral test** | PASS | Автоматизированный воспроизводимый тест `scripts/caddy_behavioral_smoke.py`: `/api/v1/health` $\to$ 200 backend JSON, `/some/spa/path` $\to$ 200 SPA `index.html`, `/api/not-real` $\to$ 404 backend JSON (не SPA index.html) |
| **SourceCraft API + CLI (M-15)** | PASS / EVIDENCED INTERPRETATION | Публичный [REST API](https://sourcecraft.dev/portal/docs/ru/sourcecraft/operations/api-start) (`api.sourcecraft.tech`) + AppSec API + Git-over-HTTPS/PAT; официальный CLI [`src`](https://sourcecraft.dev/portal/docs/ru/cli-ref/src) существует (`src api`, `src clone`, `src appsec`), но отдельный executable на сервере не вызывается; собственный `probe-sourcecraft` CLI протестирован |
| **Systemd Service Environment** | PASS | Устранены плейсхолдерные overrides `DATABASE_URL` в `sourcehealth-scheduler` и `sourcehealth-worker-code` |
| **Password Safety** | PASS | В `.env.production.example` задокументирована генерация URL-safe паролей без спецсимволов |
| **Explicit `/demo` fallback** | PASS | Маршрут `/demo`, баннер `DEMO DATASET / OFFLINE DEMO` |
| **Production deployment** | PASS / LIVE | <https://sourcehealth.tech> (live проверен 2026-09-23); воспроизводимый bundle в `deploy/` проверен скриптом `scripts/production_bundle_smoke.py` |
| **Docker socket invariant** | PASS | backend, worker, scheduler не имеют доступа к сокету Docker; изоляция через non-root/read-only |
| **Unit & Integration tests** | PASS | `python -B -m unittest discover -s tests`: **Ran 360 tests, OK (skipped=61)** |
| **Whitespace / Diff check** | PASS | `git diff --check` чист |
| **Frontend build & types** | PASS | `npm run build --prefix frontend` (2.89s) & `npm run types --prefix frontend` (zero drift) |
| **Browser mock acceptance** | PASS | `node scripts/run_browser_acceptance.mjs`: все 46 скриншотов успешно сформированы |
| **Leak sweep** | PASS | Ни одного токена, пароля или ключа в git diff и tracked working tree |
| **Local SAST Eligibility** | REPRODUCED / SCORING DECISION REQUIRED | Дискриминирующее доказательство в `tests/test_sast_eligibility.py` (Case A и Case B). Скоринг оставлен без скрытых изменений (`mvp-score-v1.2`), решение эскалировано владельцу |

## Scope guard & Owner Decisions

Этот PR не меняет scoring policy (`mvp-score-v1.2` остается канонической), контракты AppSec, OpenAPI схему или алгоритмы Source Soul.
- **P0 implementation blockers:** 0
- **P1 implementation blockers:** 0
- **OWNER / SCORING DECISION:** 1 — методологическое решение по включению находок Python AST / Secret-сканера в Code Health при `code_files_lexed == 0` (поведение воспроизведено в `tests/test_sast_eligibility.py`). Решение намеренно эскалировано владельцу No1se-pi под Scope Guard.
