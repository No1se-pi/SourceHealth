# Production deployment bundle

В `deploy/` находится минимальный production bundle для `sourcehealth.tech`: Caddy обслуживает собранный frontend и проксирует только `/api/*` на backend; PostgreSQL и Redis не публикуют порты; generic worker не получает Docker socket. `worker-code` запускается отдельным host-level systemd service и только он создаёт изолированные code-analysis containers.

## Применение владельцем

1. Скопировать `.env.production.example` в `.env.production`, заполнить значения на сервере и ограничить права файла. `SESSION_SECRET` и `SOURCECRAFT_CREDENTIAL_KEY` должны быть независимыми случайными значениями.
2. Зарегистрировать в Yandex callback `https://sourcehealth.tech/api/v1/auth/yandex/callback`.
3. Собрать frontend (`npm ci --prefix frontend && npm run build --prefix frontend`), затем запустить `docker compose -f deploy/compose.prod.yaml up -d --build`.
4. На доверенном host установить image `sourcehealth-sast`, включить `sourcehealth-worker-code.service` и `sourcehealth-scheduler.timer`. Docker socket не монтируется в backend или generic worker.
5. Проверить `curl -fsS https://sourcehealth.tech/api/v1/health`; ожидается `{"status":"ok","service":"sourcehealth"}`. Затем вручную пройти [browser acceptance](OAUTH_SOURCECRAFT_BROWSER_ACCEPTANCE.md).

В текущем окружении нет DNS/VPS и production OAuth credentials, поэтому deployment имеет статус **PREPARED**, а не PASS.
