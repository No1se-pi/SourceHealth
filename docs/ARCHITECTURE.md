# Архитектура SourceHealth

## Границы компонентов

SourceHealth — модульный монолит для трёх разработчиков:

```text
Repository → Collectors → AnalysisContext → Analyzer.analyze(context)
                                                 ↓
                                           AnalyzerResult
                                                 ↓
                         AnalysisRunner → AnalysisReport → Scoring / API / UI
```

Collectors собирают факты, analyzers рассчитывают метрики и находки, scoring
позже интерпретирует результаты, ML получает подготовленные признаки. CLI
разбирает параметры, вызывает application layer и сериализует результат.

| Компонент | Ответственность | Чего здесь нет |
|---|---|---|
| git/collector.py | Git subprocess → список Commit | Метрики, API, scoring |
| git/activity.py | Commit → GitActivityMetrics | Git subprocess, чтение файлов |
| sast/scanner.py | Обход исходников, правила → ScanResult | Запуск Git, общая orchestration |
| core/ | Контекст, Protocol, модели результатов | Вызовы анализаторов и сервисов |
| analyzers/ | Адаптация предметных результатов | API, итоговый балл |
| runner.py | Контекст, порядок запуска, изоляция ошибок | Логика конкретных проверок |
| reporting.py | Стандартный набор анализаторов, JSON 2.0 → 1.0 | Расчёт метрик |
| cli.py | Аргументы, атомарная запись UTF-8, exit code | Сбор Git, логика сканера |
| scoring/, ml/ | Документированные точки расширения | Фиктивные формулы и модели |

## AnalysisContext

`core/context.py` содержит небольшой frozen dataclass:

- `repo_path: Path` — абсолютный путь в запусках runner;
- `commits: tuple[Commit, ...] | None` — собранная история;
- `started_at` — общий UTC-момент начала, также база временных Git-метрик;
- `metadata` — подготовленные внешние данные, например SourceCraft;
- `collection_errors` — безопасные коды ошибок сборщиков.

`commits=()` означает успешно собранную пустую историю, `None` — история
недоступна или не запрашивалась. Ошибка Git не должна превращаться в успешный
результат с нулём коммитов.

Всем анализаторам передаётся один контекст. Поля frozen, вложенные словари и
Commit считаются read-only по контракту; это не sandbox от намеренной мутации.
Анализаторы — доверенный код приложения. Код проверяемого репозитория не импортируется.

`prepare_context` собирает Git один раз. Ошибка GitCollectionError/ValueError
сохраняется как `git_collection_failed`; SAST продолжает работать. История HEAD
по-прежнему целиком помещается в память — сборщик не переписан.

Сбор фактов можно заменить обычной функцией. Для SAST-only без запуска Git:

```python
from sourcehealth.analyzers import SASTAnalyzerAdapter
from sourcehealth.core import AnalysisContext
from sourcehealth.runner import AnalysisRunner

runner = AnalysisRunner([SASTAnalyzerAdapter()], context_factory=AnalysisContext)
```

Будущий `integrations/sourcecraft.py` будет собирать metadata в собственной
`context_factory`, сохраняя GitCollector независимым от API. Неожиданная ошибка
пользовательской factory прерывает подготовку запуска; factory сама представляет
ожидаемые частичные сбои в collection_errors. Runner явно отклоняет несуществующий
путь и путь к файлу.

## Analyzer и AnalyzerResult

`Analyzer` — Protocol с `name: str` и методом
`analyze(context: AnalysisContext) -> AnalyzerResult`. Наследование необязательно.
Регистрация — явный список экземпляров; discovery, plugin framework и динамический
импорт проверяемого кода отсутствуют.

| Поле результата | Тип | Значение |
|---|---|---|
| analyzer | string | Уникальный идентификатор, совпадает с ключом checks |
| status | ok / partial / error | Статус выполнения, не оценка безопасности |
| metrics | object | Счётчики, измерения, признаки |
| findings | array of objects | Находки, может быть пустым |
| metadata | object | Версия, конфигурация, покрытие, диагностика |
| error | string или null | Безопасный машинный код ошибки |

