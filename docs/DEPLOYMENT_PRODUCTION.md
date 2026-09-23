# Production deployment bundle

Текущий production стенд работает на `https://sourcehealth.tech`. В `deploy/` находится воспроизводимый bundle для обновления: Caddy обслуживает собранный frontend и проксирует только `/api/*` на backend; PostgreSQL и Redis публикуются только на loopback; generic worker не получает Docker socket. `worker-code` запускается отдельным host-level systemd service и только он создаёт изолированные code-analysis containers.

Последняя безопасная проверка health endpoint: 2026-09-23, `GET https://sourcehealth.tech/api/v1/health` → `{"status":"ok","service":"sourcehealth"}`.

## Применение владельцем

1. Скопировать `.env.production.example` в `.env.production`, заполнить значения на сервере и ограничить права файла. `SESSION_SECRET` и `SOURCECRAFT_CREDENTIAL_KEY` должны быть независимыми случайными значениями.
2. Зарегистрировать в Yandex callback `https://sourcehealth.tech/api/v1/auth/yandex/callback`.
3. Собрать frontend (`npm ci --prefix frontend && npm run build --prefix frontend`), затем запустить `docker compose -f deploy/compose.prod.yaml up -d --build`.
4. На доверенном host установить image `sourcehealth-sast`, включить `sourcehealth-worker-code.service` и `sourcehealth-scheduler.timer`. Docker socket не монтируется в backend или generic worker.
5. Проверить `curl -fsS https://sourcehealth.tech/api/v1/health`; ожидается `{"status":"ok","service":"sourcehealth"}`. Затем вручную пройти [browser acceptance](OAUTH_SOURCECRAFT_BROWSER_ACCEPTANCE.md).

Последняя проверка production URL выполняется отдельно от локальной compose validation; не записывайте credentials и cookies в этот журнал. Bundle предназначен для воспроизводимой установки/обновления существующего production стенда.
