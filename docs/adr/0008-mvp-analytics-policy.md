# ADR 0008: MVP analytics и численный scoring

Статус: принято для analytics batch 19.09.2026 по явному заданию команды.

## Контекст

Foundation и React MVP готовы; nullable baseline не закрывает обязательную аналитику.
При этом официальный AppSec и private permission bridge остаются неподтверждёнными.
Ожидание этих интерфейсов не должно останавливать остальные категории.

## Решение

Добавить `mvp-v1` к существующим профилям, используя ту же очередь analysis-code,
один clone и безопасный runtime. Collectors API и snapshot формируют allowlisted
facts; pure analyzers рассчитывают метрики; `mvp-score-v1` — оценки по опубликованным
формулам. Новая архитектура, таблицы и migrations не требуются: JSONB report уже
поддерживает checks/categories/recommendations.

Веса docs/CI/security/activity/issues/code — 15/15/20/15/15/20. Overall нормализуется
по рассчитанным категориям, при ≥3 категориях и ≥50 номинальных весов. Outage не
является нулевым score. Шесть slots сохраняются всегда. Security получает только
official AppSec; текущий NO_DATA не заменяется local SAST. Старые профили совместимы.

HTTP добавляет только public URL import с существующими session/Origin правилами,
public verification и upsert. OpenAPI/generated TypeScript меняются вместе.
Global/org discovery ограничено batch и не объявляется полным каталогом.

## Последствия и проверка

Policy сравнивается на fixtures при фиксированном coverage; изменённая формула требует
новой версии и fingerprint. Qualitative impact рекомендаций не обещает прибавку баллов.
Подробные метрики/лимиты — [ANALYTICS](../ANALYTICS.md), формулы —
[SCORING](../SCORING.md), evidence приёмки — [MVP_ANALYTICS](../MVP_ANALYTICS.md).
Live API/Я ID/AppSec acceptance указывается отдельно от тестовой инфраструктуры.
