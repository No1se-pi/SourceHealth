# REST API v1

Машиночитаемый контракт: [openapi.json](openapi.json), генерируется из `api/schemas.py`
и FastAPI routes. При запущенном API: `/docs` и `/openapi.json`. TypeScript types
генерируются из этого файла; Python dataclass internals frontend не использует.

## Endpoints

| Метод и URL | Результат | Доступ / примечание |
|---|---|---|
| GET `/api/v1/health` | HealthResponse, 200 | Liveness, без соединения с БД |
| GET `/api/v1/repositories` | RepositoryPage, 200 | Только visibility=public |
| POST `/api/v1/repositories` | RepositoryDetails, 201 | Сессия Я ID + exact Origin; проверка public через SourceCraft API |
| GET `/api/v1/repositories/{repository_id}` | RepositoryDetails, 200 | Private/unknown/nonexistent → 404 |
| GET `/api/v1/repositories/{repository_id}/analyses/latest` | AnalysisSummary, 200 | Последний законченный run; если нет → 404 |
| GET `/api/v1/repositories/{repository_id}/analyses?limit=20&offset=0` | AnalysisPage, 200 | Все статусы public repo; queued_at DESC, id DESC |
| POST `/api/v1/repositories/{repository_id}/analyses` | AnalysisSummary, 202 | Сессия Я ID + exact Origin; public repo |
| GET `/api/v1/analyses/{analysis_id}` | AnalysisDetails, 200 | Повторная проверка visibility repo |
| GET `/api/v1/analyses/{analysis_id}/report.md` | text/markdown, attachment | completed/partial; иначе 409 |
| GET `/api/v1/auth/yandex/login` | 302 к Я ID + opaque state cookie | Без настройки 503 |
| GET `/api/v1/auth/yandex/callback?code=…&state=…` | 303 `/auth/callback` + session cookie | State/PKCE + OAuth exchange |
| POST `/api/v1/auth/logout` | 204 | Exact Origin; удаляет серверную сессию |
| GET `/api/v1/me` | UserDTO, 200 | Без сессии 401 |

Нет 501 endpoints с выдуманными результатами. Реализовано session-scoped подключение
пользовательского SourceCraft PAT и выдача доступных этой сессии repositories. Private
analysis и админка отсутствуют.

## Pagination и сортировка

`GET repositories?limit=20&offset=0&sort=health_score&language=Python`.
`limit=1..100`, `offset=0..100000`, language — точное совпадение, optional.
`sort=health_score|likes|last_activity`; descending, NULLS LAST, затем UUID ascending.
По умолчанию Health. Ответ `{items, limit, offset, has_more}`. Total не вычисляется.
Offset pagination может сдвигаться при конкурентном изменении рейтинга: frozen
snapshot не обещается. Для массового каталога оценить cursor pagination через ADR.

## DTO

- RepositorySummary: UUID id; org/repo slugs; canonical_url; visibility; nullable
  health_score/language/likes/last_activity_at/latest_analysis_id.
- RepositoryDetails: Summary + sourcecraft_id/default_branch/head_sha.
- AnalysisSummary: UUID id/repository_id; profile; status/trigger; queued_at/started_at/completed_at;
  nullable head_sha/health_score; scoring_policy_version/analyzer_contract_version/error_code.
- AnalysisPage: items, limit, offset, has_more. История использует стабильный дополнительный
  порядок по UUID при одинаковом queued_at; total не вычисляется.
- AnalysisDetails: Summary + category_scores/data_coverage/recommendations/checks.
- `score_preview`: производный nullable `ScorePreviewDTO` в AnalysisDetails,
  RepositorySummary и RepositoryDetails; не является Health Score и не влияет на сортировку.
- AnalysisDetails.score_coverage: nullable объект, вычисленный backend из сохранённых
  category scores и известных весов policy; nominal_weight_percent, scored_categories,
  unscored_categories, partial_categories. Для неизвестной policy — null. Не означает
  процент проверенных файлов или полноту частичных категорий; frontend не копирует веса.
- CategoryScore: category, nullable score, availability, explanation, evidence_refs.
- AnalyzerResult: analyzer, status, availability, source, category, versions, metrics,
  findings, metadata, safe error, evidence. Metrics имеют свой analyzer contract.
