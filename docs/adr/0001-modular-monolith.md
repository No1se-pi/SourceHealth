# 0001 — Модульный монолит

## Context
Команда из трёх человек развивает уже работающие Git/SAST/runner. Нужна независимая
работа без распределённых deployment и противоречащих моделей данных.

## Decision
Один Python package с core/application/integrations/storage/api и отдельным frontend.
API/worker — процессы одного приложения. Использовать обычные Protocol/list registry,
не plugin framework, CQRS, event sourcing или repository per analyzer.

## Consequences
Границы и shared contracts требуют review; масштабировать можно API/worker отдельно.
Микросервисы допускаются после конкретного bottleneck и ADR, не из-за количества папок.
