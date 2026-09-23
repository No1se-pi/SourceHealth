# Детерминированная методика mvp-score-v1.3

`MVPPolicy` включена для `mvp-v1`. `platform-v1` и `code-v1` сохраняют
`UnconfiguredPolicy / unconfigured-v1` с nullable score. Policy не выполняет I/O,
не использует wall clock, ML, LLM или likes; повтор одинаковых checks даёт тот же score.
Определения метрик и ограничения охвата — [ANALYTICS](ANALYTICS.md).
Изменение 20.09.2026: v1.1 исключает self-comments, учитывает долю issues без ответа
и использует отдельную полноту Documentation/Debt. Старые v1 reports не меняются;
новая policy version автоматически меняет fingerprint нового запуска.
Изменение 21.09.2026: v1.2 не оценивает полностью пустой issue tracker как 100 и
ограничивает недавнюю Git-активность меньшим из signals commit count/active days.
Изменение 23.09.2026: v1.3 считает local SAST по severity density на 100 уникальных
поддерживаемых code files. Python AST findings теперь участвуют в Code Health;
нейтральные data files не меняют знаменатель. Старые v1.2 reports не пересчитываются.

## Итог и coverage

| Категория | Номинальный вес |
|---|---:|
| documentation | 15 |
| cicd | 15 |
| security | 20 |
| activity | 15 |
| issues | 15 |
| code_health | 20 |

`H = Σ(weight[c] × score[c]) / Σ(weight[c])` только для рассчитанных категорий.
Health публикуется, если рассчитаны **≥3 категории и ≥50 из 100 номинальных весов**;
иначе `health_score=null`. Всегда возвращаются шесть slots. Округление категорий и
итога — до 2 знаков. Security NO_DATA оставляет максимум 80 номинальных весов;
пять остальных категорий могут дать численный Health при явном неполном coverage.

NO_DATA/SOURCE_UNAVAILABLE/ERROR не превращаются в 0. Outage исключает компонент,
а не назначает штраф проекту. Это может изменить итог из-за изменения состава весов;
сравнивать scores следует вместе с coverage и policy version. `data_coverage` профиля
mvp-v1 содержит availability шести категорий; count и nominal weight выводятся из
slots с `score != null`. PARTIAL может иметь score только из полных независимых
компонентов Activity/Code Health. Неполные Issues/CI/docs/debt не оцениваются.
API вычисляет `score_coverage` по известной сохранённой policy; UI показывает рядом
со Score процент номинального веса, категории без оценки и partial категории.
Например, 80% и Security без оценки не означают проверенную безопасность.

Обозначение `C(x)=max(0,min(1,x))`. Внутри категории известные компоненты усредняются
по их внутренним весам; неизвестные исключаются. Numeric score требует evidence.

## Documentation

Сумма баллов за true-признаки полного snapshot:
README 20, LICENSE 15, run 20, build 10, test 15, CONTRIBUTING 5, CODEOWNERS 5, docs 10.
README size/headings — диагностические метрики, отдельного бонуса не дают.
Все false при полном обходе дают 0; partial — null.

## Issues

| Компонент | Формула 0–100 | Внутренний вес |
|---|---|---:|
| Stale | `100 × (1 − C(stale_ratio))` | 60 |
| External response | `100 × external_response_rate × (1 − C(median_first_external_response_hours / 168))` | 20 |
| Close | `100 × (1 − C(median_close_hours / 720))` | 20 |

Stale обязателен; при неполной comments истории response-компонент исключается.
Если история полная, но ответов нет, response-компонент равен 0 (rate=0, median=null).
Медиана считается среди ответивших, rate — среди всех issues; быстрые ответы меньшинству
не дают всем 100. Self-comment не является ответом. Полный пустой список наблюдаем,
но score=null: отсутствие задач не доказывает качество issue management.
Partial pagination не оценивается. Семантика первого комментария
и ограниченного comments budget явно указана в ANALYTICS.

## CI/CD

