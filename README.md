# SourceHealth

Анализ репозиториев для хакатона ЛЦТ / SourceCraft: временные метрики Git и лёгкий
SAST с 70 редактируемыми JSON-правилами. Python 3.11+, Git для сбора истории;
runtime-зависимостей Python нет.

## Установка и запуск

```powershell
python -m venv .venv
.venv/Scripts/Activate.ps1
python -m pip install -e ".[dev]"
python -m sourcehealth . --exclude "temp/*" --output temp/health-report.json
```

На Linux/macOS: `source .venv/bin/activate`. После установки также доступна
команда `sourcehealth PATH --output report.json`. Общий CLI запускает Git и SAST,
возвращает **AnalysisReport 2.0**. Для папки без Git добавьте `--no-git`.
Собственный выходной файл исключается автоматически; другие отчёты исключайте
через `--exclude` или сохраняйте вне проверяемой папки.

Специализированный CLI сохраняет JSON **1.0**:

```powershell
python -m sourcehealth.sast . --output temp/sast.json
python -m sourcehealth.sast . --with-git --output temp/legacy-health.json
python -m sourcehealth.sast . --format sarif --output temp/sast.sarif
```

Коды выхода: `0` — проверка завершена, `1` — превышен `--fail-on high|medium|low`,
`2` — ошибка или неполная проверка. Код `2` приоритетнее находок.
Все параметры: `python -m sourcehealth --help`.

## Архитектура

```text
Repository → Collectors → AnalysisContext → независимые Analyzers
                                              ↓
                                       AnalyzerResult
                                              ↓
                         AnalysisRunner → AnalysisReport → будущие Scoring / API / UI
```

Модульный монолит: runner последовательно вызывает переданный список анализаторов,
собирает историю один раз и изолирует ошибки отдельных проверок. Git и SAST
остаются самостоятельными библиотеками с небольшими адаптерами общего контракта.
Итоговый рейтинг внутри анализаторов не вычисляется.

```python
import json

from sourcehealth.analyzers import GitActivityAnalyzerAdapter, SASTAnalyzerAdapter
from sourcehealth.runner import AnalysisRunner

runner = AnalysisRunner([GitActivityAnalyzerAdapter(), SASTAnalyzerAdapter()])
report = runner.analyze(".")
print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
```

## Как добавить новый анализатор

Создайте, например, `sourcehealth/analyzers/documentation.py`:

```python
from sourcehealth.core import AnalysisContext, AnalyzerResult


class DocumentationAnalyzer:
    name = "documentation"

    def analyze(self, context: AnalysisContext) -> AnalyzerResult:
        return AnalyzerResult(
            analyzer=self.name,
            metrics={"has_readme": (context.repo_path / "README.md").is_file()},
        )
```

Добавьте `DocumentationAnalyzer()` в список своего `AnalysisRunner` и тест в
`tests/`. Для стандартного CLI регистрация находится в
`sourcehealth/reporting.py:analyze_repository`. Git, SAST и runner менять не нужно.
Общие внешние данные готовьте через `context_factory`. Подробности и пример JSON —
в [ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Структура и работа втроём

```text
sourcehealth/
├── core/                # контекст, Protocol, модели результатов
├── analyzers/           # адаптеры Git/SAST и будущие проверки
├── git/                 # прежние collector.py, activity.py, models.py
├── sast/                # сканер, движки, rules/*.json, SARIF, Docker
├── runner.py            # контекст и последовательная orchestration
├── reporting.py         # стандартный набор проверок и совместимость JSON 1.0
├── cli.py               # аргументы, вывод, exit code
├── __main__.py          # python -m sourcehealth
├── scoring/             # документированная граница будущего Health Score
└── ml/                  # документированная граница будущих features/моделей
tests/                   # все автоматические тесты
examples/legacy/          # обёртки раннего прототипа GitActivity
docs/                    # архитектура и описание Git-метрик
pyproject.toml           # установка, dev-зависимости и Ruff
.github/workflows/tests.yml
```

| Участник | Область | Контракт |
|---|---|---|
| Frontend / UI | Будущий интерфейс | JSON AnalysisReport 2.0 |
| Анализаторы | analyzers, git, sast | `analyze(context) → AnalyzerResult` |
| Integration / Backend / Scoring / ML | runner, reporting, будущие интеграции | AnalysisContext и AnalysisReport |

## Проверки

```powershell
python -B -m unittest discover -s tests -v
python -m ruff check .
```

Тесты используют локальные временные репозитории и не требуют интернета.
CI выполняет эти команды на Windows и Ubuntu, Python 3.11 и 3.13.
Форматирование всего проекта не навязывается.

## Совместимость и ограничения

- Пакет `sourcehealth.SAST` переименован в `sourcehealth.sast`: обновите импорты,
  команды `python -m` и путь Dockerfile. Старое имя больше не поддерживается;
  на Linux регистр важен. Методы сканера, модели и Git API сохранены.
- `test/GitActivity` перенесён в `examples/legacy/GitActivity`; это прототипы,
  не автоматические тесты. Новый код использует `sourcehealth.git`.
- JSON 2.0 унифицирует результаты: прежнее `checks.sast.files_scanned` теперь
  `checks.sast.metrics.files_scanned`. Старый формат доступен через SAST CLI
  и `build_report`.
- `complete=false` означает неполное покрытие. GitCollector по-прежнему
  загружает всю историю HEAD в память.
- SAST анализирует текст без запуска проекта; находки эвристические.
  Правила из проверяемого репозитория автоматически не загружаются.
- Пока нет frontend, API-сервера, формулы scoring, ML-моделей и SourceCraft API
  client. Следующие шаги: новые анализаторы, scoring/features, внешний коллектор
  SourceCraft и тонкий API поверх runner.

Подробнее: [Git-метрики](docs/METRICS.md),
[SAST, лимиты, правила и контейнерный запуск](sourcehealth/sast/README.md).
