# Совместная работа команды

## Общая договорённость

Развиваем один модульный монолит. Не создаём три независимых backend/модели отчёта.
Источники истины: core contracts, HTTP OpenAPI, Alembic schema и [ADR](adr/README.md).
Обычная новая метрика не требует изменения этих границ.

## Ownership

| Зона | Основной участник | Что можно делать независимо |
|---|---|---|
| frontend/**, docs/FRONTEND.md | Frontend developer | Layout, routing UI, evidence cards, states, локализация |
| analyzers/**, git/**, sast/** | Analyzer developer | Collect/compute facts, analyzer fixtures, metric docs |
| api/**, application/**, integrations/**, storage/**, scoring/**, ml/**, auth/runtime | Backend / architecture developer | Интеграции, очередь, policy experiments, persistence |
| core/**, API DTO, migrations/**, docs/adr/** | Общая зона | Изменение через согласованный архитектурный PR |

Это роли, а не реальные GitHub handles. Не назначаем выдуманный CODEOWNERS: добавить
его после того, как команда укажет аккаунты и реальные reviewers. Analyzer developer
может реализовать collector в integrations совместным PR, согласовав ключ facts,
без изменения client foundation.

## Рабочий цикл

1. Взять узкую задачу из ROADMAP с ожидаемым результатом и test acceptance.
2. Создать `feature/*` от `Dev-No1se`, нашей integration branch.
3. Перед кодом согласовать только затрагиваемый контракт: inputs, names, nullable
   semantics, version. Если контракт уже подходит, не создавать новый.
4. Реализовать вертикальный сценарий, fixture, meaningful test и документацию.
5. Запустить Ruff/unit; HTTP/DB change — integration; frontend — type/build.
6. Открыть PR: проблема/результат, изменённые контракты, проверки, ограничения.
7. Shared change просматривает архитектурный владелец и потребитель границы.
8. Merge через review. Не push напрямую в стабильную ветку.

### Git workflow

```text
feature/* → small PR + review → Dev-No1se → release PR → main
```

`main` — стабильная/release ветка; `Dev-No1se` — общая integration ветка.
Никаких недельных прямых push в общую ветку: обычная работа идёт короткими feature PR.
Перед release PR пройти весь CI, включая integration, frontend contract и Compose smoke.
`core/**`, API DTO, `migrations/**`, ADR — shared-contract changes: отдельно указать
в PR совместимость и потребителей, которым нужен review. GitHub handles для CODEOWNERS
пока не подтверждены, выдуманный файл не добавляем.

Foundation baseline после closure заморожен: следующая работа — категории аналитики
и методика. Расширяем существующие границы; новый архитектурный слой требует конкретной
необходимости. Команды ручного тега и границы приёмки — [FOUNDATION_CLOSURE](FOUNDATION_CLOSURE.md).

## Правила зависимостей

- Analyzer не знает frontend, не пишет в БД, не запускает очередь.
- API router не считает метрики. Scoring не обращается к SourceCraft.
- ML не запускает Docker. Frontend работает только через HTTP API.
- Новая функция покрывается проверкой поведения; не писать тест, который лишь
  повторяет implementation без обнаружения реальной ошибки.
- Миграции — для domain/storage, metrics — versioned JSONB.
- Комментарии описывают причины/инварианты/границы, не пересказывают очевидный syntax.
- Не удалять meaningful docstrings в Git/scanner/transaction/runtime коде.

## Пример первой задачи анализатора

IssuesCollector + IssuesAnalyzer: в PR описать имена safe facts, source=sourcecraft,
category=issues, окно времени, что означает полный пустой response и partial pagination.
Collector использует SourceCraftClient; analyzer — только context. Fixtures покрывают
пустой repo, timeout после первой страницы, приватный issue и UTC границы. Backend
подключает пару в profile и меняет version профиля. Frontend автоматически видит новый
check и evidence; migration отсутствует. Полная последовательность — [ANALYTICS](ANALYTICS.md).

## Пример первой задачи frontend

Список категорий + evidence: брать AnalysisDetails из generated.ts, отдельно показывать
score=null, availability и explanation, связывать evidence_refs с checks[].evidence.
Визуал можно менять полностью без согласования Python classes. Если не хватает
общего DTO поля — короткое описание use case перед shared PR, а не прямой fetch SourceCraft.

## Пример backend-задачи

Подключить CI collector: проверить официальный endpoint/response schema; ограничить
pages, сохранить timestamp/availability; включить platform cache с отдельным resource
key; подключить analyzer; проверить обновление CI при том же HEAD. Router и DB tables
при этом не меняются. Критерий «не настроен CI» требует доказательства, не одного пустого list.

## Передача между участниками и Codex-сессиями

В задаче указывать: branch, target module, ссылки docs, согласованный контракт, scope,
fixtures, команды acceptance и что не входит. Перед новой сессией читать docs/README,
ARCHITECTURE, соответствующий ADR и git diff/status. Не переписывать чужие незакоммиченные
изменения. Завершать описанием реально выполненных проверок и оставшихся вопросов.
Docs обновлять одновременно с поведением; неизвестное отмечать OPEN INTEGRATION QUESTION.
