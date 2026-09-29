# Контракт grounded AI-отчёта

AI-отчёт — отдельный reporting layer над завершённым детерминированным анализом. Он не меняет
`health_score`, оценки категорий, coverage, scoring policy или сохранённые рекомендации.

## Вход

`build_ai_context(report, detail)` формирует `ai-context-v1`. Модель получает только slugs,
официальный Health, coverage, категории, агрегированные безопасные факты и рекомендации.

| Глубина | Facts | Recommendations |
|---|---:|---:|
| `brief` | 50 | 20 |
| `detailed` | 100 | 50 |
| `expert` | 200 | 100 |

Лимиты являются верхней границей: отсутствующие данные не синтезируются. В контекст не попадают
исходники, snippets, raw SAST/AppSec payload, commit messages, имена/email авторов, PAT, cookies,
OAuth данные и другие секреты. Checks с `NO_DATA`/`SOURCE_UNAVAILABLE` не создают assertion evidence.

## Версии HTTP-контракта

`POST /api/v1/analyses/{id}/ai-summary` сохраняет прежний `ai-summary-v1`: request содержит только
`model`, а response — старые поля summary и actions. Новый структурированный контракт доступен через
`POST /api/v1/analyses/{id}/ai-report`; только он принимает `detail`.

## Выход `ai-report-v2`

Структура пригодна для последующего Markdown/PDF/DOCX export без изменения смысла:

- `executive_summary`;
- `category_analysis[]`: категория, точная сохранённая оценка и availability, assessment и IDs findings;
- `category_findings[]`: отдельные positive/problem утверждения с категорией и обязательными evidence refs;
- `strengths[]`, `risks[]`;
- `actions[]`: title, priority, why, action, implementation steps, expected result и grounding IDs;
- `roadmap.immediate/short_term/later`: точные `action-N` IDs существующих actions;
- `limitations[]`.

Каждая strength/risk/category finding обязана ссылаться на известный `evidence_ref`. Каждое действие
содержит известный `recommendation_id` и/или `evidence_ref`. Roadmap ссылается только на grounded actions
по их локальным ID и не создаёт новые действия.
`validate_ai_output()` отклоняет неизвестные IDs, изменение score/availability, утверждения по
недоступной категории, незаземлённые actions и превышение depth budget.

## Бюджеты

| Detail | Target/hard chars | Completion tokens | Timeout | Actions |
|---|---:|---:|---:|---:|
| `brief` | 10 000 | 3 000 | 45 s | 5 |
| `detailed` | 20 000 | 6 000 | 75 s | 12 |
| `expert` | 50 000 | 14 000 | 120 s | 15 |

Размер проверяется до JSON parsing; строковое обрезание ответа запрещено. Локальный live probe
28.09.2026 подтвердил, что `aliceai-llm-flash`, `yandexgpt-5-lite` и `yandexgpt-5.1` принимают
`max_completion_tokens=16_000`; production ceilings намеренно не превышают 14 000.

## Надёжность provider

На одну генерацию разрешено максимум четыре HTTP-вызова, общих для transport retry и единственного
grounding repair. Timeout, transport errors, 429 и 500/502/503/504 повторяются с bounded backoff
0.5/1.5/3 s. Корректный `Retry-After` ограничивается пятью секундами. 400/422, 401/403 и локальная
валидация не повторяются. Логи содержат только mode, detail, attempt и стабильную причину.
