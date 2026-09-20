# Mandatory 100 Closure — журнал приёмки

Статус: **в работе, Definition of Done не выполнен**. Дата: 20.09.2026.
Ветка: `feature/` + `mandatory-100-closure`.
Базовый GitHub commit: 679e10ea3a7cea45f6f022371b28f953aaac4966.
PR/merge/push feature в SourceCraft main запрещены до отдельного разрешения.

## Проверенная исходная картина

- GitHub Actions для базы: success, https://github.com/No1se-pi/SourceHealth/actions/runs/35510831612.
- SourceCraft main: `aa225141a057fb0ad28c49e6bc37409f8d8903fd`,
  `Run SourceCraft checks in native Python and Node cubes`, 2026-09-20T19:57:15+03:00.
- Сравнены Git blob IDs всех 257 файлов: содержимое GitHub базы и SourceCraft совпадает,
  кроме дополнительного `.sourcecraft/ci.yaml`. Повторный перенос не требуется.
- Репозиторий public, default branch main; CI run 4 success.
- Миграция базы 0001; повторный OpenAPI export не изменил контракт.

## Текущий атомарный этап

- Likes читаются только из `rating.reaction_counts.positive_low` (uint64 string).
  Отсутствующий rating/невалидный count — null. Полный sparse список без Like — 0.
  Существующее поле PostgreSQL int32: слишком большой count остаётся null, не обрезается.
- Import и worker refresh обновляют likes; cache metadata переведён на новый ключ.
- CI Run: официальный Swagger говорит, что public IDs пока отсутствуют;
  collector использует slug при пустом id. Epoch незавершённых стадий — неизвестная дата.
- Regression tests добавлены. Полный unit suite: 180 tests, OK, skipped=16.
  Ruff passed; live probe team-41 overall=ok; opt-in contract test passed.
- Рейтинг team-41: один Diamond, likes=0, rating.value=5 не является likes.

## Исследование официального API

Swagger https://api.sourcecraft.tech/docs/sourcecraft.swagger.json, version 0.0.1,
SHA256 `c3b1d84647cdf553cda63ff6e6ddf59d00ee36a5aa40470ad44607320639d7c3`.
В paths не найдены appsec/sast/vulnerability/sarif/finding/incident/scanning routes.
Это предварительный результат; полный AppSec/CLI review ещё не закончен.
GET /user и GET /orgs/lct-hackaton-2026/repos успешно проверены с локальным PAT;
личные данные и credential не сохранялись.
Документация PAT: https://sourcecraft.dev/portal/docs/en/sourcecraft/operations/api-start.
CLI IAM/PAT: https://sourcecraft.dev/portal/docs/en/cli-ref/src-auth-login.
Delegated Я ID → SourceCraft bridge этими проверками не подтверждён.

## Ограниченная discovery

GET /repos: одна страница, page_size=10, sort_by=created_at; есть следующая страница,
её не обходили. Получены public repositories:

- suzev/advent-test
- appolimp/hello
- sourcecraft/sourcecraft
- mibon2019/test
- fy-demonar/test1
- kamoksin/hello-world
- ellesaify/kitty-new
- sourcecraft/template-docker-image
- sourcecraft/template-node-js
- организация sourcecraft, repository `template-java-with-maven`

Это доказательство catalog API, **не** end-to-end leaderboard/UI/calibration acceptance.

## Второй checkpoint

Реализован SourceCraft PAT connection API/UI: AES-GCM Redis, отдельный ключ,
сессионный TTL, atomic write, logout/disconnect, /user verification, org listing
до 100 элементов с explicit has_more. Private/internal не сохраняются в public DB.
Обновлены OpenAPI и generated TS; добавлены cryptography/cffi/pycparser в server lock.
Это реализация и integration proof, не browser OAuth acceptance.
16 PostgreSQL/Redis integration tests прошли, Alembic upgrade/check прошли.
Frontend typecheck/build прошли. SourceCraft CI перенесён в feature tree без push.

## Продолжение

1. Integration tests import/refresh likes, затем import/discover этих 10 repositories,
   worker-code и 5–10 accept-public; сохранить только безопасные численные результаты.
2. Расширить security tests connection: wrong Origin, malformed PAT no-leak,
   invalid ciphertext, TTL expiry, concurrent logout. Пройти browser acceptance после OAuth setup.
3. Scoring control/calibration, empty issues semantics с новой v1.2; large-repo measurement.
4. AppSec evidence review, security review, SourceCraft CI в feature branch, docs/DEMO.
5. Полный acceptance gate из пользовательского задания, включая integration/Compose/runtime.

Пользователь подтвердил: OAuth client/secret/session/callback **пока не настроены**.
Browser Я ID acceptance требует настройки и ручного входа; не подменять тестовой сессией.
PostgreSQL/Redis подняты локально командой `docker compose up -d postgres redis migrate`.
Никакого deployment на сторонний сервер не выполнялось.

Точная следующая проверка: `python -m unittest tests.test_integration -v`
после настройки изолированной `_test` БД и Redis DB 15 по docs/TESTING.md.
Текущий checkpoint можно определить `git log -1 --format=%H`; журнал коммитится
вместе с описанными изменениями, поэтому self-referencing SHA в нём не записывается.
