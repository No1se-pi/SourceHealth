# Экспорт отчёта

Обязательный baseline ТЗ — Markdown. `sourcehealth/markdown.py` принимает AnalysisReport
либо сохранённый public JSON 3.0 и возвращает строку. Не читает БД/файлы/сеть и не
использует текущие часы. Одинаковый report → одинаковый Markdown.

## Содержание

Repository и время анализа; версия методики; nullable Health Score; шесть категорий
с availability/explanation; сильные стороны; проблемы/ограничения; рекомендации;
evidence. Категории/checks/evidence сортируются, рекомендации — priority/id.
Отсутствующий Score явно NO_DATA. Нет recommendations — «не сформированы», а не
«проблем не обнаружено». Сильные стороны — категории с сохранённым score ≥80;
это характеристика текущей методики, не независимая гарантия качества. Отдельно
показывается число рассчитанных категорий из шести и пояснение NO_DATA.

Raw HTML и Markdown delimiters пользовательского текста экранируются. Не делать
repository descriptions исполняемым HTML. В отчёт не добавлять source snippets,
secret values, абсолютный workspace и произвольные exception text.

## HTTP

`GET /api/v1/analyses/{id}/report.md` загружает уже сохранённый report, не инициирует
новый анализ. Только completed/partial, иначе 409 report_not_ready. Private repo
проверяется перед выдачей файла. Content-Disposition attachment с analysis UUID,
Content-Type text/markdown UTF-8. Новый renderer не изменяет старые JSON 1.0/2.0 и SARIF.

## Расширение

Первые recommendation/strength rules должны ссылаться на общий evidence contract.
PDF позже строится из той же модели/Markdown: добавлять отдельный policy или повторно
считать Score внутри PDF запрещено. PDF engine до конкретной задачи не добавлен.
Renderer unit test проверяет deterministic output, null markers и escaping;
интеграционный тест проверяет HTTP download реального сохранённого AnalysisRun.
## Explainability

Если официальный Health Score ещё не рассчитан, Markdown показывает Source Soul как
предварительный backend-derived preview с охватом и явным предупреждением об отсутствии
в рейтинге. Для доступного official AppSec выводятся только агрегированные severity counts
и формула штрафа; raw findings, snippets и secret values в отчёт не попадают.
