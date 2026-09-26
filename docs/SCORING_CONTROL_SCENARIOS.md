# SourceHealth — Контрольные сценарии scoring (mvp-score-v1.2)

Документ фиксирует детерминированное поведение канонической scoring policy `mvp-score-v1.2`
на контрольных сценариях в соответствии с Gate D.

---

## 1. Security (SourceCraft AppSec)

Security рассчитывается **исключительно** на основе данных официального SourceCraft AppSec.
Локальный SAST SourceHealth никогда не подменяет AppSec.

| Сценарий | Входные данные | Ожидаемый результат | Автоматизированный тест |
|---|---|---|---|
| **S-1: Чистый скан** | `open_by_severity: {critical: 0, high: 0, medium: 0, low: 0}`, status FINISHED | `score = 100.0`, `availability = available` | `tests/test_appsec.py::AppSecTests::test_finished_scan_is_normalized_without_raw_fields` |
| **S-2: Критические уязвимости** | `critical: 1, high: 0, medium: 0, low: 0` | `score = 60.0` (штраф 40 за critical), заметное снижение Health | `tests/test_appsec.py` |
| **S-3: Множественные дефекты** | `critical: 2, high: 2` | `score = 0.0` (80 + 40 > 100, bounded [0, 100]) | `tests/test_appsec.py` |
| **S-4: AppSec недоступен (NO_DATA)** | Отсутствует SourceCraft PAT / нет прав AppSec / интерфейс не подтверждён | `score = null`, `availability = no_data` (**НЕ превращается в 0**) | `tests/test_mvp_analytics.py::MVPAnalyticsTests::test_six_slots_security_unavailable_and_weighted_coverage` |
| **S-5: Незавершённый скан** | status IN_PROGRESS / PARTIAL | `score = null`, `availability = partial` | `tests/test_appsec.py` |

---

## 2. CI/CD

Оценка работы пайплайнов непрерывной интеграции SourceCraft CI.

| Сценарий | Входные данные | Ожидаемый результат | Автоматизированный тест |
|---|---|---|---|
| **CI-1: Зелёный пайплайн** | `ci_configured = true`, `success_rate = 1.0` (все недавние запуски успешны) | `score = 100.0`, `availability = available` | `tests/test_mvp_analytics.py::MVPAnalyticsTests::test_ci_stable_failing_absent_unknown_and_partial` |
| **CI-2: Падающий пайплайн** | `ci_configured = true`, `success_rate = 0.0` (все недавние запуски упали) | `score = 0.0`, `availability = available` | `tests/test_mvp_analytics.py::MVPAnalyticsTests::test_ci_stable_failing_absent_unknown_and_partial` |
| **CI-3: Сконфигурирован без запусков** | `ci_configured = true`, запусков нет (`items = []`) | `score = 50.0`, `availability = available` (отличается от NO_DATA и сбоев) | `tests/test_mvp_analytics.py::MVPAnalyticsTests::test_ci_stable_failing_absent_unknown_and_partial` |
| **CI-4: Не настроен** | `.sourcecraft/ci.yaml` отсутствует, `ci_configured = false` | `score = 0.0`, `availability = not_configured` | `tests/test_mvp_analytics.py::MVPAnalyticsTests::test_ci_stable_failing_absent_unknown_and_partial` |
| **CI-5: Сбой API / таймаут** | Ошибка сбора данных SourceCraft API | `score = null`, `availability = no_data` (**НЕ превращается в 0**) | `tests/test_mvp_analytics.py::MVPAnalyticsTests::test_ci_stable_failing_absent_unknown_and_partial` |

---

## 3. Documentation

Оценка полноты документации и инструкций для разработчиков.

| Сценарий | Входные данные | Ожидаемый результат | Автоматизированный тест |
|---|---|---|---|
| **DOC-1: Полный комплект** | README (20), LICENSE (15), Quick Start / запуск (20), Build (10), Tests (15), CONTRIBUTING (5), CODEOWNERS (5), docs/ (10) | `score = 100.0`, `availability = available` | `tests/test_mvp_snapshot.py::SnapshotTests::test_healthy_docs_clean_debt_and_exact_snapshot` |
| **DOC-2: Только README без инструкций** | README с общим описанием проекта, без команд сборки/запуска/тестов | `score = 20.0`, `availability = available` | `tests/test_mvp_snapshot.py::SnapshotTests::test_minimal_and_missing_documentation` |
| **DOC-3: Русский заголовок «Быстрый старт»** | README.md с разделом `## Быстрый старт` | Признак `run_instructions = true` (+20 баллов) | `tests/test_mvp_snapshot.py::SnapshotTests::test_russian_quickstart_heading_detected` |
| **DOC-4: Полное отсутствие документации** | Пустой репозиторий без README и лицензии | `score = 0.0`, `availability = available` | `tests/test_mvp_snapshot.py` |

---

## 4. Activity

Оценка регулярной активности разработки без учёта накруток.

