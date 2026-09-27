# SourceHealth

Сервис оценки здоровья и инженерной зрелости репозиториев SourceCraft для ЛЦТ 2026.
Платформа вычисляет детерминированный **Health Score (0–100)**, предоставляет глубокую аналитику кода и истории Git, формирует прозрачные свидетельства (evidence), детерминированные рекомендации и AI-резюме с защитой от галлюцинаций (grounding).

**Начать с [Руководства по продукту (PRODUCT_GUIDE)](docs/PRODUCT_GUIDE.md)** и **[документации команды](docs/README.md)**:
[требования](docs/REQUIREMENTS.md), [архитектура](docs/ARCHITECTURE.md), [методология скоринга](docs/SCORING.md),
[сценарий демонстрации](docs/DEMO.md), [масштабирование](docs/SCALING.md), [чек-лист сдачи](docs/SUBMISSION_CHECKLIST.md).

## Что уже работает

- **Канонический скоринг `mvp-score-v1.2`:** детерминированный Health Score на базе 6 категорий (Documentation 15, CI/CD 15, Security 20, Activity 15, Issues 15, Code Health 20).
- **Математический инвариант NO_DATA != 0:** отсутствие данных не штрафует проект нулем; при наличии $\ge 3$ категорий и $\ge 50\%$ веса выполняется пропорциональная ренормализация.
- **Официальный SourceCraft AppSec:** прямое взаимодействие с API `https://appsec.sourcecraft.tech` через безопасную сессионную аренду PAT пользователя; категории уязвимостей по критичности.
- **Безопасная изоляция учетных данных:** PAT шифруется AES-256-GCM в Redis с TTL 1800 с, исключена запись в PostgreSQL, логи или ответы API.
- **Интеграция с Yandex AI:** аналитические резюме на базе трех моделей (Alice AI Flash «Мозг», YandexGPT 5 Lite «Крутой мозг», YandexGPT 5.1 Pro «Мегамозг») со строгой валидацией заземления (grounding check) против фактов отчёта.
- **Глубокая Git-аналитика (Deep Analytics):** графики скорости разработки, тепловая карта времени коммитов, прокси Bus-фактора (50% порог) и карта владения с анонимизацией авторов через SHA-256.
- **Защита от накруток (Integrity):** аудит аномальных всплесков коммитов (`commit_burst`), фиктивных прогонов CI (`low_sample_ci`) и неестественных скачков баллов.
- **Сравнение репозиториев (/compare):** сопоставление проектов бок о бок с наложением радарных диаграмм и анализом дельты.
- **Профиль и геймификация:** личный кабинет (/profile), управление проектами, 12 инженерных достижений (achievements).
- **Публичный Developer API и бейджи:** стандартизированный OpenAPI/Swagger интерфейс и динамические векторные SVG-бейджи качества для `README.md`.
- **Масштабируемость и Single-Flight:** разделение очередей (`analysis` и `analysis-code`), блокировки PostgreSQL Advisory Lock, изоляция Docker контейнеров (512MB RAM, 1 CPU, 128 PIDs), поддержка репозиториев до 10 000 файлов.

## Быстрый запуск

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-server.lock
python -m pip install -e ".[dev,server]"
docker compose up -d --build
npm ci --prefix frontend
npm run dev --prefix frontend
```

Frontend: http://127.0.0.1:5173, API docs: http://127.0.0.1:8000/docs.
Настройки `.env`, Яндекс ID, подключение SourceCraft и фоновый планировщик — [инструкция запуска](docs/DEPLOYMENT.md).

## Сохранённый локальный CLI

```powershell
python -m sourcehealth . --output temp/report.json
python -m sourcehealth . --no-git --output temp/local.json
python -m sourcehealth.sast . --format sarif --output temp/report.sarif
```

CLI-only установка: `python -m pip install -e ".[dev]"`, без server dependencies.
JSON 2.0 для общего CLI, legacy 1.0 для SAST/SARIF; HTTP public report — 3.0.
[Scanner docs](sourcehealth/sast/README.md), [Git-метрики](docs/METRICS.md).

## Проверки качества

```powershell
python -B -m unittest discover -s tests -v
python -m ruff check .
npm run build --prefix frontend
npm run types --prefix frontend
```

Текущий статус тестового покрытия: **360 unit/integration tests PASS** (skipped=64).
Детали интеграционных тестов и границы проверок — в [TESTING](docs/TESTING.md).
