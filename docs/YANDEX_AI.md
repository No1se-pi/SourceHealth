# Yandex AI: grounded-отчёты

`POST /api/v1/analyses/{analysis_id}/ai-report` создаёт пользовательский отчёт поверх завершённого
публичного анализа. Нужны авторизованная Яндекс ID session, корректный Origin и настроенные
server-side credentials Yandex AI. AI не участвует в scoring и не изменяет Health.

## Независимый выбор

Request:

```json
{"model":"lite","detail":"detailed"}
```

`detail` по умолчанию равен `brief`. Старый `/ai-summary` остаётся отдельным совместимым endpoint:
request только с `model` возвращает прежний `ai-summary-v1` без новых required-полей.

| Model | Provider model |
|---|---|
| `flash` | Alice AI LLM Flash (`aliceai-llm-flash`) |
| `lite` | YandexGPT 5 Lite (`yandexgpt-5-lite`) |
| `pro` | YandexGPT 5.1 Pro (`yandexgpt-5.1`) |

| Detail | Назначение | Максимальный budget |
|---|---|---:|
| `brief` | основные выводы и действия | ~10 000 знаков |
| `detailed` | разбор рассчитанных категорий и рекомендации | ~20 000 знаков |
| `expert` | полный grounded технический отчёт и roadmap | ~50 000 знаков |

Любая комбинация model × detail допустима; backend не переключает модель автоматически. Это верхние
границы, а не требование заполнять отчёт текстом.

## Контракт и grounding

Prompt version: `sourcehealth-analyst-v2.0`; schema version: `ai-report-v2`. Ключ кеша включает
analysis ID, model, detail и обе версии. Структура содержит резюме, разбор категорий, strengths,
risks, grounded category findings, actions с implementation steps, roadmap и limitations. Подробные правила и budgets:
[AI_SUMMARY_CONTRACT.md](AI_SUMMARY_CONTRACT.md).

`NO_DATA`/`SOURCE_UNAVAILABLE` описываются только как ограничение данных. Numeric score и availability
копируются из анализа и проверяются сервером. Исходники, raw payload, commit messages, PII и секреты
в модель не отправляются.

## Ошибки и retry

Transport errors, timeout, 429 и выбранные 5xx используют bounded exponential backoff; `Retry-After`
ограничен. Общий budget — четыре provider calls, включая максимум один grounding repair. Auth и
invalid request не повторяются. UI различает временную недоступность provider, rate limit и grounding
failure, не показывает raw provider body и всегда предлагает явный повтор.

Depth-aware timeout: 45/75/120 секунд для brief/detailed/expert. Completion ceilings:
3 000/6 000/14 000 tokens. `YANDEX_AI_TIMEOUT` остаётся нижней границей операционного timeout.
