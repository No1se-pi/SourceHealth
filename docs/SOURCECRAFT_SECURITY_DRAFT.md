# SourceCraft Security API: полученный draft и границы подтверждения

Источник: предоставленный командой PDF `SCS_API_1.0.0_draft.pdf`, 3 страницы,
«Работа с SourceCraft Security API», обновлён 16.09.2026 10:55, экспорт 10:56.
SHA-256 файла: `b8417e490ee36f2483fb2f52455b275adcf67df5ee0a5df92e2886d286e00f17`.
Это описание SCS Backend API 1.0.0 по выгрузке OpenAPI, **не сама OpenAPI и не live test**.
PDF не включён в репозиторий; здесь сохранены необходимые команде выводы.

## Read-only методы из документа

| Задача | Метод | Идентификатор / особенности |
|---|---|---|
| Последний scan | GET `/v1/scans/latest` | `gitRepo`, возвращает ScanSummaryDto с uuid |
| История scans | GET `/v1/scans` | status по умолчанию FINISHED; pagination |
| Scan details | GET `/v1/scans/{scanUuid}` | UUID scan, query gitRepo |
| Группы | GET `/v1/defect-groups` | gitRepo; явно scanUuid; type/severity/status filters |
| Группа | GET `/v1/defect-groups/{publicId}` | Номер группы внутри repo, не UUID |
| Findings | GET `/v1/findings` | gitRepo, defectGroupUuid, pagination |
| История группы | GET `/v1/activities` | gitRepo, defectGroupPublicId, pagination |

`gitRepo` — внутренний ID строкой либо публичный UUID repository. Slug/Git URL не
поддерживаются по этому описанию. Нельзя считать наш `RepositoryRef.id` UUID платформы:
нужна подтверждённая связь `sourcecraft_id`/getRepo id/uuid. Сам getRepo в PDF не описан.

Pagination: response `data`, `nextPageToken`, `totalSize`; request `pageSize` 1..250,
default 50; первая страница с явным `pageToken=`. Признак конца страниц не определён.
Текущий SourceCraftClient использует другой формат pagination и единственный host
основного API; этот draft нельзя подключить простой заменой URL без нового проверенного
transport/collector контракта. Пределы страниц и защита от повторяющихся tokens обязательны.

Явный scanUuid связывает группы с одним scan и отменяет scanType. Без scanUuid выбор
последнего запуска зависит от scanType (CI/audit). Enum типов движков отличается между
операциями. Числовые severity/status не имеют опубликованной в PDF таблицы соответствия;
не угадывать значения по порядку enum.

## Что ещё нужно получить

1. Base URL Security API, auth scheme и read permissions. PDF прямо оставляет их открытыми.
2. Полную OpenAPI с DTO, обязательностью query fields и mapping числовых enum.
3. Подтверждённую repository identity mapping, связь scan с commit SHA и свежесть scan.
4. Завершение pagination, формат ошибок, rate limits, поведение при отключённом AppSec.
5. Очищенную реальную fixture SAST/SCA/secrets и проверку доступа на сервисе.

Поэтому текущий `AppSecCollector` остаётся NO_DATA, public error code
`appsec_interface_unconfirmed` сохранён. Теперь он означает неподтверждённый рабочий
контракт/доступ, а не отсутствие описанных маршрутов. Security Score остаётся null.

## Что не выполнять в foundation closure

PDF также описывает изменение статусов/комментариев, links, upload внешних отчётов,
генерацию PDF/SARIF и admin settings. Это справочные возможности, а не поручение их
вызвать. В этой задаче никаких запросов к ним нет. Загрузка нашего SARIF обратно в
AppSec не делает local SAST независимым официальным Security evidence.
Не сохранять raw descriptions/snippets, auth material или presigned URLs из будущих ответов.
