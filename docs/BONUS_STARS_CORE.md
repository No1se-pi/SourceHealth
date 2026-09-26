# Publicity, Compare и Integrity

Batch 2 добавляет три read-only проекции поверх уже сохранённых публичных результатов. Они не запускают анализ, не обращаются к SourceCraft, не меняют Health, категории, рекомендации, tracking или PAT.

## Публичность результата

`GET /api/v1/publicity/repositories/{repository_id}` возвращает канонические ссылки на публичную страницу, последний terminal-анализ, Markdown-отчёт и Health badge. Ссылки строятся только из настроенного `PUBLIC_ORIGIN`; входные `Host` и `X-Forwarded-Host` не используются. Для private/internal/unknown возвращается `404`. При отсутствии Health поле остаётся `null`, Source Soul не подставляется.

## Сравнение

`GET /api/v1/compare?repository_id=<uuid>&repository_id=<uuid>` принимает 2–4 уникальных публичных репозитория и сохраняет порядок выбора. Ответ использует последний `completed`/`partial` run, сохранённые Health, категории и canonical coverage. `NO_DATA` остаётся `score: null`; различие scoring policy отражается через `policy_versions_match=false`. Endpoint не выбирает победителя и ничего не пересчитывает.

## Сигналы устойчивости

`GET /api/v1/repositories/{repository_id}/integrity` анализирует не более двух последних terminal runs и объясняет:

- `commit_burst` — не менее 15 коммитов за не более чем 2 активных дня;
- `low_sample_ci` — CI/CD 100 при не более чем 2 наблюдаемых запусках;
- `score_jump` — изменение Health минимум на 25;
- `coverage_jump` — изменение canonical coverage минимум на 30 процентных пунктов.

Сигналы не доказывают нарушение и не меняют Score. Они отмечают ситуации, где результат следует интерпретировать осторожнее.

Frontend-компоненты созданы изолированно и пока не подключены к navigation. Это будет сделано после интеграции параллельного frontend-polish.
