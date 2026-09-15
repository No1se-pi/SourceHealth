# 0003 — PostgreSQL + versioned JSONB

## Context
Identity/run lifecycle стабильны, analyzer-specific metrics будут часто меняться.
Таблица/column на каждую метрику заставит команду постоянно синхронизировать миграции.

## Decision
Users/repositories/analysis_runs relational, результаты/coverage/recommendations JSONB.
Leaderboard sort/filter fields — индексируемые columns. Alembic с initial migration,
create_all не является deployment mechanism. PostgreSQL — persistent truth.

## Consequences
Новый analyzer обычно не требует migration. Нужно версионировать payload и поддерживать
проекции атомарно. SQLite не проверяет PostgreSQL invariants, integration использует PG.
