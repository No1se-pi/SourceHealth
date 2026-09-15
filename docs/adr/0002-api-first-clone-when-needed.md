# 0002 — API-first, clone по необходимости

## Context
Issues/CI/AppSec/metadata меняются независимо от HEAD. Clone большого repo ради API
данных дорог и не создаёт недостающие платформенные факты.

## Decision
RepositoryRef не зависит от workspace. Context допускает отсутствие workspace/commits.
API collectors получают platform facts. Clone создаётся лишь для явно выбранного
code/history profile. Shallow history не подменяет полную историю метрик.

## Consequences
Нужны независимые freshness policies и фактический SHA code анализа. Current platform
profile не клонирует repo; подключение code runtime — отдельная следующая задача.
