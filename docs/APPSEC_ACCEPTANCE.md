# Приёмка official SourceCraft AppSec

## Контракт

Источник: live OpenAPI `https://appsec.sourcecraft.tech/openapi`, проверен 23.09.2026.
Используются только GET `/v1/scans/latest`, `/v1/scans/{scanUuid}` и `/v1/defect-groups`.
Авторизация — Bearer с подключённым пользователем SourceCraft PAT. `gitRepo` — UUID/ID из
обычного Repository API. Статус полноты читается из scan details как строка `FINISHED`.

## Безопасный data flow

`Yandex ID session → encrypted session PAT → re-encrypted run lease in Redis → RQ analysis_id → worker`.
Worker применяет один PAT к обычному SourceCraft API и отдельному AppSec client, затем удаляет
lease в `finally`. AppSec не имеет shared cache. Хранятся только scan UUID и счётчики открытых
groups по severity. Raw payload, SARIF, source snippets, descriptions и secret values запрещены.
Если cached analysis ещё не содержит complete official Security, connected PAT создаёт
новый queued run. Готовый cached run никогда не получает credential lease.

## Live evidence

Безопасный probe для организации `lct-hackaton-2026`, repository team-41, получил HTTP 200
от Repository API и AppSec latest/details. Scan был `FINISHED`; bounded collector завершил все
страницы и вернул санитизированный агрегат: critical 0, high 5, medium 13, low 5, всего 23.
PAT, response bodies и данные отдельных findings не записывались.

## Негативные состояния

- нет run credential или scheduled run: `NO_DATA / appsec_credential_unavailable`;
- 401/403/404: `NO_DATA`, а не нулевой score;
- unfinished scan: `PARTIAL`, `complete=false`;
- timeout, 429, 5xx, malformed response или pagination limit: source unavailable/partial без score.

Полная browser-приёмка запускается пользователем с Yandex ID session и подключённым PAT.
Private analysis, scheduled AppSec без live session и delegated Yandex ID → SourceCraft bridge не входят
в эту интеграцию.
