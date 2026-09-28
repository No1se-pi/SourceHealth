# Yandex AI: grounded-отчёты

AI-разбор — отдельный пользовательский отчёт поверх уже завершённого анализа. Он не запускается автоматически,
не меняет `health_score`, категории, рекомендации или сохранённые факты и не используется в scoring.

## Контракт

- Endpoint: `POST /api/v1/analyses/{analysis_id}/ai-summary`.
- Доступ: только авторизованная сессия Яндекс ID, корректный `Origin` и публично доступный анализ со статусом
  `completed` или `partial`.
- Provider: Yandex AI Studio, OpenAI-совместимый синхронный REST endpoint
  `https://ai.api.cloud.yandex.net/v1/chat/completions`.
- Авторизация provider: `Authorization: Api-Key ...`; ключ остаётся только на backend.
- Формат модели: `gpt://<folder-id>/<model-id>/latest`.
- Точные ID: `aliceai-llm-flash`, `yandexgpt-5-lite`, `yandexgpt-5.1` для режимов `flash`, `lite`, `pro`.
- Структурированный ответ задаётся `response_format.type=json_schema`; результат дополнительно валидируется Pydantic и
  `validate_ai_output()`.
- Prompt version: `sourcehealth-analyst-v1.2`; schema version: `ai-summary-v1`.

Контекст формирует только `build_ai_context()`: агрегированные оценки, availability, безопасные evidence и
рекомендации. Исходники, snippets, raw payload, commit messages, имена/email, PAT, OAuth cookies и секреты в
provider не отправляются. `NO_DATA` остаётся неизвестным значением.

## Режимы

| Режим | UI | Модель |
|---|---|---|
| `flash` | Мозг / быстрый разбор | Alice AI LLM Flash |
| `lite` | Крутой мозг / сбалансированный разбор | YandexGPT 5 Lite |
| `pro` | Мегамозг / глубокий разбор | YandexGPT 5.1 Pro |

Все режимы используют один prompt и один schema contract. Они различаются только моделью.

## Конфигурация и эксплуатация

Нужны `YANDEX_AI_API_KEY` и `YANDEX_AI_FOLDER_ID`. Если хотя бы одна переменная отсутствует, endpoint отвечает
`ai_provider_disabled`; автоматического fallback нет. Дополнительно доступны `YANDEX_AI_TIMEOUT` (45 секунд),
`YANDEX_AI_CACHE_TTL` (24 часа) и `YANDEX_AI_RATE_LIMIT` (10 оплачиваемых генераций на пользователя в час).

Кеш Redis учитывает analysis ID, режим, версии prompt и schema. Ошибка кеша не отменяет генерацию. Общий предел —
два provider requests на нажатие: повтор разрешён для transport error, HTTP 429, выбранных 5xx либо единственного
grounding repair той же моделью. Ошибки авторизации и плохой JSON не повторяются. Предыдущий ответ при repair не
передаётся. JSON Schema ограничивает ссылки точными ID из контекста. Логи содержат только стабильный код события,
режим и безопасную категорию причины, без prompt, ответа и ключа.

Живой вызов Yandex AI не входит в CI: unit/API тесты используют transport/provider doubles. Для ручной проверки
используют завершённый публичный анализ и явное нажатие кнопки в браузере.