- Evidence: id/source/type/reference/summary + nullable url/location/timestamp.
- Recommendation: id/category/title/description/priority/evidence_refs/suggested_action/expected_impact.
- UserDTO: внутренний UUID id; без email, OAuth token и SourceCraft PAT.

Timestamps — UTC ISO-8601. Nullable время означает ещё не наступивший этап.
`health_score=null` нельзя превращать в `0` через `value || 0` или `Number(null)`.
Проверять `value === null`, показывать отдельную подпись.

## POST и polling

Import: `POST /api/v1/repositories`, body `{"url":"https://sourcecraft.dev/org/repo"}`.
Допустим только canonical SourceCraft URL (до 512 символов); arbitrary Git URL не
принимается. RepositoryCollector проверяет явно public visibility; упsert сохраняет
внутренний UUID существующего repo. Повторный import также возвращает 201 с тем же id.
Неподтверждённый/private/not-found repo — 404, недоступная проверка/401 внешнего API —
503 `public_repository_unverified`; invalid URL — 422 `invalid_sourcecraft_url`.
Требуются session cookie и exact Origin. Я ID не даёт private SourceCraft permissions.
Import сам не запускает анализ: frontend переходит на страницу repo с существующей
кнопкой запуска. CLI register/discover дополнительно создают analysis run.

Запуск анализа: POST body `{"force_refresh": false}`, `Content-Type: application/json`, session
cookie и Origin, точно совпадающий с PUBLIC_ORIGIN. Ответ 202 с реальным run,
включая cached terminal result. completed/partial/failed — terminal; остальные
frontend опрашивает раз в 2 секунды. Повторный POST возвращает активный run.
`force_refresh=true` сейчас 403: Я ID не подтверждает права SourceCraft. Операторский
force существует в application, HTTP policy предстоит согласовать.

Для `mvp-v1` AnalysisDetails возвращает шесть category slots и category-level
`data_coverage`; checks дополнительно содержат documentation, technical_debt, issues,
cicd, platform_activity. Score — по [SCORING](SCORING.md), текущая policy `mvp-score-v1.2`.
`head_sha` — фактический snapshot. Старые профили сохраняют check-level coverage и
nullable baseline. Snapshot failure/недоступный AppSec допускают partial report.

## Ошибки и приватность

```json
{"code":"analysis_not_found","message":"analysis_not_found","request_id":"UUID"}
```

Message сейчас равен code; UI локализует по нему. 400 — OAuth state; 401 — сессия;
403 — Origin/permissions; 404 — недоступная сущность; 409 — report not ready;
422 — validation; 503 — зависимость/config; 500 — безопасная внутренняя ошибка.
`X-Request-ID` есть в ответах. API использует `Cache-Control: no-store`.

Запрещены абсолютные filesystem paths, PAT, OAuth token, исходные строки/секреты,
tracebacks и raw exception text. DTO не очищает произвольные metrics автоматически:
allowlist на collector/analyzer boundary обязателен и проверяется тестами.

## Изменение API

```powershell
python scripts/export_openapi.py
npm run types --prefix frontend
npm run build --prefix frontend
```

OpenAPI, generated.ts, docs и tests меняются в одном PR. Новые analyzer metrics
обычно не требуют изменения DTO. Breaking HTTP change требует согласования и новой
версии либо явной миграции до первого общего deployment.
## SourceCraft connection endpoints

Все endpoints требуют Я ID сессию; изменения — точный Origin.
`POST /api/v1/sourcecraft/connection` принимает `{pat}` и возвращает только
`connected`/`expires_in`; `GET /api/v1/sourcecraft/connection` возвращает статус;
`DELETE /api/v1/sourcecraft/connection` удаляет локальный credential. PAT хранится только
как AES-GCM ciphertext в Redis, имеет TTL не дольше текущей сессии и
`SOURCECRAFT_CONNECTION_TTL`.

`GET /api/v1/sourcecraft/repositories?organization=...` возвращает до 100 URL,
`visibility`/`can_analyze` и `has_more`; ответ `no-store`, без credential и сторонних
descriptions. Private/internal элементы доступны только текущей сессии в этом ответе и
не попадают в public каталог. Анализ private/internal repositories по-прежнему запрещён.
