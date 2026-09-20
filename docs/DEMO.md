# Демо SourceHealth

## Подготовка

1. Заполнить локальный `.env` по [DEPLOYMENT](DEPLOYMENT.md), не показывая PAT и OAuth secrets.
2. Выполнить `docker compose up -d --build` и `npm run dev --prefix frontend`.
   Compose поднимает API, PostgreSQL, Redis и generic worker, но этот worker не потребляет
   очередь `analysis-code`, в которую направляются задачи профиля `mvp-v1`.
3. Собрать из корня repository изолированный runtime image:

   ```powershell
   docker build -f sourcehealth/sast/Dockerfile -t sourcehealth-sast .
   ```

4. В отдельном терминале запустить trusted worker с его собственным environment:

   ```powershell
   $env:ANALYSIS_PROFILE = "mvp-v1"
   $env:CODE_RUNTIME_ENABLED = "true"
   $env:CODE_RUNTIME_IMAGE = "sourcehealth-sast"
   python -m sourcehealth.application worker-code
   ```

   Полный MVP требует отдельного consumer очереди `analysis-code`. Для проверенного
   Windows/local demo допустим существующий `SimpleWorker` и Docker Desktop; production
   recommendation — выделенный trusted Linux host. Docker socket нельзя монтировать в
   backend или generic worker.
5. Проверить `python -m sourcehealth.application doctor`: профиль `mvp-v1`, code runtime,
   PostgreSQL и Redis должны быть доступны.
6. Открыть `http://127.0.0.1:5173`.

## Сценарий показа

1. Открыть public leaderboard: показать сортировку по Health, likes и активности,
   language filter, pagination и честные пустые значения.
2. Открыть SourceHealth team-41 и последний analysis. Показать Health 69.35, coverage 65%,
   шесть category slots, evidence и рекомендации. Объяснить, почему Issues score отсутствует
   при пустом tracker и почему Security остаётся NO_DATA.
3. Скачать Markdown report и сверить score/coverage с экраном.
4. Войти через Яндекс ID. После `/me` открыть `/sourcecraft`, подключить отдельный PAT,
   выбрать доступный public repository и запустить анализ. PAT не показывать и не сохранять
   в браузерных storage.
5. Показать историю запусков, повторный analysis и неизменяемый старый report. Завершить
   logout; он удаляет server session и Redis connection.

## Операторская проверка

```powershell
python -m sourcehealth.application probe-sourcecraft https://sourcecraft.dev/lct-hackaton-2026/case-18-repo-health-score-team-41
python -m sourcehealth.application accept-public https://sourcecraft.dev/lct-hackaton-2026/case-18-repo-health-score-team-41 --timeout 900
```

Live probe, contract и accept-public подтверждены. Ручной browser OAuth flow нужно пройти
перед показом в той же среде; build и mocked tests его не заменяют.

## Честные ограничения

- Official SourceCraft AppSec interface не найден в опубликованном Swagger: Security=NO_DATA.
- Private analysis выключен до подтверждённого delegated permission bridge.
- Среди ограниченно просмотренных первых 20 public repositories не подтверждён large-кандидат
  по порогу 10 000 files, 20 000 commits или 500 MB. Нельзя выдавать меньший repo за proof.
- Для настоящего large proof нужен существующий подходящий public repository либо разрешение
  создать специальный безопасный SourceCraft fixture.
