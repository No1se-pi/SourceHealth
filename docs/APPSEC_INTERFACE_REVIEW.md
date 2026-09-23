# SourceCraft AppSec interface review

Дата проверки: 2026-09-23.

Официальный public Swagger `https://api.sourcecraft.tech/docs/sourcecraft.swagger.json` скачан повторно: version `0.0.1`, 169 paths, SHA256 `dcd249cb7ad9247387ad76bd12b3d85c6a28a1cf05efd8c2fbbf0675f2cdfd8d`. Поиск по path names и schema names для `appsec`, `security`, `sast`, `sca`, `dependency`, `vulnerability`, `finding`, `incident`, `sarif`, `sbom`, `scan`, `secret` не нашёл findings/export resources. Найденные слова в отдельных discard routes не относятся к AppSec.

Официальная документация подтверждает, что UI SourceCraft показывает SAST incidents, статусы Open/Resolved/False Positive и экспорт SARIF; отдельные страницы описывают secret scanning с SARIF и dependency analysis с SBOM. Документация не предоставляет supported server-side API/auth contract для получения этих данных по PAT. Browser-only private RPC, cookie bridge и signed URL без подтверждённого contract не внедряются.

Итог: **BLOCKED BY OFFICIAL INTERFACE**. SourceHealth сохраняет `source=sourcecraft_appsec`, `availability=NO_DATA`, `error=appsec_interface_unconfirmed`; local SAST остаётся только `code_health`. Это честный внешний blocker, а не fake AppSec integration.

Official references:

- <https://sourcecraft.dev/portal/docs/ru/sourcecraft/operations/sast>
- <https://sourcecraft.dev/portal/docs/ru/sourcecraft/operations/secret-scan>
- <https://sourcecraft.dev/portal/docs/ru/sourcecraft/operations/supply-chain>
- <https://sourcecraft.dev/portal/docs/en/api-ref/>
