# Интеграция SourceCraft

Обновление 16 сентября: команда предоставила `SCS_API_1.0.0_draft.pdf` с описанием
отдельного Security API. Методы и оставшиеся пробелы вынесены в [SOURCECRAFT_SECURITY_DRAFT](SOURCECRAFT_SECURITY_DRAFT.md).
Ниже сведения о публичной Swagger от 15 сентября; отсутствие AppSec в ней больше
не означает отсутствие документации Security API. Draft не подтверждает live доступ.

Проверено 2026-09-15 по официальным ресурсам:

- [Работа с REST API](https://sourcecraft.dev/portal/docs/ru/sourcecraft/operations/api-start).
- [Интерактивная документация](https://api.sourcecraft.tech/docs/index.html).
- [Публичная Swagger specification](https://api.sourcecraft.tech/docs/sourcecraft.swagger.json),
  версия info `0.0.1`, «Bleeding edge of Public REST API of SourceCraft».
- [Документация платформы](https://sourcecraft.dev/portal/docs/ru/).

Спецификация может меняться без смены info.version. Перед новой интеграцией читать
конкретную response schema, сохранять sanitized fixture и дату проверки в PR.

## Клиент

Base URL `https://api.sourcecraft.tech`. PAT передаётся в `Authorization: Bearer`.
Нет redirects и пользовательского произвольного base URL. Все реализованные запросы
GET, максимум 3 попытки для transport errors/429/5xx. Retry-After соблюдается до 10с;
большая задержка возвращает rate_limited для последующего повтора scheduler.
401/403/404 и прочие 4xx не ретраятся. Timeout 15с, response до 4 MiB,
pagination по page_size/page_token/next_page_token, default max 100 страниц.
Повторяющийся token, неверный payload и превышение лимита — явная ошибка.

User-Agent и X-Request-ID устанавливает клиент. Наличие подтверждённого response
request ID у платформы не предполагается. Ошибки содержат только safe code, не body.
`iter_items()` отдаёт items по мере чтения; collector обязан сохранить уже собранную
часть и выставить partial при сбое последующей страницы. Не превращать partial в
нулевое число открытых issues.

## Integration checklist

Префикс `R = /repos/{org_slug}/{repo_slug}`. PAT означает официальный способ
аутентификации; anonymous/public доступ каждого метода отдельно не принят сквозным тестом.

| Data | Требуется ТЗ | Official source | Endpoint/interface | Auth | Implemented | Open question |
|---|---|---|---|---|---|---|
| Repository metadata | Да | Swagger GetRepository | GET R | PAT | Client + allowlist collector | Public live acceptance; rename reconciliation |
| Issues | Да | ListRepositoryIssues | GET R/issues, items=issues | PAT | Общая pagination, бизнес-collector planned | Filter/windows, private issues в public repo |
| CI/CD | Да | ListRuns | GET R/cicd/runs, items=runs | PAT/публичность workflow | Client foundation | Доступный объём history, критерий not_configured |
| AppSec SAST | Да | SCS Backend API 1.0.0 draft, 16.09 | Отдельные /v1/scans, /v1/defect-groups, /v1/findings | Не подтверждено | Boundary, NO_DATA | Base URL, auth, schemas, mapping; см. draft notes |
| AppSec SCA | Да | Тот же SCS draft | Те же методы; engine type согласовать со схемой | Не подтверждено | Boundary | Exact schema + live fixture |
| Secret scanning | Да | Тот же SCS draft | Те же методы; SECRETS указан для отчётов | Не подтверждено | Boundary | Enum конкретного метода + live fixture |
| PR/MR | Да, activity | Swagger Pull Requests | GET R/pulls | PAT | Foundation клиента | Полнота полей/времени/статусов |
| Reviews | Бонус | Swagger pull comments/reviewers/decision | GET R/pulls/{pull_request_slug}/comments, /reviewers | PAT | Planned | История review transitions и длительности |
| Contributors | Да, activity | Swagger contributors | GET R/contributors | PAT | Planned | Bots, aliases, privacy email |
| Releases | Да, activity | Swagger releases | GET R/releases | PAT | Planned | Draft/released и нужное окно |
| Likes/rating | Да, leaderboard | Repository.rating / RepositoryRating | GET R, поле rating | PAT | Поле storage nullable; сбор planned | Правило mapping reaction_counts в likes |
| Git clone | Для code/history | SourceCraft HTTPS clone | https://git.sourcecraft.dev/org/repo.git | Public clone | Прежний Docker workflow | Code profile, точный SHA, дисковая квота |
| Общий каталог public repo | Да, желательно полный охват | Каталог платформы | UI find/repositories; org-scoped GET /orgs/{org_slug}/repos | PAT для API | Planned | Подтверждённый глобальный discovery interface |

**GET R/rating возвращает реакцию текущего пользователя**, а не общий счётчик лайков.
Использовать Repository.rating только после согласования семантики. Не выдавать
число rating.value за likes без объяснения. **R/secrets управляет CI-секретами**,
это не выгрузка результатов secret scanning; этот endpoint клиент продукта не вызывает.

## AppSec boundary

`AppSecCollector` сейчас возвращает `source=sourcecraft_appsec, availability=no_data,
error=appsec_interface_unconfirmed`. Это статус незавершённой интеграции, не факт
отсутствия сканирования у проекта. Нельзя подменить его данными нашего scanner.

Перед реализацией запросить у организаторов/документации: официальный интерфейс
выгрузки (полная OpenAPI SCS draft, base URL/auth), permissions, pagination, scanner type, severity, open/resolved/false-positive,
fingerprint/reference, scan timestamp, соответствие HEAD, ограничения по private repo.
Сохранить fixture без secret values и source snippets; добавить contract test и ссылку
на источник. Лишь затем подключать collector и численную Security policy.

## Что сохраняется

RepositoryCollector сейчас сохраняет allowlist id/slug/default_branch/visibility/is_empty,
принимает только явно public metadata. description, clone_url, произвольные links,
исходные тексты и credentials не попадают в report. Unit HTTP fixtures не требуют PAT.
Отдельный live smoke включается переменными из [TESTING](TESTING.md).
