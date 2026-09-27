# Production deployment

Production работает на `https://sourcehealth.tech` и обновляется без создания параллельного
Compose stack. Фактический инфраструктурный контракт:

- Compose project: `sourcehealth`;
- PostgreSQL volume: `sourcehealth_postgres-data`;
- Redis volume: `sourcehealth_redis-data`;
- секреты и runtime-настройки: `/etc/sourcehealth/sourcehealth.env`, права `600`;
- Caddy работает как host-level systemd service и проксирует `/api/*` на
  `127.0.0.1:8000`; frontend читается из `/opt/sourcehealth/frontend/dist`;
- generic worker работает в Compose без Docker socket;
- `worker-code` и scheduler работают как host-level systemd units.

`deploy/compose.prod.yaml` фиксирует тот же project и объявляет оба data volume как
`external: true`. Поэтому Compose откажется запускаться, если существующие volumes не
найдены, вместо создания пустой PostgreSQL или Redis. Caddy в Compose отсутствует.

## Обязательная проверка перед обновлением

До `compose up` оператор обязан проверить фактические labels и mounts:

```bash
cd /opt/sourcehealth
docker compose ls -a
docker inspect sourcehealth-postgres-1 \
  --format '{{index .Config.Labels "com.docker.compose.project"}} {{range .Mounts}}{{.Name}}:{{.Destination}}{{end}}'
docker inspect sourcehealth-redis-1 \
  --format '{{index .Config.Labels "com.docker.compose.project"}} {{range .Mounts}}{{.Name}}:{{.Destination}}{{end}}'
docker volume inspect sourcehealth_postgres-data sourcehealth_redis-data
systemctl is-active caddy sourcehealth-worker-code.service sourcehealth-scheduler.timer
```

Ожидаются project `sourcehealth`, mounts `sourcehealth_postgres-data:/var/lib/postgresql/data`
и `sourcehealth_redis-data:/data`. Любое расхождение блокирует обновление.

Создать отдельный timestamped backup БД и конфигурации, сохранить текущий git SHA:

```bash
stamp=$(date -u +%Y%m%dT%H%M%SZ)
backup=/var/backups/sourcehealth/$stamp
install -d -m 700 "$backup"
git rev-parse HEAD > "$backup/rollback-sha.txt"
install -m 600 /etc/sourcehealth/sourcehealth.env "$backup/sourcehealth.env"
install -m 600 /etc/sourcehealth/compose.production.yaml "$backup/compose.production.yaml"
docker compose --env-file /etc/sourcehealth/sourcehealth.env \
  -f compose.yaml -f /etc/sourcehealth/compose.production.yaml \
  exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  | gzip -9 > "$backup/postgres.sql.gz"
gzip -t "$backup/postgres.sql.gz"
chmod 600 "$backup"/*
```

Не печатать значения env и не копировать populated env в репозиторий.

## Штатное обновление существующего стенда

Production продолжает использовать существующую пару файлов
`compose.yaml + /etc/sourcehealth/compose.production.yaml`. Это сохраняет текущие labels,
project name, volumes и loopback ports.

```bash
cd /opt/sourcehealth
git fetch origin --prune
git checkout main
git pull --ff-only origin main
npm ci --prefix frontend
npm run build --prefix frontend
docker build -f sourcehealth/sast/Dockerfile -t sourcehealth-sast .

systemctl stop sourcehealth-scheduler.timer
systemctl stop sourcehealth-worker-code.service
docker compose --env-file /etc/sourcehealth/sourcehealth.env \
  -f compose.yaml -f /etc/sourcehealth/compose.production.yaml \
  up -d --build
systemctl start sourcehealth-worker-code.service
systemctl start sourcehealth-scheduler.timer
```

`migrate` выполняет `python -m alembic upgrade head` и должен завершиться с exit code 0 до
старта backend/worker. Docker socket нельзя монтировать в backend или generic worker.
Host Caddy и production secrets при обновлении не изменяются.

`deploy/compose.prod.yaml` является проверяемым standalone-описанием того же контракта. Для
его `config`/аварийного применения нужно явно указать существующий env:

```bash
SOURCEHEALTH_ENV_FILE=/etc/sourcehealth/sourcehealth.env \
docker compose --env-file /etc/sourcehealth/sourcehealth.env \
  -f deploy/compose.prod.yaml config
```

Не применять этот файл, пока `docker volume inspect` не подтвердил оба external volumes.

## Проверка и rollback

```bash
docker compose --env-file /etc/sourcehealth/sourcehealth.env \
  -f compose.yaml -f /etc/sourcehealth/compose.production.yaml ps
systemctl is-active caddy sourcehealth-worker-code.service sourcehealth-scheduler.timer
curl -fsS https://sourcehealth.tech/api/v1/health
```

Ожидаемый health: `{"status":"ok","service":"sourcehealth"}`. При ошибке остановить
обновление, вернуть SHA из `rollback-sha.txt`, пересобрать прежнюю версию через ту же
Compose topology и проверить health. Восстановление БД требуется только если миграция успела
изменить данные и это подтверждено отдельно.
