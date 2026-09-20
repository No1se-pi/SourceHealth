# Локальный запуск и модель deployment

## Требования

Python ≥3.11, Git, Docker Engine/Desktop с Compose v2 (поддержка optional env_file),
Node 22.12+ для frontend. Проверенная среда разработки: Windows/PowerShell, Python 3.11,
Node 24. Worker production/development запускается Linux-контейнером: RQ Worker использует fork.
Compose credentials предназначены только для loopback development.

## Первый запуск

Из корня repository:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-server.lock
python -m pip install -e ".[dev,server]"
Copy-Item .env.example .env
docker compose config --quiet
docker compose up -d --build
npm ci --prefix frontend
npm run dev --prefix frontend
```

Миграции и backend внутри образа запускаются через `python -m alembic` и
`python -m uvicorn`. Это сохраняет запуск в hardened-окружениях, где исполнение
установленных console scripts запрещено политикой mount (`operation not permitted`).

Не копировать .env.example поверх своего заполненного .env. Linux/macOS activation:
`source .venv/bin/activate`. `requirements-server.lock` фиксирует runtime dependency
snapshot; npm ci использует package-lock.json. Обновление lock — отдельный проверяемый PR.

Адреса: frontend http://127.0.0.1:5173, backend http://127.0.0.1:8000, API docs
http://127.0.0.1:8000/docs. PostgreSQL доступен локально на 15432 (POSTGRES_PORT),
Redis на 6379. Внутри сети Compose — postgres:5432 и redis:6379.
15432 выбран, чтобы обходить часто занятый/зарезервированный 5432 на Windows.

Сначала migrate применяет Alembic; backend/worker ждут его успешного завершения.
Первая БД пуста — это нормально. Нет fake leaderboard или dummy users.

## Backend на хосте

```powershell
docker compose up -d postgres redis
python -m alembic upgrade head
python -m uvicorn sourcehealth.api.app:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

Не запускать одновременно второй backend на том же порту. На Windows URL БД использует
127.0.0.1:15432: localhost может сначала пытаться подключиться к недоступному IPv6.
Подключения БД ограничены connect_timeout=10 секунд.

## Добавить настоящий публичный SourceCraft repo

Если API требует PAT, заполнить SOURCECRAFT_PAT локально; не добавлять его в Git.
До запуска Compose доступ можно проверить без DB/Redis командой `probe-sourcecraft`, а
сквозной pipeline после запуска инфраструктуры — `accept-public`; точные команды и коды
завершения описаны в [LIVE_ACCEPTANCE](LIVE_ACCEPTANCE.md).
Операторская команда проверяет visibility через настоящий SourceCraft API:

```powershell
python -m sourcehealth.application register https://sourcecraft.dev/ORGANIZATION/REPOSITORY
```

Подставить существующие slugs. Команда печатает repository_id и analysis_id.
По умолчанию фоновый анализ собирает metadata; `code-v1` добавляет Git/SAST через trusted
worker ниже. `mvp-v1` добавляет обязательную аналитику и численную policy; partial
из-за AppSec NO_DATA ожидаем, но не требует null overall при достаточном coverage.
Непубличный/unverified repo не принимается.

## Trusted code worker — отдельный execution profile

Обычный `docker compose up` поднимает PostgreSQL, Redis, migrations, API и generic worker.
Он не потребляет очередь `analysis-code`: для полного `mvp-v1` нужен отдельный trusted
`worker-code`. Это операторский Linux host/VM с Docker Engine/CLI, установленным
SourceHealth той же ревизии и сетевым доступом к сервисным PostgreSQL/Redis. Процесс имеет
привилегии Docker daemon на **выделенной машине**. Не переносить этот доступ в API или
generic Compose worker и не монтировать туда Docker socket.

Production recommendation — отдельный Linux trusted host. Для локального Windows demo
допустим проверенный путь через существующий `SimpleWorker` и Docker Desktop.

