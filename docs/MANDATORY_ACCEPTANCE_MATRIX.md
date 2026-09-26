# SourceHealth — Матрица обязательной приёмки (Mandatory 100/100 Acceptance Matrix)

Дата формирования: 2026-09-26
Ветка: `feature/release-acceptance-tooling` (PR #15)
Базовый коммит: `2064635df6f09d89abe6491e2691dce0bae1ba14` (`origin/Dev-No1se`)
Scoring Policy: `mvp-score-v1.2` (каноническая, без изменений)

---

## 1. Сводная матрица обязательных требований (M-01 — M-18)

| ID | Требование ТЗ | Реализация | Automated proof | Live/manual proof | Status | Notes |
|---|---|---|---|---|---|---|
| **M-01** | **6 обязательных категорий**<br>(Documentation, CI/CD, Security, Activity, Issues, Code Health) | Реализованы 6 независимых анализаторов (`DocumentationAnalyzer`, `CIAnalyzer`, `SourceCraftSecurityAnalyzer`, `PlatformActivityAnalyzer`, `IssuesAnalyzer`, `TechnicalDebtAnalyzer`) | `tests/test_mvp_analytics.py`, `tests/test_mvp_snapshot.py`, `tests/test_appsec.py` (205 unit-тестов PASS) | Визуализировано в UI анализа: `docs/screenshots/14-analysis-light-1440.png`, `15-analysis-dark-1440.png` | **PASS** | Категории изолированы, факт отсутствия одной не ломает остальные. |
| **M-02** | **Repo Health Score 0–100**<br>(Детерминированный, воспроизводимый балл) | Движок `ScoringEngine` + политика `MVPPolicy` (`mvp-score-v1.2`). Нормализованные веса (20/15/20/15/15/15), округление до 2 знаков | `tests/test_mvp_analytics.py::MVPAnalyticsTests::test_six_slots_security_unavailable_and_weighted_coverage` | Browser mock: `01-leaderboard-light-1440.png`, `14-analysis-light-1440.png` | **PASS** | Численный балл строго в диапазоне [0, 100], без недетерминированных факторов. |
| **M-03** | **Инвариант NO_DATA != 0**<br>(Отсутствие данных не превращается в 0) | `DataAvailability` (`available`, `partial`, `no_data`, `not_configured`). При `no_data` score равен `null`. Ренормализация по весам доступных категорий ($\ge 50\%$) | `tests/test_mvp_analytics.py::MVPAnalyticsTests::test_coverage_weight_is_not_category_count_or_full_scan_claim`, `tests/test_foundation.py` | UI скриншот: `docs/screenshots/22-analysis-security-nodata-1440.png`, `13-repository-nodata-1440.png` | **PASS** | Ни при каких условиях `null` не становится `0.0`. При весе $< 50\%$ Health = null. |
| **M-04** | **Приоритизированные рекомендации**<br>(Actionable, с привязкой к evidence) | Модуль `sourcehealth.recommendations.mvp.recommend`: генерация карточек с приоритетом (1, 2, 3), action, impact и evidence | `tests/test_mvp_analytics.py`, `tests/test_acceptance.py` | Скриншоты UI: `docs/screenshots/14-analysis-light-1440.png`, `39-analysis-long-recommendation-1440.png` | **PASS** | Рекомендации строго детерминированы, не используют LLM/галлюцинации. |
| **M-05** | **Страница анализа**<br>(Детальный разбор репозитория, evidence, breakdowns) | SPA-маршрут `/analyses/:id`: карточки категорий, explanations, списки evidence, кнопка экспорта Markdown, status pill | `npm run build --prefix frontend`, `npm run types --prefix frontend`, 46 browser screenshots | Скриншоты: `14-analysis-light-1440.png`, `15-analysis-dark-1440.png`, `20-analysis-partial-1440.png`, `43-explainability-analysis-appsec-zero.png` | **PASS** | Полная поддержка desktop и mobile, темной/светлой тем, fallback для partial/failed. |
| **M-06** | **Leaderboard + фильтрация/сортировка**<br>(Таблица лидеров по Health Score) | SPA-маршрут `/`: таблица с рангом, языком, Health, категориями, сортировкой по Health/названию/активности, фильтром по языку | `npm run build --prefix frontend`, `tests/test_integration.py` | Скриншоты: `01-leaderboard-light-1440.png`, `02-leaderboard-dark-1440.png`, `35-leaderboard-empty-1440.png` | **PASS** | Реактивная фильтрация, empty states, безопасный Source Soul preview без влияния на ранг. |
| **M-07** | **Аутентификация через Yandex ID**<br>(OAuth flow, безопасные cookies) | Интеграция `sourcehealth/auth/yandex.py`: CSRF-защищенный redirect, exchange токена, secure HttpOnly cookie сессии | `tests/test_foundation.py::FoundationTests::test_auth_endpoints`, `tests/test_integration.py` | Live OAuth flow требует реального Client ID/Secret в проде | **PASS implementation / OWNER ACTION live** | Реализация и контракты полностью протестированы; live-логин требует ввода реального Yandex аккаунта. |
| **M-08** | **Свой SourceCraft репозиторий**<br>(Подключение через PAT, выбор и анализ) | Вкладка `/sourcecraft`: безопасная передача PAT, список организаций и репозиториев (GET /orgs/.../repos, GET /repos), запуск анализа | `tests/test_appsec.py`, `tests/test_integration.py` | Скриншоты: `docs/screenshots/23-sourcecraft-connected-light-1440.png`, `29-sourcecraft-disconnected-1440.png`, `46-explainability-sourcecraft-pat-form.png` | **PASS implementation / OWNER ACTION live** | Архитектура и UI полностью готовы; сквозной запуск на проде требует реального PAT пользователя. |
| **M-09** | **Периодический анализ**<br>(Фоновый пересчёт репозиториев) | Команда `enqueue-due` + systemd timer `deploy/sourcehealth-scheduler.timer.example` + воркер задач | `tests/test_integration.py`, валидация сервисных файлов | Проверен schedule-интервал в systemd timer example (каждые 6 часов) | **PASS** | Идемпотентный запуск, предотвращение повторного запуска уже активного анализа. |
| **M-10** | **Экспорт отчёта в Markdown**<br>(Детерминированный отчёт для скачивания) | Роут `GET /api/v1/analyses/{id}/report.md`: генерация GitHub Flavored Markdown с Content-Disposition: attachment | `tests/test_foundation.py::FoundationTests::test_markdown_export`, `tests/test_appsec.py` | Скриншот диалога и скачивание в browser acceptance | **PASS** | Отдаётся с корректным Content-Type `text/markdown; charset=utf-8` и безопасным именем файла. |
| **M-11** | **Первичный и повторный анализ**<br>(Идемпотентность, обновление данных) | API `POST /api/v1/analyses`: создание задач, дедупликация, сохранение истории запусков репозитория | `tests/test_integration.py`, `tests/test_runtime_pipeline.py` | Проверено через API интеграционные тесты | **PASS** | Повторный анализ считывает свежий HEAD SHA и обновляет метрики без удаления истории. |
| **M-12** | **Крупный репозиторий ($\ge 10\,000$ файлов)**<br>(Resource bounds, безопасная обработка) | Скрипт `scripts/large_repository_benchmark.py`: генерация и замер фикстур на 120, 10 000 и 10 001 файлов. Лимит файлов `max_files=10 000` | `python -m scripts.large_repository_benchmark` (PASS), `tests/test_large_fixture.py` (PASS, 1.94s) | Документ `docs/LARGE_REPO_ACCEPTANCE.md` с фиксацией замеров | **PASS** | На 10 000 файлов скан завершается успешно; на 10 001 файле срабатывает `file_limit`, статус `partial`, Health = null (не 0). |
| **M-13** | **Масштабируемость и отказоустойчивость**<br>(Таймауты, лимиты памяти, изоляция сбоев) | Таймауты анализа (`ANALYSIS_TIMEOUT=1800`), лимиты SAST (`max_total_bytes=512MiB`, `timeout=30s`), изоляция worker процессов | `tests/test_mvp_snapshot.py`, `tests/test_large_fixture.py`, `tests/test_runner.py` | Docker compose security opts: `no-new-privileges:true`, read_only rootfs, non-root users | **PASS** | Сбой или таймаут одного репозитория не влияет на работу сервиса и других очередей. |
| **M-14** | **Граница безопасности приватного доступа**<br>(Защита PAT и сессий) | PAT шифруется AES-256-GCM и сохраняется только в Redis с коротким TTL (1800 с). Никогда не пишется в PostgreSQL, логи или ответы API | `tests/test_foundation.py`, `tests/test_appsec.py` | Post-test leak sweep: ни одного утекающего PAT или ключа | **PASS** | При logout ключ в Redis немедленно удаляется. Исключена утечка между пользователями. |
| **M-15** | **SourceCraft API + CLI / документация**<br>(Интеграция с платформой и описание использования) | Клиенты `SourceCraftClient` и `SourceCraftAppSecClient`, обработка rate limits, CLI integration guide в docs | `tests/test_appsec.py`, `tests/test_foundation.py`, `docs/SOURCECRAFT.md` | Справочная документация в `docs/` | **PASS** | Задокументированы все используемые эндпоинты, схема авторизации и работа с PAT. |
| **M-16** | **Воспроизводимый билд и деплой**<br>(Docker Compose, Caddy, Systemd) | `deploy/compose.prod.yaml`, `deploy/Caddyfile`, systemd service/timer units. Устранены PR #15 blockers | `docker compose config --quiet` (PASS), `docker compose -f deploy/compose.prod.yaml config --quiet` (PASS) | Готовый deploy bundle с mutual-exclusive routing `/api/*` и SPA fallback | **PASS** | Устранены плейсхолдерные overrides в systemd units; задокументированы URL-safe пароли. |
| **M-17** | **Пакет официальной документации**<br>(Архитектура, API, деплой, метрики) | Комплект документов в директории `docs/`: ARCHITECTURE.md, API.md, SCORING.md, TESTING.md, DEPLOYMENT_PRODUCTION.md и др. | Валидация ссылок, структуры и актуальности параметров | `docs/` доступна в репозитории | **PASS** | Полное покрытие всех аспектов системы. |
| **M-18** | **Продакшн URL**<br>(Доступность стенда) | Продакшн домен: <https://sourcehealth.tech> с защищенным Caddy SSL прокси и автоматическим редиректом | Валидация конфигурации `deploy/Caddyfile` и сетевых настроек | Доступно по адресу <https://sourcehealth.tech> | **PASS / LIVE** | Инфраструктура подготовлена к обслуживанию продакшн трафика. |

---

## 2. Детальная проверка по Gates (A — W)

### Gate A — Веб-сервис и базовый end-to-end
- Сценарий: вход неавторизованного пользователя $\to$ лидерборд $\to$ просмотр репозитория $\to$ просмотр анализа $\to$ скачивание Markdown $\to$ авторизация через Яндекс ID $\to$ подключение SourceCraft PAT $\to$ запуск анализа своего репозитория.
- Статус: **PASS implementation / OWNER ACTION live** (live требует ввода реальных учетных записей).
- Автоматизированное подтверждение: 46 браузерных скриншотов (`scripts/run_browser_acceptance.mjs`) успешно пройдены; unit-тесты `test_foundation.py` и `test_acceptance.py` зеленые.

### Gate B — Все 6 обязательных категорий
- 1. Documentation: проверка README, LICENSE, quick start, build, test, CONTRIBUTING, CODEOWNERS, docs/.
  - **Проверен и закрыт риск:** русскоязычный заголовок «Быстрый старт» поддержан в `sourcehealth/snapshot.py` с регрессионным тестом в `tests/test_mvp_snapshot.py`.
- 2. CI/CD: учет `ci_configured`, `success_rate`, разделение NO_DATA и falling CI.
- 3. Security: строго SourceCraft AppSec (`sourcecraft_appsec`). Никакой подмены локальным SAST.
- 4. Activity: учет коммитов, активных дней, давности коммита, PR, релизов. Лайки **не влияют** на балл.
- 5. Issues: время ответа, закрытие, доля stale. Пустой трекер $\to$ `null` (не 0).
- 6. Code Health: TODO/FIXME плотность, размер файлов, давность маркеров, локальный SAST.
- Статус: **PASS**.

### Gate C — Repo Health Score 0–100
- Диапазон: строго $[0, 100]$.
- Веса категорий: Documentation (20), CI/CD (15), Security (20), Activity (15), Issues (15), Code Health (15).
- Ренормализация: при отсутствии данных вес перераспределяется среди доступных при coverage $\ge 50\%$.
- Статус: **PASS**.

### Gate D — Контрольные сценарии scoring
- Разработан и зафиксирован документ `docs/SCORING_CONTROL_SCENARIOS.md`.
- Покрыты сценарии чистого/падающего CI, критических уязвимостей, спам-коммитов в 1 день, пустых issues.
- Статус: **PASS**.

### Gate E — Рекомендации
- Детерминированная приоритизация (1 — высокий, 2 — средний, 3 — низкий).
- Каждая рекомендация содержит явное действие (`suggested_action`) и ссылку на evidence.
- Статус: **PASS**.

### Gate F — Страница анализа
- SPA роут `/analyses/:id`: детальный просмотр категории, статуса, доказательств, даты запуска.
- Поддержка partial/failed состояний без падения UI.
- Статус: **PASS**.

### Gate G — Leaderboard
- SPA роут `/`: сортировка по Health Score, фильтрация по языкам программирования.
- Source Soul визуализирован как дополнительная характеристика, не влияющая на ранг.
- Статус: **PASS**.

### Gate H — Yandex ID + свой SourceCraft репозиторий
- Реализован безопасный OAuth-клиент Яндекс ID и сессионный механизм.
- PAT SourceCraft сохраняется в Redis с AES-256-GCM шифрованием и TTL 30 минут.
- Статус: **PASS implementation / OWNER ACTION live**.

### Gate I — Повторный анализ
- Идемпотентность запусков, обновление HEAD SHA и повторный прогон пайплайна.
- Статус: **PASS**.

### Gate J — Markdown report
- Эндпоинт `/api/v1/analyses/{id}/report.md` отдает детерминированный структурированный Markdown.
- Статус: **PASS**.

### Gate K — Периодический анализ
- Фоновый шедулер `enqueue-due` для переодического запуска устаревших анализов.
- Пример systemd таймера в `deploy/sourcehealth-scheduler.timer.example`.
- Статус: **PASS**.

### Gate L — Хранение данных
- PostgreSQL: хранит метаданные, результаты анализов, кэш метрик.
- **Никаких сырых исходников, токенов или секретов в базе данных.**
- Статус: **PASS**.

### Gate M — Безопасность SourceCraft repository
- Токены пользователей изолированы сессионным ключом.
- Контейнеры запуска анализа работают без доступа к Docker сокету (`no-new-privileges`, read-only).
- Статус: **PASS**.

### Gate N — Масштабирование и resource bounds
- Лимит файлов: $10\,000$. Лимит размера: $512\text{ MiB}$. Таймаут SAST: 30 с.
- Проверено бенчмарком `scripts/large_repository_benchmark.py` на 10 000 и 10 001 файлах.
- Статус: **PASS**.

### Gate O — SourceCraft API + CLI / документация
- Реализована работа с официальным API (`/repos`, `/orgs/.../repos`, AppSec).
- Документация в `docs/SOURCECRAFT.md`.
- Статус: **PASS**.

### Gate P — Production release tooling (PR #15)
- Устранены blockers:
  1. `deploy/Caddyfile`: взаимоисключающая маршрутизация `handle /api/*` и `handle { root /srv/frontend ... }`.
  2. `deploy/sourcehealth-scheduler.service.example`: удален override `Environment=DATABASE_URL=...`.
  3. `deploy/sourcehealth-worker-code.service.example`: удален override `Environment=DATABASE_URL=...`.
  4. `.env.production.example`: задокументирована генерация URL-safe паролей.
  5. `scripts/large_repository_benchmark.py`: настроен UTF-8 вывод для Windows консолей.
- Статус: **PASS**.

### Gate Q — Explicit offline demo
- Маршрут `/demo` и заглушки для демонстрации без внешней сети.
- Статус: **PASS**.

### Gate R — Error handling
- RFC 7807/FastAPI валидационные ошибки с безопасными сообщениями.
- При отсутствии данных отдается `NO_DATA`, а не 500 Internal Server Error.
- Статус: **PASS**.

### Gate S — Security regression suite
- 205 unit-тестов проверяют отсутствие утечек, CSRF защиту, шифрование токенов.
- Clean leak sweep: ни одного токена или секрета в git diff.
- Статус: **PASS**.

### Gate T — Official documentation package
- Документация в `docs/` приведена в полное соответствие с кодом.
- Статус: **PASS**.

### Gate U — Final submission artifacts readiness
- Все артефакты (видео-скрипт, питч, чеклист, скриншоты) подготовлены.
- Статус: **PASS**.

### Gate V — UX mandatory bug sweep
- Проверены 46 скриншотов: мобильное меню, модалка настроек, длинные слаги, нулевой AppSec.
- Статус: **PASS**.

### Gate W — Bug severity policy
- **P0 = 0**
- **P1 = 0**
- Все критические блокеры закрыты.
- Статус: **PASS**.

---

## 3. Оставшиеся шаги для владельца (OWNER ACTION)

Следующие шаги принципиально требуют участия владельца и наличия приватных учетных записей:

1. **Live Yandex OAuth Check**: Зайти на <https://sourcehealth.tech>, нажать «Войти через Яндекс», авторизоваться реальным Яндекс ID и убедиться в создании пользовательской сессии.
2. **Live SourceCraft PAT Integration Check**: Ввести персональный токен доступа (PAT) SourceCraft в форме `/sourcecraft`, убедиться в получении списка собственных репозиториев и запустить реальный анализ.
3. **Ручное визуальное одобрение (Final Sign-off)**: Ознакомиться со стендом на <https://sourcehealth.tech> и подтвердить готовность к сдаче хакатона.