`100 × success / (success + failed + timeout + rejected)` при полном списке и
непустом знаменателе. Подтверждённое отсутствие нативной конфигурации — 0.
Конфигурация есть, полный список runs пуст — 40 (настроено, но исполнение не доказано).
Только canceled/skipped/in-progress runs — null. Outage/partial — null.
Duration/recent failures/latest status информативны, не меняют формулу v1.

## Activity

| Компонент | Формула | Вес |
|---|---|---:|
| Recent activity | `100 × min(C(commits_last_30_days/20), C(active_days_last_30_days/5))` | 40 |
| Последний commit | `100 × (1 − C(days_since_last_commit / 90))` | 40 |
| Обновлённые PR 30 дней | `100 × C(recent_pr_activity / 5)` | 10 |
| Contributors | `100 × C(contributors_count / 3)` | 5 |
| Последний release | `100 × (1 − C(days_since_release / 365))` | 5 |

Нужен полный Git result. Burst из множества commits в один день не максимизирует recent activity.
Полная пустая Git-история даёт 0; недоступная — null.
Полное отсутствие releases даёт 0 для release-компонента. Неизвестные platform
компоненты исключаются, категория помечается partial. Давность release вычисляется
по сохранённому reference_time platform analyzer. PR count/merged count — диагностика.

## Code Health

| Компонент | Формула | Вес |
|---|---|---:|
| TODO/FIXME density | `100 × (1 − C(marker_density / 5))` | 40 |
| Большие файлы | `100 × (1 − C(large_files / code_files))` | 10 |
| Возраст маркеров | `100 × (1 − C(oldest_marker_age_days / 365))` | 10 |
| Local SAST | `max(0,100 − 100×(15×high + 5×medium + low)/code_files_analyzed)` | 40 |

Нужно **≥50 известных внутренних весов**. Debt требует полного snapshot и code_files>0.
Возраст учитывается только при age_complete; чистый набор без маркеров даёт 100 этому
компоненту. Local SAST требует полного check и `code_files_analyzed>0`. Счётчик
учитывает каждый поддерживаемый code file один раз; число нейтральных data/docs files
его не увеличивает. `python_files_parsed` и `code_files_lexed` остаются диагностикой
работы отдельных движков. Один SAST без debt
не даёт численного Code Health. Debt без SAST может дать partial score по ≥50 весам.
Репозиторий без поддерживаемых code files не получает фиктивный 100.

## Security boundary

В production остаётся `score=null, availability=no_data,
error=appsec_interface_unconfirmed`. Local SAST никогда не входит в Security.

Зарезервирован **внутренний нормализованный**, а не внешний wire DTO:
source=sourcecraft_appsec, complete=true, open_by_severity с неотрицательными
critical/high/medium/low и официальным evidence. Только такой полный result допускает
`max(0,100 − 40×critical − 20×high − 5×medium − low)`; resolved не включаются.
Synthetic fixture проверяет готовность policy, но не является подключённым AppSec.
Перед подключением нужны подтверждённые mappings и реальная sanitized fixture из
[SOURCECRAFT_SECURITY_DRAFT](SOURCECRAFT_SECURITY_DRAFT.md).

## Рекомендации и replay

Детерминированные правила: отсутствуют README/run/build/test/license; CI не настроен
или success_rate<0.8; stale_open_count>0; TODO/FIXME>0; local SAST findings>0.
Отдельное правило official AppSec работает только с указанным выше подтверждённым
source/input, сейчас в production не срабатывает. Каждая рекомендация содержит
валидные evidence_refs, priority, suggested_action и qualitative High/Medium impact.
Численные обещания «+7 Health» не используются. Сортировка стабильна по priority/id.

Fixtures покрывают healthy/bad/empty/partial/outage, порог coverage, все шесть
категорий, Security unavailable, монотонность ухудшения/исправления при фиксированном
охвате, одинаковую SAST density для small/large, Python AST-only findings и replay
без зависимости от wall clock/popularity. ScoringEngine проверяет
диапазон, finite числа, source Security и references. Новая формула требует новой
policy version/fingerprint; сохранённые reports не переписываются.
