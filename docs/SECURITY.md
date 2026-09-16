# Безопасность и недоверенные репозитории

## Границы доверия

Исходники, README, comments, issue body, filenames и API error text — недоверенные
данные. Они не становятся инструкциями исполнителя/LLM. Правила нашего анализатора
загружаются только из доверенного пакета или явно выбранной оператором rules-dir.
Код анализируемого проекта не импортируется и не выполняется.

## Runtime

Сохранённый Docker workflow: clone container с сетью → scan container без сети →
cleanup обоих контейнеров и volume в finally. HTTPS host allowlist SourceCraft,
redirects выключены, hooks отключены, credential helper пустой, submodules не обходятся,
полная история default branch без shallow. Analyze stage: read-only repository/rootfs,
UID 10001, network none, cap-drop ALL, no-new-privileges, ограничение CPU/memory/PIDs/time.
Имена ресурсов создаёт сервис, не пользовательский repo. Cleanup failure виден в результате.

**Docker socket даёт чрезвычайно привилегированный доступ к хосту.** Нельзя считать
read-only socket mount безопасной изоляцией. Compose API-only worker socket не получает.
Для `worker-code` — отдельный изолированный runner host/VM с доверенным оператором,
Docker CLI/Engine; общий backend image/worker не получает socket или privileged mode.
Ограниченный контроллер запуска, filesystem с quotas и egress allowlist на clone stage
остаются условиями публичного deployment.
Контейнер анализа не получает socket/PAT/home directory. AnalysisRuntime позволяет
заменить Docker executor без изменения analyzer logic.

Текущий volume не имеет дисковой квоты; timeout/memory limits её не заменяют.
Прежде чем принимать массовые web clone jobs, нужны disk quota, concurrency budget,
уборщик оставшихся ресурсов после смерти хоста и мониторинг cleanup_pending.
finally покрывает обычные ошибки/timeout, но не гарантирует исполнение после SIGKILL
оркестратора/потери машины. Raw source не должен попадать в persistent DB.

## Secrets и identity

PAT допускается в .env/service configuration, не в URLs/JSON/report/DB/logs.
OAuth token используется для identity и затем не сохраняется. Session cookie opaque,
state одноразовый; детали — [AUTH](AUTH.md). SecretStr скрывает repr, но не защищает
ручной get_secret_value() print: вывод таких значений запрещён.

В findings сохраняются тип проблемы, severity и relative location, не source line
или secret value. Исходные API descriptions/comments не сохраняются без отдельного
allowlist и обоснования. Даже synthetic тестовые tokens создавать из коротких частей
в runtime, не коммитить реалистичные цельные credentials/webhook URLs.

## Public/private

Public API выдаёт только visibility=public. Private/unknown, в том числе report по
известному UUID, возвращают 404. Нужна актуальная authorization при включении private
функций; UUID сам по себе не permission. Cached результат не обходит ACL. Service PAT
не передаёт свои полномочия пользователю Я ID. Bridge не подтверждён — private flow закрыт.

## Логи и ошибки

Используется стандартный logging с JSON formatter: time, level, event, component,
request_id, analysis_id, repository_id. Отсутствующие IDs — null. Произвольные exception
args/body не сериализуются. API request IDs генерируются сервисом, недоверенный header
не принимается как логируемое содержимое. Uvicorn access log отключён; proxy должен
исключать query callback. HTTP errors: стабильный code/message/request_id, без stacktrace.
Включая debug, не логировать PAT, OAuth, source code и values secrets.

## До публичного deployment

HTTPS, реальные credentials через secret storage, ограниченные DB/Redis network ACL,
rate limits analysis requests, browser auth acceptance, production backups/restore,
AppSec/SourceCraft authorization, resource quotas и обновления dependency lock.
Это конкретные задачи следующего этапа, не заявление о готовой production защите.
