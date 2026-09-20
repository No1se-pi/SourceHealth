# Roadmap после MVP analytics, 19.09.2026

## Реализованный обязательный batch

- Documentation snapshot analyzer; Issues и CI collectors/analyzers.
- PR/contributors/published releases, Activity совместно с прежним GitActivity.
- Local SAST + TODO/FIXME density, bounded blame age и большие code files.
- mvp-score-v1.1, minimum coverage, детерминированные рекомендации и Markdown.
- Public URL import, ограниченное org/global discovery по официальному Swagger.
- Один mvp-v1 run через trusted analysis-code, шесть category slots и persistence.
- Контрактные unit tests и настоящий HTTP/RQ/PostgreSQL/Redis end-to-end с fixtures
  внешних систем. Точные проверки — [MVP_ANALYTICS](MVP_ANALYTICS.md).

Эти пункты реализованы и локально проверены. Public live SourceCraft pipeline подтверждён
20.09.2026; реальный OAuth browser acceptance и полное исходное хакатонное ТЗ ещё не закрыты.

## P0 — оставшаяся внешняя и продуктовая приёмка

Операторский контур `probe-sourcecraft` → `accept-public` и opt-in live test реализован.
Успешный public live прогон с локальным PAT зафиксирован в [LIVE_ACCEPTANCE](LIVE_ACCEPTANCE.md).

| Задача | Владелец | Что нужно / критерий |
|---|---|---|
| Успешный public SourceCraft доступ | Backend + владелец доступа | Закрыто 20.09: metadata и analytics complete, полный worker pipeline принят; discovery отдельно не принимался |
| Official AppSec | Backend + организаторы | Base URL/auth/full schema/enums/repo mapping и sanitized real fixture; затем подключить collector |
| Я ID → private SourceCraft permission bridge | Backend + организаторы | Подтверждённый механизм проверки прав; private остаются disabled |
| Живой public каталог и отчёты | Backend/Analyzer | Один public import → mvp worker → score/evidence/Markdown принят; осталось проверить discovery и выборку разных repo |
| Калибровка policy | Analyzer/Backend | 5–10 разных реальных repo: размеры/языки, scores и coverage; проверить Activity thresholds и влияние абсолютных SAST counts |
| Реальный вход и UI flow | Frontend/Backend | OAuth app, public import → run → partial/evidence/recommendations → Markdown, logout |
| Большой repository | Analyzer/Backend | SourceCraft repo ≥10 000 tracked files или ≥20 000 commits или ≥500 МБ; time/memory/coverage/cleanup |
| Лайки рейтинга | Backend | Подтвердить mapping rating/reactions; не выдавать rating.value за likes |
| Стенд и материалы сдачи | Вся команда | Deployment, SourceCraft repository, URL, презентация, видео, примеры отчётов |

Не нужно повторно реализовывать foundation или ждать AppSec для проверки пяти остальных
категорий. Глобальный discovery endpoint уже известен: blocker теперь доступ и live
приёмка, а не отсутствие документации. Приватность и official Security не закрываются mocks.

## P1 — устойчивость эксплуатации

Квоты запросов, отдельные TTL/ETag ресурсов, rename/visibility reconciliation,
scoped private caches после ACL bridge, code snapshot reuse и requested-SHA pinning,
disk quota/cleanup после смерти host, измеренная оптимизация большой Git-истории,
retention/backups/restore, нагрузка нескольких workers. Фактический HEAD mvp-v1 уже
сохраняется; code cache ещё не используется. Budget коллекции и per-source partial
semantics уже реализованы.

## P2 — дополнительные возможности

ML/LLM, Road to 80, badges, сравнения, bus factor, anti-gaming, PDF, admin panel.
Kubernetes/Kafka/microservices не являются планом по умолчанию. Сначала обязательные
сценарии исходного ТЗ; никакая бонусная функция не заменяет live приёмку.

## Definition of done

Реализация, документация и meaningful tests меняются вместе. Mock/contract, настоящая
локальная инфраструктура, browser и live external acceptance указываются отдельно.
NO_DATA не выдаётся за 0, partial — за полный охват, build — за пользовательскую приёмку.
