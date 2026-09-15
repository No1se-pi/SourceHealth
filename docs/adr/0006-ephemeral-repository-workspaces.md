# 0006 — Одноразовые workspaces

## Context
Чужие репозитории недоверенны, исходный код нельзя сохранять без необходимости.
Clone требует сеть; анализ должен быть изолирован.

## Decision
AnalysisRuntime абстрагирует существующий Docker workflow: сетевой clone, затем
offline/read-only/non-root scan с лимитами; cleanup containers/volume в finally.
Persistent storage получает только безопасные facts/results/references.

## Consequences
Нужны disk quota и уборка после смерти хоста до публичного code worker deployment.
Docker socket привилегирован; API/platform worker его не получает. Executor можно
заменить без переписывания analyzers. Cleanup failure нельзя выдавать за полный успех.