Метрики без находок и находки без метрик допустимы. Внутренняя структура метрик
и находок принадлежит конкретному анализатору; общий контейнер стабилен для UI.
Поля SAST описаны в его README.

Вложенные значения должны быть JSON-совместимыми. `to_dict()` проверяет контейнеры,
статус и сериализацию с запретом NaN/Infinity. Не передавайте Path, datetime,
произвольные классы или сырые секреты. Даты в метриках заранее превращаются в
ISO 8601 строки, как в GitActivityMetrics.

GitActivityAnalyzerAdapter передаёт готовые commits прежнему GitActivityAnalyzer,
сохраняя его чистый API. SASTAnalyzerAdapter вызывает прежний scanner, переносит
счётчики и summary в metrics, находки в findings, конфигурацию, пропуски, версии
и digest в metadata. ScanResult.complete=false превращается в status=partial
с сохранением уже найденных проблем.

## AnalysisRunner

Runner принимает анализаторы и необязательную context_factory. Проверяет уникальность
имён до запуска, готовит контекст, последовательно вызывает каждый analyze,
проверяет результат и сохраняет его копию в checks.

Исключение анализатора, неверный тип результата, несовпавшее имя или ошибка
JSON-сериализации дают `status=error, error=analyzer_failed`. Следующий анализатор
всё равно запускается. Текст исключений не попадает в публичный JSON, поскольку
может содержать данные репозитория. KeyboardInterrupt/SystemExit не поглощаются.

Параллельное выполнение и очереди пока не нужны. Позднее внешний worker сможет
вызывать этот же pipeline; предметные анализаторы не зависят от CLI.

## AnalysisReport и контракт UI

`AnalysisReport.to_dict()` возвращает JSON версии **2.0**. Пример отчёта с ошибкой
Git и успешной независимой проверкой:

```json
{
  "schema_version": "2.0",
  "repository": {"path": "/workspace/repo"},
  "started_at": "2026-09-12T10:00:00+00:00",
  "completed_at": "2026-09-12T10:00:01+00:00",
  "status": "partial",
  "complete": false,
  "checks": {
    "git_activity": {
      "analyzer": "git_activity", "status": "error",
      "metrics": {}, "findings": [], "metadata": {},
      "error": "git_collection_failed"
    },
    "documentation": {
      "analyzer": "documentation", "status": "ok",
      "metrics": {"has_readme": true}, "findings": [], "metadata": {}, "error": null
    }
  }
}
```

UI может перечислять checks, показывать метрики, находки и ошибки без знания Python.
`complete=true` только когда все запрошенные проверки имеют status=ok.
Общий status=error, если все проверки завершились ошибкой; partial, если есть
неполнота вместе с другими результатами; иначе ok. Единственная partial-проверка
также даёт общий partial. Пустой список даёт checks={}, complete=true, status=ok:
это отсутствие запрошенных проверок, не доказательство здоровья репозитория.
Число находок не влияет на complete/status.

В отчёт не копируются commit messages и email авторов. Repository содержит
локальный абсолютный путь; внешний API позднее может заменить его своим ID.
Scoring учитывает partial/error как недостаток данных, не как нулевые находки.
ML строится поверх подготовленных features. API/frontend пока не реализованы.

## CLI, JSON 1.0 и миграция

```powershell
# Общий отчёт 2.0, Git + SAST по умолчанию
python -m sourcehealth . --exclude "temp/*" --output temp/report.json
# Только SAST, контракт 2.0
python -m sourcehealth . --no-git --output temp/report.json
# Прежний JSON 1.0
python -m sourcehealth.sast . --with-git --output temp/legacy.json
# SARIF
python -m sourcehealth.sast . --format sarif --output temp/report.sarif
```

