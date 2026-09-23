# PR description — final MVP closure

## Goal

Закрыть оставшиеся обязательные технические gate SourceHealth: large-repository
поведение, size-skew/performance, фактический AppSec source-of-truth и release readiness.

## Mandatory status

- Large SourceCraft repository: **PASS** — public fixture, 10 000 tracked files, full run и cleanup.
- Anti-size-skew: **PASS** — 120 и 10 000 файлов дают одинаковый score; 10 001 даёт bounded partial.
- False positives/performance: **PASS** — deterministic density, findings budget и no raw source output.
- Official SourceCraft AppSec: **BLOCKED WITH EVIDENCE** — свежий Swagger не публикует supported findings contract; NO_DATA сохранён.
- Yandex ID / SourceCraft browser: **BLOCKED** — нужен ручной owner run по чек-листу.
- Deployment bundle: **PREPARED** — Caddy, production compose, worker-code systemd и scheduler templates.
- Fallback demo: **PASS** — явный `/demo` с маркировкой `DEMO DATASET / OFFLINE DEMO`.

## Verification

Unit, Ruff, OpenAPI/generated TypeScript, frontend build, integration PostgreSQL/Redis/RQ,
compose smoke и Docker snapshot smoke зафиксированы в [FINAL_RELEASE_ACCEPTANCE](FINAL_RELEASE_ACCEPTANCE.md).
Live large details — [LARGE_REPO_ACCEPTANCE](LARGE_REPO_ACCEPTANCE.md); performance —
[PERFORMANCE_ACCEPTANCE](PERFORMANCE_ACCEPTANCE.md); AppSec — [APPSEC_INTERFACE_REVIEW](APPSEC_INTERFACE_REVIEW.md).

## External blockers

1. Владелец должен вручную пройти real Yandex login и SourceCraft PAT flow; secrets в чат и PR не передаются.
2. Для production нужны VPS/DNS и регистрация HTTPS OAuth callback `https://sourcehealth.tech/api/v1/auth/yandex/callback`.
3. SourceCraft должен предоставить supported server-side AppSec contract, если требуется численный Security score.
