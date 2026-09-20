# SourceHealth

Сервис оценки здоровья репозиториев SourceCraft для ЛЦТ 2026.
Текущий этап — MVP аналитики поверх modular monolith для команды из трёх человек.

**Начать с [документации команды](docs/README.md)**:
[требования](docs/REQUIREMENTS.md), [архитектура](docs/ARCHITECTURE.md),
[совместная работа](docs/DEVELOPMENT.md), [roadmap](docs/ROADMAP.md).

## Что уже работает

- Существующие Git-анализ, local SAST, CLI, SARIF и изолированный Docker workflow.
- API-only AnalysisContext, repository identity, availability и evidence contracts.
- FastAPI, PostgreSQL/Alembic, Redis/RQ, lifecycle и дедупликация запусков.
- Фоновый code-v1: Git + local SAST через один Docker runtime на отдельном trusted worker.
- mvp-v1: Documentation, Issues, CI/CD, Git/platform Activity, Code Health/debt,
  детерминированный Score и рекомендации с evidence.
- Live SourceCraft collectors/discovery, Я ID Authorization Code + PKCE/server sessions и
  сессионное подключение пользовательского PAT для выбора доступного public repository.
- React/TypeScript интерфейс, public URL import, HTTP DTO/OpenAPI и Markdown report.

**Score рассчитывается в mvp-v1** при достаточном coverage; старые профили сохраняют null.
Public SourceCraft pipeline и выбор public repository через пользовательское подключение
подтверждены API/integration/live-приёмкой. Официальный AppSec и delegated private access
не подтверждены; локальный SAST считается Code Health и не подменяет Security. Private
analysis остаётся запрещённым.
Точные проверки и ограничения — [MVP analytics](docs/MVP_ANALYTICS.md),
формулы — [SCORING](docs/SCORING.md), live-процедура — [LIVE_ACCEPTANCE](docs/LIVE_ACCEPTANCE.md).

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
Первоначально список репозиториев пуст. Настройки .env, Я ID, регистрация настоящего
SourceCraft repo и scheduler — [инструкция запуска](docs/DEPLOYMENT.md).

## Сохранённый локальный CLI

```powershell
python -m sourcehealth . --output temp/report.json
python -m sourcehealth . --no-git --output temp/local.json
python -m sourcehealth.sast . --format sarif --output temp/report.sarif
```

CLI-only установка: `python -m pip install -e ".[dev]"`, без server dependencies.
JSON 2.0 для общего CLI, legacy 1.0 для SAST/SARIF; HTTP public report — 3.0.
[Scanner docs](sourcehealth/sast/README.md), [Git-метрики](docs/METRICS.md).

## Проверки

```powershell
python -B -m unittest discover -s tests -v
python -m ruff check .
npm run build --prefix frontend
```

PostgreSQL/Redis integration, live opt-in и границы проверок — [TESTING](docs/TESTING.md).
Не отправлять токены и исходный код в отчёты/логи. Документация и контракты обновляются
в том же PR, что и поведение. Стабильная ветка изменяется через review.
