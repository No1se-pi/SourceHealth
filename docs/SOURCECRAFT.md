# Интеграция SourceCraft

Проверено по официальной [Swagger](https://api.sourcecraft.tech/docs/sourcecraft.swagger.json)
19.09.2026: info.version `0.0.1`, SHA-256 скачанного файла
`c3b1d84647cdf553cda63ff6e6ddf59d00ee36a5aa40470ad44607320639d7c3`.
Версия может не меняться при изменении методов. Fixtures в tests/mvp_fixtures.py
переписаны вручную по схемам, **не являются live responses**.

Дополнительные источники: [REST API](https://sourcecraft.dev/portal/docs/ru/sourcecraft/operations/api-start),
[CI/CD configuration](https://sourcecraft.dev/portal/docs/en/sourcecraft/ci-cd-ref/).
Отдельный предоставленный SCS draft 1.0.0 разобран в
[SOURCECRAFT_SECURITY_DRAFT](SOURCECRAFT_SECURITY_DRAFT.md); он не подтверждает
base URL/auth/security mapping.

## Клиент и бюджеты

Base URL строго `https://api.sourcecraft.tech`, PAT в Authorization Bearer.
Redirects запрещены; пользователь не задаёт host. GET-only, максимум 3 попытки при
transport errors/429/5xx. Retry-After до 10с; более долгий возвращает rate_limited.
401/403/404 не ретраятся. Response до 4 MiB, timeout по умолчанию 15с; User-Agent и
X-Request-ID задаёт клиент. Ошибки возвращают только безопасный code, не response body.

Pagination: page_size/page_token/next_page_token. Default клиента 100 страниц,
analytics profile ограничивает до 5 страниц на resource и 2000 уникальных items.
Общий deadline платформенной аналитики 120с, timeout запроса ≤10с. Import — deadline
45с. Коллектор сохраняет полученные items при последующей ошибке и ставит partial;
до первого item — source_unavailable. Полный пустой ответ — available, complete=true.
Дедупликация id не превращает ограниченный batch в полный snapshot каталога.

## Реализованные collectors

Префикс R = `/repos/{org_slug}/{repo_slug}`. Все методы подтверждены Swagger;
успешная live приёмка фиксируется только результатом операторских команд из
[LIVE_ACCEPTANCE](LIVE_ACCEPTANCE.md); contract fixtures сами по себе её не подтверждают.

Перед запуском инфраструктуры `probe-sourcecraft URL` проверяет metadata, Issues, CI/CD,
pull requests, contributors и releases. Команда не открывает PostgreSQL/Redis и печатает
только allowlisted JSON summary. Exit code: 0 — полный ответ, 1 — partial/outage ресурса,
2 — configuration/auth/repository/schema error.

| Collector | Endpoint / ключ списка | Сохраняемые поля и правила |
|---|---|---|
| RepositoryCollector | GET R | id, slug, явно public visibility, default_branch, is_empty, безопасный language.name |
| IssuesCollector | GET R/issues / issues | Без несовместимого filter query; private отбрасывается по visibility; id/slug, status.status_type, created_at/updated_at/completed_at |
| Issues comments enrichment | GET R/issues/{issue_slug}/comments / issue_comments | created_at; author.id сравнивается с issue.author.id только в памяти, self исключаются |
| CICollector | GET R/cicd/runs / runs | id/status, dates.created_at/started_at/finished_at, duration |
| PullRequestsCollector | GET R/pulls / pull_requests | id/status/created_at/updated_at |
| ContributorsCollector | GET R/contributors / contributors | Только id, без names/emails |
| ReleasesCollector | GET R/releases / releases | Только status=published; id/released_at, без notes |
| CatalogCollector | GET /repos / repositories | Глобальный public discovery; sort_by=created_at |
| CatalogCollector | GET /orgs/{org_slug}/repos / repositories | Org-scoped discovery; без неподдерживаемого sort_by |

Wire статусы Issues: initial/in_progress/paused/completed/cancelled; completed_at
маппится в closed_at. CI: created/prepared/processing/success/failed/canceled/timeout/
skipped/awaiting_approval/rejected; timestamps вложены в dates. Pull requests:
draft/open/discarded/merging/merged. Releases: draft/published/discarded, сохраняются
только published. Неизвестные enum/невалидные даты означают неполное наблюдение,
а не успешную догадку. Closed/response/duration semantics — [ANALYTICS](ANALYTICS.md).

Для comments budget — первые 10 issues, не более 2000 comments на issue и 5 страниц.
Неполная comments история оставляет latency null, не уничтожая полные issue counts.
Внешний ответ требует известного author.id у issue и каждого comment. Author IDs
не сохраняются в facts. Unanswered count и response rate также null при неполной истории.
Bodies, descriptions, release notes, CI error messages и персональные поля не
попадают в facts/report. Ключи и timestamp проходят allowlist/validation.

## Каталог и import

Глобальный `GET /repos` **теперь подтверждён официальным контрактом**; прежний вопрос
о неизвестном endpoint снят. DiscoverRepositories возвращает публичные repositories
в public организациях/проектах. Pagination не гарантирует snapshot consistency при
смене visibility/удалениях; не заявляем «все SourceCraft repositories».

CLI `discover [--organization SLUG] --limit 20` выполняет ограниченный batch
(1..100 repos, до 5 страниц, общий deadline 120с), повторно проверяет каждую public
запись через RepositoryCollector, делает idempotent upsert и ставит analysis в очередь.
HTTP POST /api/v1/repositories принимает только SourceCraft URL с session/Origin;
описание flow в [API](API.md), команды в [DEPLOYMENT](DEPLOYMENT.md).
Реальное наполнение каталога требует рабочего API доступа.

## Live наблюдение 19.09.2026

На `sourcecraft/documentation` выполнены GET repository metadata, issues,
CI runs, pulls, contributors, releases и отдельный GET /repos. Все семь попыток
дали `authentication_required` (HTTP 401); успешных items — 0. Raw bodies/PAT не
сохранялись. Это подтверждает обработку отказа доступа, **не** успешность wire mapping
на живых данных. Следующая приёмка: рабочий read PAT → sanitized fixtures → public
import → trusted worker → отчёт. Я ID session не заменяет SourceCraft PAT.

## AppSec boundary и другие открытые вопросы

AppSecCollector возвращает source=sourcecraft_appsec, availability=no_data,
error=appsec_interface_unconfirmed. Это ограничение интеграции, не отсутствие
уязвимостей. Нельзя подменять Security локальным SAST. Для подключения нужны base URL,
auth, полная OpenAPI, enums/severity/resolution, repository identity mapping и real
sanitized fixture. Policy имеет только внутренний нормализованный input, не fake client.

Private repository flow запрещён до подтверждения Я ID → SourceCraft permission bridge.
Likes остаются nullable: Repository.rating.value не объявляется числом likes.
**GET R/rating — реакция текущего пользователя; R/secrets — управление CI secrets,
а не secret scanning findings.** Ни один из них не используется для Security.

Clone остаётся public HTTPS `https://git.sourcecraft.dev/org/repo.git`, без передачи
PAT в clone URL. Issues/CI collectors не используют Git HEAD как ключ свежести.