| Сценарий | Входные данные | Ожидаемый результат | Автоматизированный тест |
|---|---|---|---|
| **ACT-1: Регулярная здоровая разработка** | $\ge 20$ коммитов за 30 дней, $\ge 5$ активных дней, давность последнего коммита $\le 7$ дней, PR, релизы | `score = 100.0`, `availability = available` | `tests/test_mvp_analytics.py` |
| **ACT-2: Заброшенный репозиторий** | Последний коммит более 90 дней назад, 0 коммитов за 30 дней | `score = 0.0`, `availability = available` | `tests/test_mvp_analytics.py` |
| **ACT-3: Spam burst (накрутка в 1 день)** | 20 коммитов в один день (`active_days = 1`) | `score \le 80.0`, однодневный спам не даёт максимум активности | `tests/test_mvp_analytics.py::MVPAnalyticsTests::test_same_day_commit_burst_cannot_max_recent_activity` |
| **ACT-4: Лайки (stars/reactions)** | Любое количество лайков/реакций | Не влияют на оценку Activity и Health (не входят в формулу) | `tests/test_repository_rating.py` |

---

## 5. Issues

Оценка работы с обращениями и багами.

| Сценарий | Входные данные | Ожидаемый результат | Автоматизированный тест |
|---|---|---|---|
| **ISS-1: Здоровый трекер** | Время ответа $< 24$ ч, медиана закрытия $< 72$ ч, доля устаревших $\le 20\%$ | `score = 100.0`, `availability = available` | `tests/test_mvp_analytics.py::MVPAnalyticsTests::test_issues_healthy_empty_stale_and_partial` |
| **ISS-2: Без ответов / брошенные** | Обращения без первого ответа разработчика (`unanswered_count > 0`) | Штраф пропорционально доле неотвеченных | `tests/test_mvp_analytics.py::MVPAnalyticsTests::test_unanswered_issues_lower_response_component_and_partial_is_unknown` |
| **ISS-3: Зависшие задачи (stale)** | `stale_ratio = 1.0` (все обращения открыты $> 30$ дней без обновлений) | Значительное падение score категории | `tests/test_mvp_analytics.py::MVPAnalyticsTests::test_issues_healthy_empty_stale_and_partial` |
| **ISS-4: Пустой трекер (0 issues)** | Репозиторий без обращений (`observed_count = 0`) | `score = null`, `availability = available` (**НЕ превращается в 0**, не искажает рейтинг) | `tests/test_mvp_analytics.py::MVPAnalyticsTests::test_empty_issues_are_observed_but_not_scored` |

---

## 6. Code Health & Technical Debt

Оценка качества кодовой базы и технического долга.

| Сценарий | Входные данные | Ожидаемый результат | Автоматизированный тест |
|---|---|---|---|
| **CH-1: Чистый код** | 0 маркеров TODO/FIXME, файлы $\le 1000$ строк, 0 findings локального SAST | `score = 100.0`, `availability = available` | `tests/test_mvp_snapshot.py::SnapshotTests::test_healthy_docs_clean_debt_and_exact_snapshot` |
| **CH-2: Плотность маркеров долга** | Наличие TODO/FIXME маркеров, файлы $> 1000$ строк, давность маркеров | Score снижается пропорционально плотности долга | `tests/test_mvp_snapshot.py::SnapshotTests::test_debt_counts_age_and_size_without_executing_repository` |
| **CH-3: Уязвимости локального SAST** | Срабатывание правил локального SAST | Штраф пропорционально серьёзности findings | `tests/test_sast.py` |
| **CH-4: Неполный скан / таймаут** | Превышен лимит файлов / таймаут парсинга | `availability = partial`, незавершённый скан не объявляется чистым | `tests/test_large_fixture.py`, `scripts/large_repository_benchmark.py` |

---

## 7. Missing Data & Coverage Renormalization

Поведение агрегирующего движка `ScoringEngine` при отсутствии части данных.

| Сценарий | Входные данные | Ожидаемый результат | Автоматизированный тест |
|---|---|---|---|
| **COV-1: Доступны все 6 категорий** | Номинальный вес = $100\%$ | $\text{Health} = \sum w_i \cdot s_i$ | `tests/test_mvp_analytics.py` |
| **COV-2: Security отсутствует (NO_DATA)** | Доступны 5 категорий из 6 (вес $80\% \ge 50\%$) | Оставшиеся категории ренормализуются: $\text{Health} = \frac{\sum w_i \cdot s_i}{80}$ | `tests/test_mvp_analytics.py::MVPAnalyticsTests::test_six_slots_security_unavailable_and_weighted_coverage` |
| **COV-3: Менее $50\%$ веса категорий** | Доступна только 1 категория (например, только Activity с весом $15\%$) | $\text{Health} = \text{null}$ (недостаточно данных для объективного общего балла) | `tests/test_mvp_analytics.py::MVPAnalyticsTests::test_coverage_weight_is_not_category_count_or_full_scan_claim` |
| **COV-4: Инвариант NO_DATA != 0** | Любая категория со статусом `no_data` | Ни при каких обстоятельствах не подставляет $0.0$ в числитель или отображение | `tests/test_mvp_analytics.py`, `tests/test_foundation.py` |
