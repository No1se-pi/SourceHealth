# 0005 — Security только из SourceCraft AppSec

## Context
ТЗ прямо требует реальные AppSec SAST/SCA/secret findings. Уже существующий scanner
SourceHealth полезен, но не является заменой платформенного security источника.

## Decision
Local scanner сохранён как sourcehealth_local/code_health с id sast для совместимости.
Отдельная AppSec boundary, sourcecraft_appsec/security. Scoring фильтрует неподходящий
source и проверяет evidence refs. Неподтверждённый AppSec endpoint → NO_DATA, не fake facts.

## Consequences
Security Score остаётся null до реальной интеграции/методики. Требуются официальные
permissions/schema и live acceptance. CI secrets endpoint не используется как scanner API.
