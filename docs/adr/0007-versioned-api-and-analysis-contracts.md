# 0007 — Версионированные контракты

## Context
Frontend, analyzers и backend развиваются независимо. Существуют CLI JSON 2.0 и
SAST/SARIF JSON 1.0 consumers; путь workspace нельзя публиковать в web API.

## Decision
REST /api/v1, публичный report 3.0 с RepositoryRef, независимые analyzer/policy versions.
CLI 2.0 и SAST legacy 1.0 сохраняются для действующих consumers. HTTP DTO/OpenAPI
порождают frontend types. Availability отделена от score; null не равен нулю.

## Consequences
Shared breaking changes требуют согласования/миграции. Новая метрика внутри metrics
не требует нового endpoint/таблицы. Правдивые nullable fields позволяют параллельно
делать UI, пока scoring/AppSec ещё не подключены.