На trusted host, из checkout проверенной ревизии:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-server.lock
python -m pip install -e '.[server]'
docker build -f sourcehealth/sast/Dockerfile -t sourcehealth-sast .
# DATABASE_URL / REDIS_URL — сервисные адреса через environment/secret storage.
export ANALYSIS_PROFILE=mvp-v1
export CODE_RUNTIME_ENABLED=true
export CODE_RUNTIME_IMAGE=sourcehealth-sast
export CODE_RUNTIME_TIMEOUT=180
export ANALYSIS_TIMEOUT=600
python -m sourcehealth.application worker-code
```

Для полного MVP задать `ANALYSIS_PROFILE=mvp-v1` у API, register и scheduler
(`code-v1` остаётся совместимым старым профилем),
перезапустить соответствующие процессы. Обычный worker можно оставить для старых
`platform-v1` jobs. Dispatcher сам выбирает очередь по сохранённому профилю run.
API не нуждается в `CODE_RUNTIME_ENABLED=true`: настройка включается только у
trusted code worker. Image — настройка оператора, не пользовательский HTTP параметр.

Один вызов runtime делает clone → offline Git/SAST/documentation/debt → cleanup. Никаких install/test/build
команд целевого repo. Clone не получает PAT; поддерживаются только verified public repo.
Timeout/clone error/отсутствие Docker → partial report с сохранением platform facts.
Выделенный runtime включать сначала в контролируемой среде: disk quotas,
уборка после SIGKILL и code cache ещё требуют операционной приёмки. mvp-v1 уже сохраняет
фактический SHA, но не принимает пользовательский SHA для pinning.

## Public import и ограниченное discovery

После входа Я ID форма на leaderboard принимает SourceCraft URL, проверяет public
через API и открывает страницу repo; запуск — существующей кнопкой. SOURCECRAFT_PAT
настраивается оператором отдельно от OAuth Я ID. Private пока запрещены.

```powershell
python -m sourcehealth.application discover --organization ORGANIZATION --limit 20
python -m sourcehealth.application discover --limit 20
```

Без organization используется подтверждённый Swagger endpoint GET /repos. Каждая
найденная запись повторно проверяется, импортируется и ставится на анализ. Это один
ограниченный batch (limit 1..100, 120с), а не полный обход каталога. Вывод содержит число
импортов и availability; partial не означает полный каталог. Live доступ ещё не принят.

## Изолированный Compose smoke

```powershell
python scripts/compose_smoke.py
```

Скрипт реально собирает backend/worker, поднимает PostgreSQL/Redis/migrate/backend/worker,
ждёт health, проверяет HTTP 200 и регистрацию RQ worker. Проект `sourcehealth-smoke-*`,
случайные порты, собственные volumes и пустой env-file изолируют его от обычного стенда.
В `finally` выполняется `docker compose down -v --remove-orphans` только для smoke-проекта.
CI имеет дополнительный `always()` cleanup. Live SourceCraft/Я ID/code scan не требуется.

## Scheduler и восстановление доставки

```powershell
docker compose run --rm scheduler
docker compose exec worker python -m sourcehealth.application dispatch
```

One-shot scheduler нужно вызывать регулярно. Linux cron из каталога deployment,
например раз в минуту: `* * * * * cd /srv/sourcehealth && docker compose run --rm scheduler`.
Не вставлять scheduler loop в FastAPI. По умолчанию repository refresh раз в сутки,
command раз в минуту обеспечивает due selection/recovery/dispatch.

## Я ID для локального браузера

Реально зарегистрировать OAuth приложение с callback:
`http://127.0.0.1:5173/api/v1/auth/yandex/callback`. В .env для этого dev-сценария:
PUBLIC_ORIGIN=http://127.0.0.1:5173, YANDEX_REDIRECT_URI с этим callback,
COOKIE_SECURE=false, клиентские credentials и случайный SESSION_SECRET ≥32 символов.
Vite проксирует callback в backend, затем /auth/callback показывает результат.
После изменений перезапустить backend. Это явная локальная настройка; публичный
стенд использует HTTPS и COOKIE_SECURE=true. SourceCraft bridge отдельно не реализован.

## Диагностика

```powershell
docker compose ps
docker compose logs --tail 100 backend worker migrate
python -m alembic current
python -m alembic check
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
```

Health подтверждает живой HTTP процесс; доступ БД/Redis и миграции проверять отдельно.
Сопоставлять request_id/analysis_id в безопасных логах. Не выводить .env/credentials.
`docker compose down` останавливает сервисы, сохраняет named volumes; `down -v`
удаляет данные и не является обычной командой обновления.

## Scale / production

API можно масштабировать stateless, workers — через `docker compose up -d --scale worker=2`.
DB/Redis shared; PG locks удерживают single-flight. Соблюдать лимиты внешнего API и
ресурсов workers. Compose не является готовой production cloud конфигурацией:
нужны HTTPS reverse proxy, секреты, DB roles/backups, private network, rate limits,
cron, monitoring и restore drill. Не монтировать Docker socket в web API или обычный
platform worker. Code workers выделять по [SECURITY](SECURITY.md).
# Дополнительная настройка подключения SourceCraft

Для пользовательского PAT connection задайте отдельный `SOURCECRAFT_CREDENTIAL_KEY`:
base64 от 32 случайных байтов (`openssl rand -base64 32`). Не используйте SESSION_SECRET
повторно и не коммитьте значение. SOURCECRAFT_CONNECTION_TTL по умолчанию 1800с.
При смене ключа прежние подключения потребуют повторного ввода PAT.
Это не включает private analysis и не заменяет настройку Яндекс OAuth.
