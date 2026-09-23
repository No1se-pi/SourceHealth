# Финальная release-приёмка

Этот документ содержит только текущие release gates. Исторические журналы из PR #14 сюда
не переносятся, чтобы не смешивать разные scoring и AppSec contracts.

| Gate | Status | Evidence |
|---|---|---|
| Large repository | PASS | Final post-PR13 run, 10 000 files, 10.707 s, cleanup PASS: [LARGE_REPO_ACCEPTANCE](LARGE_REPO_ACCEPTANCE.md) |
| Fixture boundary 10 001 | PASS | benchmark: `file_limit` → partial, score не превращается в 0 |
| Official SourceCraft AppSec | PASS / LIVE | implementation merged in PR #12; current contract/evidence: `docs/APPSEC_ACCEPTANCE.md` |
| `/demo` fallback | PASS | explicit `/demo`, prominent `DEMO DATASET / OFFLINE DEMO` |
| Production deployment | PASS / LIVE | <https://sourcehealth.tech>; reproducible bundle in `deploy/` |
| Docker socket invariant | PASS | backend, worker, scheduler have no socket; only host worker-code is trusted |
| Unit / Ruff / diff | run in PR | commands from `docs/TESTING.md` |
| Integration | run in PR | PostgreSQL `_test`, Redis DB 15 |
| Frontend build | run in PR | `npm ci --prefix frontend && npm run build --prefix frontend` |

## Final run fields

После merge PR #13 повторить live large run и добавить только URL, HEAD, file/commit/size
threshold, analysis id, duration, terminal status, Health, coverage и cleanup. PAT, headers,
cookies, raw responses и source contents запрещены.

## Scope guard

Этот PR не меняет scoring policy, AppSec implementation, OpenAPI/generated types или
Source Soul/explainability components.
