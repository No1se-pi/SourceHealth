# Roadmap после foundation

## P0 — обязательный сквозной продукт

| Шаг | Владелец | Зависимость | Готово когда |
|---|---|---|---|
| Подтвердить AppSec API | Backend + организаторы | Доступ/документация | Есть официальный interface и sanitized real fixture |
| Подтвердить Я ID → SourceCraft permissions | Backend + организаторы | OAuth app/разрешённая схема | Реально получен список доступных repo, проверен запрет чужого |
| Documentation и Issues | Analyzer | Стабильные facts из Collector | Unit fixtures + evidence + корректный NO_DATA |
| CI/CD и platform activity | Analyzer/Backend | Verified endpoints | Полные/partial данные, время и refresh без изменения HEAD |
| Snapshot/cache и эксплуатация code profile | Backend | Уже подключённый code-v1 | Фактический SHA, pinning, quotas, cache hit при том же snapshot |
| Первая Score policy + recommendations | Backend + вся команда | Метрики и AppSec | Формула/weights/docs/replay и контрольные сценарии шести категорий |
| Leaderboard/detail UX | Frontend | DTO foundation уже готов | Score/categories/evidence/no-data/partial, фильтры и выгрузка |
| Реальный вход и собственный repo | Backend/Frontend | Подтверждённый bridge | Полный пользовательский сценарий, logout/permissions |
| Наполнение каталога | Backend | Discovery interface | Живые SourceCraft repo, воспроизводимый import/update |
| Демонстрация | Вся команда | Предыдущие шаги | Public/own repo, first/repeat run, Markdown, большой repo |

Не ждать AppSec, чтобы делать frontend и несекьюрные analyzers: они работают по
nullable contract. Но нельзя закрывать Security задачу локальным SAST или synthetic findings.

## P1 — устойчивость и операционная приёмка

Квоты analysis requests и внешнего API; TTL/ETag каждого ресурса; полный collection
provenance; rename/visibility reconciliation; private access scoped caches; code disk
quota и cleanup после смерти хоста; крупная история streaming/incremental при измеренной
необходимости; политики retention; production DB least privilege/backups/restore;
browser auth tests и нагрузочные сценарии нескольких workers.

## P2 — дополнительные возможности

ML context/peer comparison, AI grounded summary, badges, history comparisons, review
analytics, anti-gaming, PDF. Каждая функция требует отдельной пользы/критерия приёмки.
Ни одна не заменяет P0. Kubernetes/Kafka/microservices не являются планом по умолчанию.

## Definition of done

Результат работает на реальных данных/инфраструктуре, требуемых сценарием; контракт
и документация обновлены; tests meaningful и проходят; отсутствие данных не выдаётся
за успех/0; evidence проверяемо; secrets не утекли. Mock-based check обозначен как mock,
а live acceptance — как live. Код foundation сам по себе не закрывает продуктовый пункт ТЗ.
