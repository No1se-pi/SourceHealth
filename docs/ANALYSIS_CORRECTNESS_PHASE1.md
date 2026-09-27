# Достоверность анализа: фаза 1

Фаза закрепляет корректность `mvp-score-v1.2`, не меняя веса, формулы категорий и production policy.

## CI/CD

Runtime-контракт явно переносит два независимых поля:

- `ci_configured: bool | null` — найден ли native SourceCraft CI;
- `ci_config_complete: bool` — можно ли по полному tracked snapshot доказывать отсутствие конфигурации.

Полный snapshot без CI вместе с полным пустым списком запусков даёт `CI=0`. Наличие конфигурации без запусков даёт `40`. Терминальные запуски используют `100 × success / (success + failed + timeout + rejected)`. Неполный snapshot не доказывает отсутствие CI. Если SourceCraft CI API недоступен, полный локальный snapshot без native CI остаётся достаточным независимым доказательством `CI=0`; без полного snapshot результат равен `NO_DATA`.

Custodes-like regression с `Activity=16.61`, `Documentation=80`, `Code Health=100`, остальными категориями `NO_DATA` даёт Health `68.98`. После доказанного `CI=0` Health равен `53.06`: ноль участвует в знаменателе, а `NO_DATA` — нет.

## Official AppSec

Security остаётся числовым только для полного official SourceCraft AppSec результата, полученного через immutable analysis credential lease. Два открытых `medium` findings дают `90` по неизменной формуле v1.2. Отсутствие PAT, ответы 401/403, незавершённый scan и неполная pagination дают ненулевую availability/error семантику и `Security=null`. Local SAST относится только к Code Health.

## Характеризация Activity v1.2

Фиксированное reference time: `2026-09-19T00:00:00Z`. Значения компонентов приведены по шкале 0..100.

| Сценарий | Activity | recent | recency | PR | contributors | release |
|---|---:|---:|---:|---:|---:|---:|
| A, очень активный | 100.00 | 100.00 | 100.00 | 100.00 | 100.00 | 100.00 |
| B, 20 commits в один день | 68.00 | 20.00 | 100.00 | 100.00 | 100.00 | 100.00 |
| C, обычный, последний commit 15 дней | 58.67 | 50.00 | 83.33 | 20.00 | 66.67 | 0.00 |
| D, та же история, 29 дней | 52.44 | 50.00 | 67.78 | 20.00 | 66.67 | 0.00 |
| E, та же история, 31 день | 31.56 | 0.00 | 65.56 | 20.00 | 66.67 | 0.00 |
| F, custodes-like, 56 дней | 18.44 | 0.00 | 37.78 | 0.00 | 66.67 | 0.00 |
| G, 90 дней | 3.33 | 0.00 | 0.00 | 0.00 | 66.67 | 0.00 |
| H, 180+ дней | 3.33 | 0.00 | 0.00 | 0.00 | 66.67 | 0.00 |
| I, полностью наблюдаемая пустая история | 0.00 | — | — | — | — | — |
| J, partial/unavailable Git | `NO_DATA` | — | — | — | — | — |

Формула монотонна внутри окон и защищена от burst: 20 commits за один день не максимизируют recent-компонент. Между 29 и 31 днём обнаружен скачок `20.88` пункта Activity из-за обнуления 30-дневного recent-компонента. Custodes-like низкий результат объясним сочетанием нулевых recent/PR/release и линейного угасания recency; он выглядит чрезмерно суровым, но одного набора недостаточно для безопасной калибровки.

`mvp-score-v1.3` в этой фазе не реализуется. Перед новой policy нужны replay на нескольких реальных репозиториях и отдельное утверждение формулы; v1.2 остаётся production default и полностью воспроизводимой.

## Наблюдаемость

Worker пишет ограниченные structured events для стадий и итоговые миллисекунды: `repository_metadata_ms`, `appsec_ms`, `issues_ms`, `cicd_ms`, `pull_requests_ms`, `contributors_ms`, `releases_ms`, `runtime_ms`, `scoring_ms`, `total_ms`. События содержат только analysis/repository id, имя стадии, availability, complete и стабильный error code. PAT, Authorization, cookies, source code, raw response и произвольный exception text не логируются.
