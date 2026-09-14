# 0004 — Redis/RQ и durable lifecycle

## Context
HTTP не должен ждать clone/анализ. Одновременные запросы не должны запускать несколько
тяжёлых jobs. Сбой Redis не должен терять принятую заявку.

## Decision
RQ с UUID job ID, queued rows PG как durable outbox. Row lock + partial UNIQUE
repository/profile; worker session advisory lock против duplicate delivery. Redis
для доставки/cache/session, не source of truth. One-shot enqueue-due по cron.

## Consequences
Нужны dispatcher/recovery и понимание session lock pooling. Queue at-least-once,
application idempotent. PG/Redis transaction атомарности не обещаем: разрыв закрывает
reconciliation. Kafka/Celery не добавляются без иной доказанной задачи.
