# Финальная release-приёмка (Final Release Acceptance)

Этот документ содержит сводный статус release gates проекта SourceHealth.
Полная матрица обязательных требований M-01 — M-18 и ворот A — W зафиксирована в [MANDATORY_ACCEPTANCE_MATRIX](MANDATORY_ACCEPTANCE_MATRIX.md).
Контрольные сценарии скоринга зафиксированы в [SCORING_CONTROL_SCENARIOS](SCORING_CONTROL_SCENARIOS.md).

| Gate | Status | Evidence |
|---|---|---|
| **Large repository ($\ge 10\,000$ files)** | PASS | Локальный бенчмарк `python -m scripts.large_repository_benchmark` на 120, 10 000 и 10 001 файлах: 10 000 файлов завершаются успешно (Health 82.31); 10 001 файл дает `file_limit`, статус `partial`, Health = null: [LARGE_REPO_ACCEPTANCE](LARGE_REPO_ACCEPTANCE.md) |
| **Fixture boundary 10 001** | PASS | Скан останавливается по `file_limit`, Health не превращается в 0, coverage падает до 15% |
| **Official SourceCraft AppSec** | PASS / LIVE | Реализован клиент `SourceCraftAppSecClient`; парсинг severity tanpa утечек SARIF/кода: `docs/APPSEC_ACCEPTANCE.md` |
| **Documentation Quick Start (RU)** | PASS | Поддержан заголовок «Быстрый старт» в README без шелл-команд; регрессионный тест в `tests/test_mvp_snapshot.py` |
| **Production Caddy routing** | PASS | Взаимоисключающие `handle /api/*` (reverse_proxy) и `handle` (SPA `try_files` + static files) в `deploy/Caddyfile` |
| **Systemd Service Environment** | PASS | Устранены плейсхолдерные overrides `DATABASE_URL` в `sourcehealth-scheduler` и `sourcehealth-worker-code` |
| **Password Safety** | PASS | В `.env.production.example` задокументирована генерация URL-safe паролей без спецсимволов |
| **Explicit `/demo` fallback** | PASS | Маршрут `/demo`, баннер `DEMO DATASET / OFFLINE DEMO` |
| **Production deployment** | PASS / LIVE | <https://sourcehealth.tech>; воспроизводимый стек в `deploy/compose.prod.yaml` |
| **Docker socket invariant** | PASS | backend, worker, scheduler не имеют доступа к сокету Docker; изоляция через non-root/read-only |
| **Unit tests** | PASS | `python -B -m unittest discover -s tests`: **205 tests PASS** (skipped=28) |
| **Whitespace / Diff check** | PASS | `git diff --check` чист |
| **Frontend build & types** | PASS | `npm run build --prefix frontend` (1.57s) & `npm run types --prefix frontend` (zero drift) |
| **Browser mock acceptance** | PASS | `node scripts/run_browser_acceptance.mjs`: все 46 скриншотов успешно сформированы |
| **Leak sweep** | PASS | Ни одного токена, пароля или ключа в репозитории |

## Scope guard

Этот PR не меняет scoring policy (`mvp-score-v1.2` остается канонической), контракты AppSec, OpenAPI схему или алгоритмы Source Soul.
Все изменения строго направлены на закрытие release-gate PR #15 и исправление известных блокеров.