`sast.__main__` — тонкая обёртка над общим CLI. Публичный
`build_report(path, scanner, with_git=False)` доступен оттуда, но реализован в
reporting и делегирует runner. `to_legacy_report` сохраняет старые плоские поля
SAST и Git-метрики. Container runner и SARIF сохраняют JSON 1.0 и коды выхода.
Общий CLI для SARIF требует `--no-git`, поскольку SARIF содержит только SAST.

| JSON 1.0 | JSON 2.0 |
|---|---|
| checks.sast.files_scanned | checks.sast.metrics.files_scanned |
| checks.sast.summary | checks.sast.metrics.summary |
| checks.sast.findings | Тот же путь |
| checks.sast.ruleset_digest | checks.sast.metadata.ruleset_digest |
| checks.sast.complete | checks.sast.status == "ok" |
| checks.git_activity.metrics | Тот же путь |
| Верхний complete | Тот же смысл; добавлены status, repository, времена |

Пакет переименован с `sourcehealth.SAST` в `sourcehealth.sast`. Обновлены импорты,
тесты, Dockerfile и документация. Alias старого регистра не добавлен: два каталога,
различающихся только регистром, конфликтуют на Windows. На Linux старые импорты
нужно заменить явно; предметные методы и модели сохранены. JSON-правила теперь
в `sourcehealth/sast/rules/*.json`, включены в wheel и по-прежнему не загружаются
из анализируемого репозитория автоматически.

`test/GitActivity` перемещён в `examples/legacy/GitActivity`: обёртки раннего
прототипа сохранены, автоматические тесты их не используют. Новый код импортирует
sourcehealth.git; все автоматические тесты находятся в tests/.

## Как добавить новый анализатор

1. Создайте модуль, например `sourcehealth/analyzers/documentation.py`.
2. Реализуйте name и analyze по Protocol.
3. Верните AnalyzerResult без итогового Health Score.
4. Передайте экземпляр в AnalysisRunner. Для стандартного CLI дополните список
   в reporting.analyze_repository; общие данные добавляйте через context_factory.
5. Добавьте локальный тест, включая partial/error, если применимо.

```python
from sourcehealth.core import AnalysisContext, AnalyzerResult
from sourcehealth.analyzers import GitActivityAnalyzerAdapter, SASTAnalyzerAdapter
from sourcehealth.runner import AnalysisRunner


class DocumentationAnalyzer:
    name = "documentation"

    def analyze(self, context: AnalysisContext) -> AnalyzerResult:
        return AnalyzerResult(
            analyzer=self.name,
            metrics={"has_readme": (context.repo_path / "README.md").is_file()},
        )


runner = AnalysisRunner([
    GitActivityAnalyzerAdapter(), SASTAnalyzerAdapter(), DocumentationAnalyzer(),
])
report = runner.analyze(".")
```

## Работа команды и следующие шаги

Frontend использует JSON 2.0. Разработчик анализаторов работает в собственных
модулях через Protocol. Разработчик integration/backend/scoring/ML отвечает за
контекст, стандартный состав запуска и потребителей отчёта. Изменения core/JSON
согласуются командой; обычная новая проверка их не требует.

Ближайшие расширения: hygiene, contributors, dependencies, documentation,
complexity, duplication; secret scanning уже входит в SAST. Далее — SourceCraft
metadata, политика scoring, ML-признаки и тонкий API вокруг runner.

Сознательно отсутствуют микросервисы, очереди, БД/ORM, Redis, Celery, Kubernetes,
async, plugin framework, ML-библиотеки и фиктивный рейтинг: сейчас они не решают
задачу независимой разработки. Неиспользуемые api/integrations каталоги не созданы;
scoring/ml содержат только запрошенные документированные границы.

Проверки: `python -B -m unittest discover -s tests -v` и `python -m ruff check .`.
CI повторяет их на Ubuntu/Windows с Python 3.11/3.13 после `pip install -e ".[dev]`.
