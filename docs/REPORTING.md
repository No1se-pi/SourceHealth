# Экспорт отчётов

SourceHealth экспортирует сохранённый публичный отчёт анализа в Markdown, PDF и
DOCX. Все форматы строятся из единой allowlist-модели `ReportDocument`; renderer’ы
не обращаются к БД, сети или текущим часам, не запускают анализ и не пересчитывают
Health Score.

## Архитектура

```text
AnalysisRun.results (public JSON 3.0)
              ↓
       ReportDocument
       ↙      ↓      ↘
 Markdown    PDF     DOCX
```

`sourcehealth/markdown.py` сохраняет прежний публичный контракт. PDF создаётся
ReportLab в памяти на страницах A4; для воспроизводимой кириллицы пакет содержит
DejaVu Sans 2.37 Regular/Bold и исходную лицензию. DOCX создаётся `python-docx` как
настоящий OOXML-документ с заголовками, таблицами, списками и ссылкой SourceCraft.
Chromium, LibreOffice, временные файлы и внешние конвертеры не используются.

Модель допускает только известные публичные поля. Строки и коллекции ограничены,
нулевые байты удаляются, неизвестные внутренние поля игнорируются. В документы не
добавляются source snippets, PAT/OAuth tokens, environment values, workspace paths
или произвольный exception text.

## Содержание и семантика

Форматы показывают identity и канонический URL репозитория, analysis ID/status при
HTTP-экспорте, время сохранённого анализа, версию scoring policy, сохранённый Health
Score, coverage, шесть категорий с нормативными весами, рекомендации, checks,
evidence и ограничения данных. `NO_DATA` явно означает отсутствие подтверждённых
данных, а не нулевую оценку. Security остаётся основанным только на официальном
SourceCraft AppSec; local SAST относится к Code Health.

Markdown дополнительно сохраняет прежние секции Source Soul, AppSec aggregates и
deep analytics для обратной совместимости.

## HTTP

- `GET /api/v1/analyses/{id}/report.md` — `text/markdown; charset=utf-8`;
- `GET /api/v1/analyses/{id}/report.pdf` — `application/pdf`;
- `GET /api/v1/analyses/{id}/report.docx` —
  `application/vnd.openxmlformats-officedocument.wordprocessingml.document`.

Файлы имеют имена `sourcehealth-{id}.{md|pdf|docx}` и создаются в памяти. Доступ
проверяет существующая граница `public_run`. Экспорт разрешён только для
`completed`/`partial`; остальные состояния возвращают `409 report_not_ready`.

## Проверка

Renderer-тесты проверяют semantic parity трёх форматов, кириллицу, PDF signature и
парсинг страниц, OOXML ZIP и `word/document.xml`, готовность отчёта и исключение
неизвестных secret-полей. OpenAPI описывает PDF/DOCX как binary responses.
