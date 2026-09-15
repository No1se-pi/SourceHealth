# Backend и точки расширения

## Где находится логика

`api/app.py` — composition root и небольшая группа routers в одном файле. Создаёт
settings, engine/session factory, Redis, application/auth services. Здесь HTTP codes,
cookies, валидация входа и сериализация DTO. Расчётов метрик и scoring в routers нет.
По мере роста можно разнести routers по ресурсам без изменения контракта.

`application/services.py` — транзакционные команды: register, request_analysis,
transition, finish, enqueue_due. `application/jobs.py` — доставка и исполнение.
`integrations/sourcecraft` — транспорт и collectors. `storage/models.py` — SQLAlchemy
модели. `core` — переносимые понятия без PostgreSQL/HTTP/Redis imports.

В `api/app.py` читающие SELECT пока находятся рядом с handlers: это простые
проекции persistence → DTO, не аналитика. При усложнении фильтров выделять query service,
не вводить repository interface на каждую таблицу ради симметрии.

## Добавление коллектора и анализатора

1. Коллектор получает `RepositoryRef`, использует общий клиент и возвращает `CollectedFacts`.
2. Сохраняет только allowlisted безопасные факты; ограничивает число страниц/объём.
3. Application собирает их в context под именем коллектора, отдельно записывает availability.
4. Анализатор получает context и возвращает AnalyzerResult. Не пишет в DB и не ставит jobs.
5. Зарегистрировать анализатор в конкретном профиле в `application/jobs.py`.
6. Если inputs/поведение профиля изменились — изменить `ANALYSIS_PROFILE`; иначе может
   быть переиспользован завершённый run со старым набором анализаторов.
7. Добавить unit fixtures и обновить ANALYTICS/SOURCECRAFT. Core/DTO/migration обычно не меняются.

Для дальнейшего роста профили выделяются в обычный Python registry, когда появляется
второй реально поддерживаемый профиль. Сейчас поддерживается только `platform-v1`:
repository metadata + availability AppSec. Изменение строки настройки само по себе
не включает новые анализаторы или clone.

## Ошибки и конфигурация

ServiceError содержит код и HTTP status. Публичная ошибка имеет только code/message/request_id.
Request validation не отражает присланные значения, чтобы PAT из ошибочного запроса
не появился в ответе. SQLAlchemy errors и Redis errors дают 503, неожиданные ошибки — 500.
`GET health` — liveness; он не проверяет БД. Для readiness использовать health Compose
и отдельную проверку подключения/миграции.

`Settings` читает environment и необязательный `.env`. URL БД и токены — SecretStr,
но это не заменяет запрет логирования. Все изменения environment требуют перезапуска
процесса. CLI-only установка не требует server extras.

## Состояние публичных use cases

Чтение открытых repository/run/report реализовано. POST анализа требует реальную
сессию Я ID и правильный Origin, возвращает queued/cached run. Операторская CLI
`register` проверяет публичность через SourceCraft и ставит первый run.
HTTP endpoint произвольного import URL отсутствует. Private repos и force refresh
через HTTP закрыты до реализации авторизации SourceCraft и допустимой refresh policy.
